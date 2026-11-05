"""Actualisation serveur et versions immuables, sans modifier les scripts existants."""
from __future__ import annotations

import copy
import csv
import gc
import hashlib
import importlib.util
import json
import ijson
import os
import re
import tempfile
import threading
from collections import Counter
from pathlib import Path
from uuid import uuid4
from functools import lru_cache

from actualiser_pully import Etat, ecrire_atomique, maintenant
from fiches_contraintes import contraintes
from observations_cantonales import export_observations

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE=ROOT/'API/bases/pully_parcelles_2026-11-04_1614.csv'


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    ids=[r.get('egrid') for r in rows]
    if not ids or any(not e for e in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Base vide ou EGRID manquants/dupliqués')
    return rows


def write_json(path,value):
    # Écrire progressivement : les fiches complètes dépassent 80 Mo et dumps()
    # en conserve plusieurs copies en mémoire avant même l'écriture.
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
        os.replace(tmp,path)
    finally:
        Path(tmp).unlink(missing_ok=True)


@lru_cache(maxsize=1)
def immutable_json(path):
    # Éviter de conserver l’ancienne base pendant le chargement de la suivante.
    immutable_json.cache_clear()
    gc.collect()
    with Path(path).open('rb') as stream:
        return dict(ijson.kvitems(stream,'',use_float=True))


def verifier_fiches(path,expected,version):
    verified=set()
    with path.open('rb') as stream:
        for egrid,fiche in ijson.kvitems(stream,'',use_float=True):
            if egrid in verified or fiche.get('egrid')!=egrid or fiche.get('version')!=version:
                raise ValueError('Fiche candidate incohérente')
            verified.add(egrid)
    if verified!=expected:raise ValueError('Version candidate incohérente')


class OperationState(Etat):
    def __init__(self,folder,operation):
        super().__init__(folder)
        self.folder=folder
        self.data.update(operation_id=operation,mode='contraintes')

    def maj(self,**values):
        super().maj(**values)
        if any(key in values for key in ('etape','statut')):
            print('Foncimo opération '+json.dumps({key:self.data.get(key) for key in
                ('operation_id','statut','etape','erreur','bilan')},ensure_ascii=False),flush=True)
        history=self.folder/'operations';history.mkdir(exist_ok=True)
        write_json(history/(self.data['operation_id']+'.json'),self.data)


class UpdateService:
    def __init__(self,storage=None,reference=None,contours=None,config=None,slopes=None,collector=None,base_collector=None,mode_actualisation="complet"):
        self.storage=Path(storage or ROOT/'API/versions')
        self.reference=Path(reference or DEFAULT_REFERENCE)
        self.contours=Path(contours or ROOT/'data/parcelles/source_esri_lv95.json')
        self.config=Path(config or ROOT/'code/criteres.json')
        self.slopes=Path(slopes or ROOT/'data/pentes_parcelles/pentes_parcelles.csv')
        self.collector=collector
        self.base_collector=base_collector
        self.mode_actualisation=mode_actualisation
        self.storage.mkdir(parents=True,exist_ok=True)
        self.pointer=self.storage/'version_active.json'
        self.lock=self.storage/'actualisation.lock'
        self.mutex=threading.Lock()
        self.thread=None
        spec=importlib.util.spec_from_file_location('_criteres_fiches',ROOT/'code/criteres_category.py')
        self.criteria=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.criteria)
        self.classifier_sha=sha(ROOT/'code/criteres_category.py')
        self._recover_initialisation()
        self._initialise()
        self._recover_interrupted()
        self._upgrade_interface()

    def _recover_initialisation(self):
        """Un arrêt brutal peut laisser un verrou avant la première version."""
        if self.pointer.exists() or not self.lock.exists():return
        before=self.lock.stat()
        try:owner=json.loads(self.lock.read_text())
        except (ValueError,OSError):return
        if not isinstance(owner,dict) or owner.get('operation_id')!='initialisation':return
        pid=owner.get('pid')
        if type(pid) is not int or pid<=0:return
        try:os.kill(pid,0)
        except ProcessLookupError:
            current=self.lock.stat()
            if (current.st_ino,current.st_mtime_ns)==(before.st_ino,before.st_mtime_ns):
                self.lock.unlink()
        except PermissionError:return

    def _recover_interrupted(self):
        if not self.lock.exists():return
        before=self.lock.stat()
        try:owner=json.loads(self.lock.read_text())
        except (ValueError,OSError):return
        if not isinstance(owner,dict) or not re.fullmatch('[a-f0-9]{32}',str(owner.get('operation_id',''))):return
        try:os.kill(int(owner['pid']),0)
        except ProcessLookupError:
            operation=owner['operation_id'];state=OperationState(self.storage,operation)
            try:state.data=self.status(operation)
            except KeyError:pass
            state.maj(statut='erreur',etape=None,fin_utc=maintenant(),version_active=self.active(),
                      erreur='Opération interrompue avant la fin ; dernière version valide conservée.')
            current=self.lock.stat()
            if (current.st_ino,current.st_mtime_ns)==(before.st_ino,before.st_mtime_ns):self.lock.unlink()
        except (PermissionError,ValueError,KeyError):return

    def _initialise(self):
        if self.pointer.exists():
            return
        # Verrou partagé avec le CLI existant ; aucune initialisation concurrente.
        fd=os.open(self.lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,json.dumps({'pid':os.getpid(),'operation_id':'initialisation'}).encode());os.close(fd)
        try:
            if self.pointer.exists():return
            rows=read_csv(self.reference)
            cfg=self.criteria.load_criteria(self.config)
            version='initiale-'+uuid4().hex
            folder=self.storage/version;folder.mkdir()
            slope_snapshot=folder/'pentes.csv'
            if self.slopes.exists():slope_snapshot.write_bytes(self.slopes.read_bytes())
            fiches=self._fiches(rows,{}, {},cfg,version,contours_path=self.contours)
            write_json(folder/'parcelles.json',{r['egrid']:r for r in rows})
            (folder/'contours.json').write_bytes(self.contours.read_bytes())
            self._interface(folder, rows, fiches, self.contours, slope_snapshot)
            write_json(folder/'fiches.json',fiches)
            write_json(folder/'manifest.json',dict(version=version,empreinte=None,
                mode='base_initiale_contraintes_inconnues',regles=cfg,date_creation=maintenant(),
                reference={'fichier':str(self.reference),'sha256':sha(self.reference)},
                contours={'fichier':str(self.contours),'sha256':sha(self.contours)}))
            write_json(self.pointer,{'version':version})
        finally:
            self.lock.unlink(missing_ok=True)

    def _upgrade_interface(self):
        """Migration locale du contrat d'affichage ; le CSV actif et les observations sont conservés."""
        previous=self.active();folder=self.version_path(previous)
        export=folder/'interface.json'
        if export.exists() and json.loads(export.read_text()).get('schema_version')==2:return
        fd=os.open(self.lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,json.dumps({'pid':os.getpid(),'operation_id':'migration_interface'}).encode());os.close(fd)
        try:
            if self.active()!=previous:raise RuntimeError('Version active modifiée pendant la préparation')
            if not (folder/'contours.json').exists():
                raise ValueError('Ancienne version sans contours archivés : migration impossible sans mélanger les sources')
            with tempfile.TemporaryDirectory(prefix='.interface-v2-',dir=self.storage) as temp:
                stage=Path(temp);version='application-'+uuid4().hex
                incoming=json.loads((folder/'parcelles.json').read_text());rows=list(incoming.values())
                fiches=copy.deepcopy(json.loads((folder/'fiches.json').read_text()))
                prior=json.loads((folder/'manifest.json').read_text());cfg=prior['regles']
                for name in ('contours.json','pentes.csv','simulation.json'):
                    if (folder/name).exists():(stage/name).write_bytes((folder/name).read_bytes())
                # Les anciennes versions initiales n'archivaient pas le CSV de pentes.
                # Reprendre uniquement les mesures déjà exportées, sans lire un raster actuel.
                if not (stage/'pentes.csv').exists() and export.exists():
                    old_payload=json.loads(export.read_text());slope_rows=[]
                    for item in old_payload.get('parcels',[]):
                        facts=item[6][5]
                        slope_rows.append({'egrid':item[1],'pente_mediane_pct':facts[7],
                            'part_pixels_valides_pct':facts[8],'statut_calcul':'repris_export_precedent'})
                    if slope_rows:
                        with (stage/'pentes.csv').open('w',encoding='utf-8',newline='') as stream:
                            writer=csv.DictWriter(stream,fieldnames=list(slope_rows[0]))
                            writer.writeheader();writer.writerows(slope_rows)
                from donnees_interface import voisinage
                neighbors=voisinage(rows,stage/'contours.json',self.criteria)
                for row in rows:
                    egrid=row['egrid'];fiches[egrid]['version']=version
                    fiches[egrid]['classement']=self.criteria.evaluate_parcel(row,cfg,neighbors.get(egrid))
                self._interface(stage,rows,fiches,stage/'contours.json',stage/'pentes.csv')
                write_json(stage/'parcelles.json',incoming);write_json(stage/'fiches.json',fiches)
                manifest=dict(prior,version=version,precedente=previous,empreinte=None,
                              mode='migration_interface_v2',date_creation=maintenant(),schema_interface=2)
                write_json(stage/'manifest.json',manifest)
                payload=json.loads((stage/'interface.json').read_text())
                if payload['total']!=len(rows) or {r[1] for r in payload['parcels']}!=set(fiches):
                    raise ValueError('Migration interface incomplète')
                os.rename(stage,self.storage/version)
                write_json(self.pointer,{'version':version})
                # Une vérification sans changement appartient aux observations, pas à l'ancienne présentation.
                checked=self.storage/'verification_sources.json'
                if checked.exists():
                    data=json.loads(checked.read_text())
                    if data.get('version')==previous:
                        data['version']=version;write_json(checked,data)
        finally:self.lock.unlink(missing_ok=True)

    def _interface(self,folder,rows,fiches,contours,slopes):
        from donnees_interface import preparer
        config_path=folder/'simulation.json'
        if not config_path.exists():
            config_path.write_bytes((ROOT/'code/filtres.json').read_bytes())
        preparer(folder,rows,fiches,contours,slopes,json.loads(config_path.read_text()))

    def interface(self,version=None):
        version=version or self.active()
        folder=self.version_path(version)
        if not (folder/'interface.json').exists():
            # Migration d'une version antérieure : ne pas y ajouter de données actuelles.
            raise KeyError('Version antérieure sans export interface ; lancer une actualisation')
        payload=immutable_json(str(folder/'interface.json'))
        from donnees_interface import altitudes_repere
        heights=altitudes_repere(tuple(tuple(row[7]) if row[7] else None for row in payload['parcels']))
        # Ne pas muter l'export immuable en cache ni imposer une migration des versions.
        manifest=json.loads((folder/'manifest.json').read_text())
        return dict(payload,actualisation={'mode':manifest.get('mode_actualisation','initiale'),
                    'date':manifest.get('date_activation',manifest.get('date_creation'))},
                    parcels=[row[:9]+[height] for row,height in zip(payload['parcels'],heights)])

    def active(self):
        return json.loads(self.pointer.read_text())['version']

    def version_path(self,version):
        if not re.fullmatch(r'(initiale|application)-[a-f0-9]{32}',version):
            raise KeyError('Version inconnue')
        folder=self.storage/version
        if not (folder/'manifest.json').exists():raise KeyError('Version inconnue')
        return folder

    def _fiches(self,rows,crossings,provenance,cfg,version,slopes_path=None,contours_path=None,patrimoine=None):
        from donnees_interface import voisinage
        neighbors=voisinage(rows,contours_path or self.contours,self.criteria)
        result={}
        for row in rows:
            egrid=row['egrid']
            observation=(patrimoine or {}).get(egrid)
            rules=dict(row)
            if observation:
                for kind,field in (('batiments','notes_batiment_existante_json'),('sites','notes_site_existante_json')):
                    notes=[n for n in observation['notes_'+kind] if n != 0]
                    if notes:
                        old=rules.get(field) or []
                        if isinstance(old,str):old=json.loads(old)
                        rules[field]=list(old)+[n for n in notes if n not in old]
            result[egrid]=dict(egrid=egrid,numero_parcelle=row.get('numero_parcelle'),version=version,
                presente_derniere_collecte=True,zone_dominante=row.get('zone_dominante'),
                classement=self.criteria.evaluate_parcel(rules,cfg,neighbors.get(egrid)),
                patrimoine_geovd=observation,
                contraintes=contraintes(crossings.get(egrid),provenance),
                alertes=(crossings.get(egrid) or {}).get('alertes_json',[]))
        return result

    def fiche(self,egrid,version=None):
        version=version or self.active()
        folder=self.version_path(version)
        fiches=immutable_json(str(folder/'fiches.json'))
        if egrid not in fiches:raise KeyError('EGRID inconnu')
        result=copy.deepcopy(fiches[egrid])
        # Annotations stockées séparément, jamais écrasées par une actualisation.
        annotations=self.storage/'annotations_expert.json'
        result['annotations_expert']=json.loads(annotations.read_text()).get(egrid,{}) if annotations.exists() else {}
        verification=self.storage/'verification_sources.json'
        if verification.exists():
            checked=json.loads(verification.read_text())
            if checked.get('version')==version:
                for field in result['contraintes'].values():
                    source=field.get('source') or {}
                    info=checked.get('sources',{}).get(source.get('id'),{})
                    if info.get('empreinte_contenu_sha256')==source.get('empreinte') and info.get('verifie_utc'):
                        field['date_verification']=info['verifie_utc']
        return result

    def liste(self,version=None,offset=0,limit=50):
        version=version or self.active()
        fiches=immutable_json(str(self.version_path(version)/'fiches.json'))
        ids=sorted(fiches)
        # Les résumés renvoient vers l'unique endpoint de fiche pour Carte et Liste.
        return dict(version=version,total=len(ids),offset=offset,
                    parcelles=[dict(egrid=e,numero_parcelle=fiches[e]['numero_parcelle'],
                                    statut=fiches[e]['classement']['statut_filtrage_criteres']) for e in ids[offset:offset+limit]])

    def status(self,operation=None):
        if operation:
            if not re.fullmatch('[a-f0-9]{32}',operation):raise KeyError('Opération inconnue')
            path=self.storage/'operations'/(operation+'.json')
        else:path=self.storage/'etat_actualisation.json'
        if not path.exists():
            if operation:raise KeyError('Opération inconnue')
            return {'statut':'aucune_operation','version_active':self.active()}
        return json.loads(path.read_text())

    def versions(self):
        result=[];active=self.active()
        for folder in self.storage.iterdir():
            if not folder.is_dir() or not re.fullmatch(r'(initiale|application)-[a-f0-9]{32}',folder.name):continue
            path=folder/'manifest.json'
            if not path.exists():continue
            data=json.loads(path.read_text())
            result.append(dict(version=folder.name,active=folder.name==active,
                date=data.get('date_activation',data.get('date_creation')),
                mode=data.get('mode_actualisation','initiale'),bilan=data.get('bilan')))
        return dict(versions=sorted(result,key=lambda r:r['date'] or '',reverse=True),
                    stockage='temporaire')

    def archive(self,version):
        import zipfile
        folder=self.version_path(version)
        stream=tempfile.TemporaryFile()
        try:
            with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
                for path in sorted(folder.rglob('*')):
                    if path.is_file() and not path.is_symlink():archive.write(path,path.relative_to(folder))
            stream.seek(0)
            return stream
        except Exception:
            stream.close();raise

    def start(self,background=True):
        with self.mutex:
            if self.lock.exists():
                # Le même ID est rendu aux doubles clics, pas une seconde tâche.
                try:owner=json.loads(self.lock.read_text())
                except (ValueError,OSError):owner={}
                operation=owner.get('operation_id') if isinstance(owner,dict) else None
                if operation and re.fullmatch('[a-f0-9]{32}',operation):
                    return {'operation_id':operation,'reutilisee':True}
                raise RuntimeError('Actualisation CLI/initialisation déjà en cours ; consulter etat_actualisation.json')
            operation=uuid4().hex
            try:fd=os.open(self.lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            except FileExistsError:
                raise RuntimeError('Actualisation déjà en cours dans un autre processus')
            os.write(fd,json.dumps({'pid':os.getpid(),'operation_id':operation}).encode());os.close(fd)
            state=OperationState(self.storage,operation)
            try:state.maj(etape='Vérification des sources',version_active=self.active())
            except Exception:
                self.lock.unlink(missing_ok=True);raise
            if background:
                self.thread=threading.Thread(target=self._worker,args=(state,),daemon=False)
                self.thread.start()
            else:self._worker(state)
            return {'operation_id':operation,'reutilisee':False}

    def _worker(self,state):
        previous=self.active()
        state.maj(mode=self.mode_actualisation)
        try:
            with tempfile.TemporaryDirectory(prefix='.candidate-',dir=self.storage) as temp:
                stage=Path(temp)
                # Capturer les entrées, pour ne pas classer avec un fichier modifié en cours de traitement.
                reference=stage/'parcelles.csv';reference.write_bytes(self.reference.read_bytes())
                contours=stage/'contours.json';contours.write_bytes(self.contours.read_bytes())
                config=stage/'criteres.json';config.write_bytes(self.config.read_bytes())
                slope_snapshot=stage/'pentes.csv'
                if self.slopes.exists():slope_snapshot.write_bytes(self.slopes.read_bytes())
                previous_folder=self.version_path(previous)
                old=json.loads((previous_folder/'parcelles.json').read_text())
                patrimoine=None
                if self.base_collector:
                    self.base_collector(stage,state,old)
                    if self.mode_actualisation=='geovd':
                        from patrimoine_geovd import collecter as collecter_patrimoine
                        before_path=previous_folder/'patrimoine_geovd.json'
                        before=json.loads(before_path.read_text()) if before_path.exists() else None
                        patrimoine=collecter_patrimoine(contours,state,before)
                        write_json(stage/'patrimoine_geovd.json',patrimoine)
                    from donnees_interface import derivations
                    derivations(stage,state)
                rows=read_csv(reference);cfg=self.criteria.load_criteria(config)
                destination,report,crossings=export_observations(reference,contours,stage/'croisements',state,self.collector)
                previous_folder=self.version_path(previous)
                if patrimoine:report['sources'].update(patrimoine['sources'])
                incoming={row['egrid']:row for row in rows}
                missing=sorted(set(old)-set(incoming))
                added=sorted(set(incoming)-set(old))
                old_fiches=json.loads((previous_folder/'fiches.json').read_text()) if missing else {}
                # Les collecteurs isolés forment des cycles module/fonctions ; les libérer
                # avant de construire les fiches, sans attendre le seuil du GC.
                missing_rows={e:old[e] for e in missing}
                del old
                immutable_json.cache_clear()
                gc.collect()
                state.maj(etape='Construction des fiches de la version candidate')
                version='application-'+uuid4().hex
                fiches=self._fiches(rows,{r['egrid']:r for r in crossings},report,cfg,version,slope_snapshot,contours,patrimoine['parcelles'] if patrimoine else None)
                for egrid in missing:
                    incoming[egrid]=missing_rows[egrid]
                    fiches[egrid]=copy.deepcopy(old_fiches[egrid]);fiches[egrid]['version']=version
                    fiches[egrid]['presente_derniere_collecte']=False
                    fiches[egrid]['derniere_version_observee']=old_fiches[egrid]['version']
                    fiches[egrid]['contraintes']=contraintes()
                    fiches[egrid]['alertes']=sorted(set(fiches[egrid]['alertes'])|{'absente_derniere_collecte_a_examiner'})
                del old_fiches,missing_rows
                gc.collect()
                if set(fiches)!=set(incoming):raise ValueError('Fiches incomplètes')
                # Contours des parcelles absentes conservés uniquement pour la consultation historique.
                if missing and (previous_folder/'contours.json').exists():
                    current=json.loads(contours.read_text())
                    present_ids={f['attributes'].get('egris_egrid') for f in current['results']}
                    current['results'].extend(f for f in json.loads((previous_folder/'contours.json').read_text())['results']
                                              if f['attributes'].get('egris_egrid') in missing and f['attributes'].get('egris_egrid') not in present_ids)
                    write_json(contours,current)
                state.maj(etape='Préparation de la carte et de la liste')
                self._interface(stage,list(incoming.values()),fiches,contours,slope_snapshot)
                gc.collect()
                identity=dict(reference=sha(reference),contours=sha(contours),regles=sha(config),
                    algorithme=sha(Path(__file__)),fiches=sha(Path(__file__).with_name('fiches_contraintes.py')),
                    observations=sha(Path(__file__).with_name('observations_cantonales.py')),
                    classement=self.classifier_sha,
                    pentes=sha(slope_snapshot) if slope_snapshot.exists() else None,
                    simulation=sha(stage/'simulation.json'),interface=sha(Path(__file__).with_name('donnees_interface.py')),
                    calculs={name:sha(ROOT/'code'/name) for name in ('classification.py','prospection.py','geometrie.py')},
                    collecte=sha(Path(__file__).with_name('collecte_application.py')) if self.base_collector else None,
                    sources={k:{field:info.get(field) for field in ('empreinte_contenu_sha256','empreinte_metadonnees_sha256')} for k,info in report['sources'].items()})
                identity['mode_actualisation']=self.mode_actualisation
                identity['patrimoine_geovd']=patrimoine['empreinte'] if patrimoine else None
                identity['algorithme_patrimoine_geovd']=sha(Path(__file__).with_name('patrimoine_geovd.py')) if patrimoine else None
                fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
                prior=json.loads((previous_folder/'manifest.json').read_text())
                alerts=list(state.data.get('alertes',[]))+[f'{key} : {count} parcelle(s)' for key,count in report['alertes'].items()]
                if missing:alerts.append(f'{len(missing)} parcelle(s) absentes conservées pour examen ; aucun archivage automatique')
                bilan={'parcelles':len(fiches),'ajoutees':len(added),'absentes':len(missing),'croisements':report['bilan']}
                bilan['perimetre']=self.mode_actualisation
                if patrimoine:
                    bilan.update(premiere_observation_geovd=patrimoine['premiere_observation'],
                                 evolutions_notes_geovd=patrimoine['evolutions'])
                if prior.get('empreinte')==fingerprint:
                    write_json(self.storage/'verification_sources.json',{'version':previous,'sources':report['sources']})
                    state.maj(statut='aucun_changement',etape=None,fin_utc=maintenant(),
                              version_active=previous,bilan=bilan,alertes=alerts)
                    return
                manifest=dict(version=version,empreinte=fingerprint,identite=identity,regles=cfg,
                              date_creation=maintenant(),mode_actualisation=self.mode_actualisation,source_croisements=str(destination.relative_to(stage)),
                              bilan=bilan,alertes=alerts,precedente=previous)
                write_json(stage/'fiches.json',fiches)
                del fiches  # Libérer le candidat avant la relecture de contrôle sur Free.
                write_json(stage/'parcelles.json',incoming)
                write_json(stage/'manifest.json',manifest)
                # Relire avant activation ; une erreur conserve le pointeur précédent.
                gc.collect()
                state.maj(etape='Relecture de contrôle')
                verifier_fiches(stage/'fiches.json',set(incoming),version)
                manifest['date_activation']=maintenant()
                write_json(stage/'manifest.json',manifest)
                state.maj(etape='Activation',bilan=bilan,alertes=alerts)
                target=self.storage/version
                os.rename(stage,target)
                write_json(self.pointer,{'version':version})
                state.maj(statut='termine',etape=None,fin_utc=maintenant(),version_active=version,fichier=version)
        except Exception as error:
            state.maj(statut='erreur',etape=None,fin_utc=maintenant(),version_active=self.active(),
                      erreur=f'Actualisation non appliquée : {error}')
        finally:
            self.lock.unlink(missing_ok=True)
