"""Export versionné des intersections cantonales, sans activation applicative.

Les champs métier et la couverture d'étude ne sont jamais déduits d'une emprise
de service ou du seul nom d'un attribut. Les réponses brutes sont conservées.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
from uuid import uuid4

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

BASE = 'https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer'
LAYERS = {'isos':404, 'dangers':422}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def request_json(url, params=None):
    data=urllib.parse.urlencode(params).encode() if params else None
    req=urllib.request.Request(url,data=data,headers={'User-Agent':'DIW26-croisements/1.0'})
    with urllib.request.urlopen(req,timeout=90) as response:
        result=json.load(response)
    if not isinstance(result,dict) or 'error' in result:
        raise ValueError(f'Réponse ArcGIS invalide : {url} : {result.get("error") if isinstance(result,dict) else "non objet"}')
    return result


def polygon_esri(geometry):
    """Anneaux imbriqués/disjoints ; toute géométrie invalide est refusée."""
    if not geometry or not geometry.get('rings'):
        raise ValueError('Géométrie surfacique absente')
    result=None
    for ring in geometry['rings']:
        part=Polygon([(p[0],p[1]) for p in ring])
        if not part.is_valid or part.is_empty or part.area<=0:
            raise ValueError('Anneau invalide ; aucune réparation automatique')
        result=part if result is None else result.symmetric_difference(part)
    if result.is_empty or not result.is_valid or result.geom_type not in ('Polygon','MultiPolygon'):
        raise ValueError('Contour invalide')
    return result


def collect_layer(layer_id, bbox, request=request_json):
    """Inventaire des IDs puis lots récursifs ; aucun lot tronqué n'est accepté."""
    url=f'{BASE}/{layer_id}'
    verified=now()
    metadata=request(url+'?f=json')
    if metadata.get('geometryType')!='esriGeometryPolygon':
        raise ValueError('La couche doit contenir des polygones : '+url)
    oid=metadata.get('objectIdField') or next((f['name'] for f in metadata.get('fields',[]) if f['type']=='esriFieldTypeOID'),None)
    if not oid:
        raise ValueError('Identifiant objet absent du schéma')
    spatial={'f':'json','where':'1=1','geometry':','.join(map(str,bbox)),
             'geometryType':'esriGeometryEnvelope','inSR':2056,
             'spatialRel':'esriSpatialRelIntersects'}
    inventory=request(url+'/query',dict(spatial,returnIdsOnly='true'))
    ids=inventory.get('objectIds')
    if ids is None or inventory.get('exceededTransferLimit') or len(ids)!=len(set(ids)):
        raise ValueError('Inventaire des identifiants incomplet ou dupliqué')
    expected=sorted(ids)
    count=request(url+'/query',dict(spatial,returnCountOnly='true')).get('count')
    if count!=len(expected):
        raise ValueError('Le nombre annoncé diffère de l’inventaire ; source mouvante ou collecte incomplète')
    calls=0

    def batch(wanted):
        nonlocal calls
        calls+=1
        reply=request(url+'/query',{'f':'json','objectIds':','.join(map(str,wanted)),
                                   'outFields':'*','returnGeometry':'true','outSR':2056})
        if reply.get('spatialReference',{}).get('latestWkid',reply.get('spatialReference',{}).get('wkid'))!=2056:
            raise ValueError('Réponse dans un CRS inattendu')
        features=reply.get('features')
        if not isinstance(features,list):
            raise ValueError('Liste d’entités absente')
        actual=[f.get('attributes',{}).get(oid) for f in features]
        if len(actual)!=len(set(actual)) or not set(actual)<=set(wanted):
            raise ValueError('Objets dupliqués ou inattendus')
        if reply.get('exceededTransferLimit') or set(actual)!=set(wanted):
            if len(wanted)<=1:
                raise ValueError('Objet manquant ou réponse tronquée : '+str(wanted))
            middle=len(wanted)//2
            return batch(wanted[:middle])+batch(wanted[middle:])
        return features

    size=max(1,min(200,int(metadata.get('maxRecordCount') or 200)))
    features=[]
    for start in range(0,len(expected),size):
        features.extend(batch(expected[start:start+size]))
    # Contrôle de l'inventaire après téléchargement ; on ne mélange pas deux lots.
    after=request(url+'/query',dict(spatial,returnIdsOnly='true'))
    if after.get('exceededTransferLimit') or sorted(after.get('objectIds') or [])!=expected:
        raise ValueError('L’inventaire a changé pendant le téléchargement')
    after_metadata=request(url+'?f=json')
    if metadata.get('editingInfo')!=after_metadata.get('editingInfo'):
        raise ValueError('La date d’édition a changé pendant le téléchargement')
    # Valider toutes les géométries sources avant publication, pas les réparer.
    for feature in features:
        polygon_esri(feature.get('geometry'))
    features.sort(key=lambda feature:feature['attributes'][oid])
    return dict(metadata=metadata,features=features,provenance=dict(
        url=url,verifie_utc=verified,collecte_fin_utc=now(),objets=len(features),
        version_donnee=None,date_donnee=None,
        edition_declaree=metadata.get('editingInfo'),
        version_logiciel_arcgis=metadata.get('currentVersion'),
        empreinte_metadonnees_sha256=digest(metadata),empreinte_contenu_sha256=digest(features),
        ids_sha256=digest(expected),requêtes_lots=calls,completude='ids_et_comptage_controles',
        bbox_mn95=list(bbox),attribution=metadata.get('copyrightText'),
        avertissement='La date de collecte et la version du logiciel ne sont pas la date ou la version de la donnée ; licence et couverture d’étude à vérifier.'))


