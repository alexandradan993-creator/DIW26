"""Actualisation serveur et versions immuables, sans modifier les scripts existants."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    ids=[r.get('egrid') for r in rows]
    if not ids or any(not e for e in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Base vide ou EGRID manquants/dupliqués')
    return rows


def write_json(path,value):
    ecrire_atomique(path,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


@lru_cache(maxsize=4)
def immutable_json(path):
    return json.loads(Path(path).read_text())


class OperationState(Etat):
    def __init__(self,folder,operation):
        super().__init__(folder)
        self.folder=folder
        self.data.update(operation_id=operation,mode='contraintes')

    def maj(self,**values):
        super().maj(**values)
        history=self.folder/'operations';history.mkdir(exist_ok=True)
        write_json(history/(self.data['operation_id']+'.json'),self.data)


class UpdateService:
    def __init__(self,storage=None,reference=None,contours=None,config=None,slopes=None,collector=None):
        self.storage=Path(storage or ROOT/'API/versions')
        self.reference=Path(reference or ROOT/'pully_parcelles.csv')
        self.contours=Path(contours or ROOT/'data/parcelles/source_esri_lv95.json')
        self.config=Path(config or ROOT/'code/criteres.json')
        self.slopes=Path(slopes or ROOT/'data/pentes_parcelles/pentes_parcelles.csv')
        self.collector=collector
        self.storage.mkdir(parents=True,exist_ok=True)
        self.pointer=self.storage/'version_active.json'
        self.lock=self.storage/'actualisation.lock'
        self.mutex=threading.Lock()
        self.thread=None
        spec=importlib.util.spec_from_file_location('_criteres_fiches',ROOT/'code/criteres_category.py')
        self.criteria=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.criteria)
        self.classifier_sha=sha(ROOT/'code/criteres_category.py')
        self._initialise()
        self._recover_interrupted()

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
            fiches=self._fiches(rows,{}, {},cfg,version)
            write_json(folder/'fiches.json',fiches)
            write_json(folder/'parcelles.json',{r['egrid']:r for r in rows})
            write_json(folder/'manifest.json',dict(version=version,empreinte=None,
                mode='base_initiale_contraintes_inconnues',regles=cfg,date_creation=maintenant()))
            write_json(self.pointer,{'version':version})
        finally:
            self.lock.unlink(missing_ok=True)

    def active(self):
        return json.loads(self.pointer.read_text())['version']

    def version_path(self,version):
        if not re.fullmatch(r'(initiale|application)-[a-f0-9]{32}',version):
            raise KeyError('Version inconnue')
        folder=self.storage/version
        if not (folder/'manifest.json').exists():raise KeyError('Version inconnue')
        return folder

    def _fiches(self,rows,crossings,provenance,cfg,version,slopes_path=None):
        slopes={}
        slopes_path=slopes_path or self.slopes
        if slopes_path.exists():
            with slopes_path.open(encoding='utf-8-sig',newline='') as stream:
                for row in csv.DictReader(stream):
                    if not row.get('egrid') or row['egrid'] in slopes:
                        raise ValueError('EGRID pente absent/dupliqué')
                    slopes[row['egrid']]=row
        result={}
        for row in rows:
            egrid=row['egrid']
            result[egrid]=dict(egrid=egrid,numero_parcelle=row.get('numero_parcelle'),version=version,
                presente_derniere_collecte=True,zone_dominante=row.get('zone_dominante'),
                classement=self.criteria.evaluate_parcel(row,cfg,slopes.get(egrid)),
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
        try:
            with tempfile.TemporaryDirectory(prefix='.candidate-',dir=self.storage) as temp:
                stage=Path(temp)
                # Capturer les entrées, pour ne pas classer avec un fichier modifié en cours de traitement.
                reference=stage/'parcelles.csv';reference.write_bytes(self.reference.read_bytes())
                contours=stage/'contours.json';contours.write_bytes(self.contours.read_bytes())
                config=stage/'criteres.json';config.write_bytes(self.config.read_bytes())
                slope_snapshot=stage/'pentes.csv'
                if self.slopes.exists():slope_snapshot.write_bytes(self.slopes.read_bytes())
                rows=read_csv(reference);cfg=self.criteria.load_criteria(config)
                destination,report,crossings=export_observations(reference,contours,stage/'croisements',state,self.collector)
                previous_folder=self.version_path(previous)
                old=json.loads((previous_folder/'parcelles.json').read_text())
                old_fiches=json.loads((previous_folder/'fiches.json').read_text())
                incoming={row['egrid']:row for row in rows}
                missing=sorted(set(old)-set(incoming))
                added=sorted(set(incoming)-set(old))
                state.maj(etape='Validation de la version candidate')
                version='application-'+uuid4().hex
                fiches=self._fiches(rows,{r['egrid']:r for r in crossings},report,cfg,version,slope_snapshot)
                for egrid in missing:
                    incoming[egrid]=old[egrid]
                    fiches[egrid]=copy.deepcopy(old_fiches[egrid]);fiches[egrid]['version']=version
                    fiches[egrid]['presente_derniere_collecte']=False
                    fiches[egrid]['derniere_version_observee']=old_fiches[egrid]['version']
                    fiches[egrid]['contraintes']=contraintes()
                    fiches[egrid]['alertes']=sorted(set(fiches[egrid]['alertes'])|{'absente_derniere_collecte_a_examiner'})
                if set(fiches)!=set(incoming):raise ValueError('Fiches incomplètes')
                identity=dict(reference=sha(reference),contours=sha(contours),regles=sha(config),
                    algorithme=sha(Path(__file__)),fiches=sha(Path(__file__).with_name('fiches_contraintes.py')),
                    observations=sha(Path(__file__).with_name('observations_cantonales.py')),
                    classement=self.classifier_sha,
                    pentes=sha(slope_snapshot) if slope_snapshot.exists() else None,
                    sources={k:{field:info.get(field) for field in ('empreinte_contenu_sha256','empreinte_metadonnees_sha256')} for k,info in report['sources'].items()})
                fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
                prior=json.loads((previous_folder/'manifest.json').read_text())
                alerts=[f'{key} : {count} parcelle(s)' for key,count in report['alertes'].items()]
                if missing:alerts.append(f'{len(missing)} parcelle(s) absentes conservées pour examen ; aucun archivage automatique')
                bilan={'parcelles':len(fiches),'ajoutees':len(added),'absentes':len(missing),'croisements':report['bilan']}
                if prior.get('empreinte')==fingerprint:
                    write_json(self.storage/'verification_sources.json',{'version':previous,'sources':report['sources']})
                    state.maj(statut='aucun_changement',etape=None,fin_utc=maintenant(),
                              version_active=previous,bilan=bilan,alertes=alerts)
                    return
                manifest=dict(version=version,empreinte=fingerprint,identite=identity,regles=cfg,
                              date_creation=maintenant(),source_croisements=str(destination.relative_to(stage)),
                              bilan=bilan,alertes=alerts,precedente=previous)
                write_json(stage/'fiches.json',fiches);write_json(stage/'parcelles.json',incoming)
                write_json(stage/'manifest.json',manifest)
                # Relire avant activation ; une erreur conserve le pointeur précédent.
                verified=json.loads((stage/'fiches.json').read_text())
                if set(verified)!=set(incoming):raise ValueError('Version candidate incohérente')
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
