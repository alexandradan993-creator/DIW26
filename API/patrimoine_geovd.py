"""Observations cantonales séparées du patrimoine historique SIGIP."""
import hashlib
import json
from pathlib import Path

from shapely.strtree import STRtree
from croisements_contraintes import collect_layer, polygon_esri
from suivi_collecte import SuiviCollecte

LAYERS={'batiments':(316,'vd.batiment_recense'),'sites':(402,'vd.site')}


def collecter(contours,etat,previous=None,collect=None):
    raw=json.loads(Path(contours).read_text())
    if raw.get('sr')!=2056:raise ValueError('Contours patrimoniaux hors MN95')
    polygons={}
    for feature in raw['results']:
        egrid=feature['attributes'].get('egris_egrid')
        if not egrid or egrid in polygons:raise ValueError('EGRID patrimonial absent ou dupliqué')
        try:polygons[egrid]=polygon_esri(feature.get('geometry'))
        except ValueError:polygons[egrid]=None
    valid=[g for g in polygons.values() if g is not None]
    if not valid:raise ValueError('Aucun contour patrimonial exploitable')
    bbox=(min(g.bounds[0] for g in valid),min(g.bounds[1] for g in valid),
          max(g.bounds[2] for g in valid),max(g.bounds[3] for g in valid))
    transport=SuiviCollecte(etat)
    def request(url,params=None):
        data=json.loads(transport(url,params,post=params is not None))
        if not isinstance(data,dict) or 'error' in data:raise ValueError('Réponse patrimoniale GEO.vd invalide')
        return data
    parcels={e:dict(notes_batiments=[],notes_sites=[],objets=[],contour_exploitable=g is not None)
             for e,g in polygons.items()}
    sources={}
    for kind,(layer,expected) in LAYERS.items():
        bundle=collect(layer,bbox) if collect else collect_layer(layer,bbox,request=request)
        metadata=bundle['metadata'];fields={f['name'] for f in metadata.get('fields',[])}
        if metadata.get('name')!=expected or 'NOTE_CARTO' not in fields:
            raise ValueError(f'Schéma du patrimoine GEO.vd modifié : {layer}')
        sources['geovd_'+str(layer)]=bundle['provenance']
        geometries=[polygon_esri(f['geometry']) for f in bundle['features']]
        tree=STRtree(geometries)
        for egrid,polygon in polygons.items():
            if polygon is None:continue
            entry=parcels[egrid]
            for index in tree.query(polygon,predicate='intersects'):
                i=int(index)
                if polygon.intersection(geometries[i]).area<.1:continue
                attrs=bundle['features'][i]['attributes']
                notes=[]
                for key in ('NOTE_CARTO','NOTE_DETAIL'):
                    value=attrs.get(key)
                    if value is not None:
                        if isinstance(value,bool) or str(value) not in {str(n) for n in range(0,8)}:
                            raise ValueError(f'Note patrimoniale inconnue GEO.vd : couche {layer}, {key}={value!r}')
                        # Code officiel 0 : objet recensé mais pas évalué (légende GEO.vd).
                        # Conservé comme observation, jamais comme preuve d’absence de protection.
                        notes.append(int(value))
                entry['notes_'+kind].extend(notes)
                entry['objets'].append(dict(couche=layer,id=attrs.get('ID_OBJET_RECENSE'),
                    note_carto=attrs.get('NOTE_CARTO'),note_detail=attrs.get('NOTE_DETAIL'),
                    fiche=attrs.get('FICHE'),url=attrs.get('URL_RECENS')))
    before=(previous or {}).get('parcelles',{})
    for egrid,entry in parcels.items():
        for kind in ('batiments','sites'):entry['notes_'+kind]=sorted(set(entry['notes_'+kind]))
        entry['verifie_utc']=max(s['verifie_utc'] for s in sources.values())
        prior=before.get(egrid)
        entry['precedentes']=({k:prior.get(k) for k in ('notes_batiments','notes_sites')} if prior else None)
        entry['evolution_notes']=(any(entry[k]!=prior.get(k) for k in ('notes_batiments','notes_sites')) if prior else None)
    fingerprint=hashlib.sha256(json.dumps({k:v['empreinte_contenu_sha256'] for k,v in sources.items()},sort_keys=True).encode()).hexdigest()
    return dict(parcelles=parcels,sources=sources,empreinte=fingerprint,
                premiere_observation=not bool(before),
                evolutions=sum(p['evolution_notes'] is True for p in parcels.values()))