class SpatialLayer:
    def __init__(self,bundle,field=None,coverage=None):
        self.bundle=bundle
        self.field=field
        if field and field not in {f['name'] for f in bundle['metadata'].get('fields',[])}:
            raise ValueError('Champ métier absent des métadonnées : '+field)
        self.geometries=[polygon_esri(f['geometry']) for f in bundle['features']]
        self.tree=STRtree(self.geometries)
        self.coverage=coverage
        field_info=next((f for f in bundle['metadata'].get('fields',[]) if f['name']==field),{})
        self.labels={str(v['code']):v['name'] for v in (field_info.get('domain') or {}).get('codedValues',[])}

    def intersect(self,polygon):
        intersections=[];details=[];classes={}
        for index in self.tree.query(polygon,predicate='intersects'):
            feature=self.bundle['features'][int(index)]
            part=polygon.intersection(self.geometries[int(index)])
            if part.area<=0:
                continue  # simple contact de bord : pas de surface recouverte
            attrs=feature['attributes']
            value=attrs.get(self.field) if self.field else None
            details.append(dict(valeur_metier=value,attributs=attrs,surface_m2=part.area,
                                part_parcelle_pct=100*part.area/polygon.area))
            intersections.append(part)
            if value is not None:
                classes.setdefault(str(value),[]).append(part)
        area=unary_union(intersections).area if intersections else 0.
        covered=None if self.coverage is None else min(100.,100*polygon.intersection(self.coverage).area/polygon.area)
        coverage_state='inconnue' if covered is None else 'complete' if covered>=99.999999 else 'partielle' if covered>0 else 'hors_couverture'
        return dict(intersection_detectee=bool(intersections),surface_union_m2=area,
                    part_parcelle_pct=min(100.,100*area/polygon.area),
                    couverture_etude_pct=covered,statut_couverture=coverage_state,
                    classes=[dict(code=k,libelle=self.labels.get(k),surface_union_m2=unary_union(v).area,
                                  part_parcelle_pct=min(100.,100*unary_union(v).area/polygon.area)) for k,v in sorted(classes.items())],
                    objets=details)


def load_coverage(path):
    if path is None:
        return None
    source=json.loads(path.read_text())
    # Un périmètre d'étude doit être sourcé explicitement, pas une simple bbox.
    if source.get('sr')!=2056 or not source.get('source') or not source.get('date_donnee'):
        raise ValueError('Couverture : sr=2056, source et date_donnee requis')
    return unary_union([polygon_esri(f['geometry']) for f in source['features']])


