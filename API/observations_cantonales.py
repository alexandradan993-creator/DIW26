"""Adaptateur métier séparé : réutilise l'exporteur sans modifier son code."""
import csv
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from shapely.ops import unary_union
import croisements_contraintes as existing


class DetailedLayer(existing.SpatialLayer):
    def __init__(self,bundle,field=None,coverage=None):
        super().__init__(bundle,field,coverage)
        renderer=bundle['metadata'].get('drawingInfo',{}).get('renderer',{})
        if renderer.get('field1')==field:
            self.labels.update({str(v['value']):v['label'] for v in renderer.get('uniqueValueInfos',[])})
        if bundle['metadata'].get('name')=='vd.carte_synthetique_danger_naturel':
            if field!='DEG_DN_PREP' or self.labels.get('W')!='Danger nul':
                raise ValueError('Schéma/légende danger modifié : vérifier avant activation')
            if coverage is None:
                self.coverage=unary_union([g for g,f in zip(self.geometries,bundle['features'])
                                          if f['attributes'].get(field) in ('R','B','J','H','W')])

    def intersect(self,polygon):
        result=super().intersect(polygon)
        if self.bundle['metadata'].get('name')=='vd.carte_synthetique_danger_naturel':
            risk=[polygon.intersection(self.geometries[int(i)]) for i in self.tree.query(polygon,predicate='intersects')
                  if self.bundle['features'][int(i)]['attributes'].get(self.field) in ('R','B','J','H')]
            result['surface_danger_identifie_m2']=unary_union(risk).area if risk else 0.
            result['part_danger_identifie_pct']=min(100.,100*result['surface_danger_identifie_m2']/polygon.area)
        return result


def danger_state(cross):
    codes={c['code'] for c in cross['classes']}
    if codes & {'R','B','J','H'}:
        return 'danger_identifie'
    if (codes=={'W'} and cross['statut_couverture']=='complete'
            and all(o['valeur_metier']=='W' for o in cross['objets'])):
        return 'danger_nul_zone_etudiee'
    return 'a_verifier'


def export_observations(reference,contours,output,etat,collect=None):
    # Module isolé : aucune mutation du module réutilisé par le CLI du collègue.
    spec=importlib.util.spec_from_file_location('_exporteur_isole',Path(existing.__file__))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.SpatialLayer=DetailedLayer
    from suivi_collecte import SuiviCollecte
    transport=SuiviCollecte(etat)
    def request(url, params=None):
        reply=json.loads(transport(url,params,post=params is not None))
        if not isinstance(reply,dict) or "error" in reply:
            raise ValueError("Réponse ArcGIS cantonale invalide")
        return reply
    fetched={}
    def checked_collect(layer,bbox):
        bundle=collect(layer,bbox) if collect else existing.collect_layer(layer,bbox,request=request)
        expected={404:'vd.perimetre_fonde_sur_isos',422:'vd.carte_synthetique_danger_naturel'}[layer]
        if bundle['metadata'].get('name')!=expected:
            raise ValueError('La source a changé de couche : '+str(layer))
        fetched[layer]=bundle
        return bundle
    destination,report=module.export_crossings(reference,contours,output,etat,
        field_site='NOM_SITE',field_danger='DEG_DN_PREP',collect=checked_collect)
    path=destination/'croisements.csv'
    with path.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        for key in ('isos_json','dangers_json','alertes_json'):
            row[key]=json.loads(row[key]) if row[key] else None
        if row['isos_json'] and not row['isos_json']['intersection_detectee']:
            row['isos_etat']='aucun_recouvrement_couche_consultee'
        if row['dangers_json']:
            row['dangers_etat']=danger_state(row['dangers_json'])
            if any(c['code'] in ('X','Z') for c in row['dangers_json']['classes']):
                row['alertes_json'].append('danger_information_manquante_ou_revision')
        row['danger_bloquant']=None
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
    report['bilan']={name:dict(Counter(r[name+'_etat'] for r in rows)) for name in ('isos','dangers')}
    report['alertes']=dict(Counter(a for r in rows for a in r['alertes_json']))
    report['semantique_dangers']='Légende officielle 422 : R/B/J/H dangers ; W nul étudié ; X/Z inconnue/révision. Aucune règle bloquante déduite.'
    report['fichiers_sha256']['croisements.csv']=hashlib.sha256(path.read_bytes()).hexdigest()
    (destination/'provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return destination,report,rows