def export_crossings(reference, contours, output, etat, field_site=None, field_danger=None,
                     coverage_isos=None, coverage_dangers=None, collect=collect_layer):
    with reference.open(encoding='utf-8-sig',newline='') as stream:
        source_rows=list(csv.DictReader(stream))
    ids=[r.get('egrid') for r in source_rows]
    if not ids or any(not e for e in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Référence vide ou EGRID absents/dupliqués')
    raw=json.loads(contours.read_text())
    if raw.get('sr')!=2056:
        raise ValueError('Contours sources attendus en MN95 sr=2056')
    geometries={};geometry_errors={}
    for feature in raw['results']:
        egrid=feature['attributes'].get('egris_egrid')
        if egrid in geometries or egrid in geometry_errors:
            raise ValueError('Contour EGRID dupliqué : '+str(egrid))
        try:
            geometries[egrid]=polygon_esri(feature.get('geometry'))
        except ValueError as error:
            geometry_errors[egrid]=str(error)
    relevant=[geometries[e] for e in ids if e in geometries]
    if not relevant:
        raise ValueError('Aucun contour valide : aucune version produite')
    bbox=unary_union(relevant).bounds
    bundles={};layers={}
    etat.maj(etape='Récupération')
    for name,layer_id in LAYERS.items():
        bundle=collect(layer_id,bbox)
        bundles[name]=bundle
        layers[name]=SpatialLayer(bundle,field_site if name=='isos' else field_danger,
                                   load_coverage(coverage_isos if name=='isos' else coverage_dangers))
    etat.maj(etape='Contrôle',sources={k:v['provenance'] for k,v in bundles.items()})
    rows=[]
    etat.maj(etape='Calcul des attributs')
    for source in source_rows:
        egrid=source['egrid'];polygon=geometries.get(egrid)
        row=dict(egrid=egrid,numero_parcelle=source.get('numero_parcelle'),
                 isos_etat='a_verifier',dangers_etat='a_verifier',danger_bloquant=None)
        alerts=[]
        if polygon is None:
            alerts.append('contour_absent_ou_invalide')
            row.update(isos_json=None,dangers_json=None)
        else:
            for name,layer in layers.items():
                cross=layer.intersect(polygon)
                if cross['intersection_detectee']:
                    state='dans_perimetre' if name=='isos' else 'danger_identifie'
                elif cross['statut_couverture']=='complete':
                    state='hors_perimetres_consultes' if name=='isos' else 'aucun_danger_identifie_dans_donnees_consultees'
                else:
                    state='a_verifier'
                row[name+'_etat']=state;row[name+'_json']=cross
                if cross['statut_couverture']!='complete':
                    alerts.append(name+'_couverture_'+cross['statut_couverture'])
                if cross['intersection_detectee'] and not layer.field:
                    alerts.append(name+'_champ_metier_a_identifier')
                elif any(obj['valeur_metier'] is None for obj in cross['objets']):
                    alerts.append(name+'_valeur_metier_absente')
            declared=source.get('surface_geometrique_m2')
            try:
                difference=abs(float(declared)-polygon.area)/polygon.area
                if difference>.01:
                    alerts.append('ecart_surface_superieur_1pct')
            except (ValueError,TypeError):
                alerts.append('surface_reference_inconnue')
        row['alertes_json']=alerts
        rows.append(row)
    manifest=dict(version_export='croisements-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8],
                  date_calcul_utc=now(),parcelles=len(rows),sources={k:v['provenance'] for k,v in bundles.items()},
                  mapping=dict(site_isos=field_site,classe_danger=field_danger),
                  entrees_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [reference,contours,coverage_isos,coverage_dangers] if p},
                  bilan={name:dict(Counter(r[name+'_etat'] for r in rows)) for name in LAYERS},
                  alertes=dict(Counter(a for row in rows for a in row['alertes_json'])),
                  activation_automatique=False,classement_recalcule=False,
                  limites='Export à contrôler avant intégration. Absence de couverture sourcée = inconnu. Présence de danger distincte du caractère bloquant, non évalué. Aucune activation ni décision expert modifiée.')
    output.mkdir(parents=True,exist_ok=True)
    etat.maj(etape='Écriture')
    with tempfile.TemporaryDirectory(prefix='.croisements-',dir=output) as temp:
        stage=Path(temp)/'export';stage.mkdir()
        with (stage/'croisements.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader()
            writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
        for name,bundle in bundles.items():
            (stage/(name+'_source.json')).write_text(json.dumps(bundle,ensure_ascii=False)+'\n')
        manifest['fichiers_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
        (stage/'provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        destination=output/manifest['version_export']
        os.rename(stage,destination)
    return destination,manifest
