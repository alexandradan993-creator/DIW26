"""Calcule la forme et les retraits ; ne valide pas les règles réglementaires."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pyproj import Transformer
from shapely import transform
from shapely.geometry import shape, mapping

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from geometrie import calculer_forme


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'code/filtres.json')
    parser.add_argument('--output',type=Path,default=ROOT/'data/formes_parcelles')
    args=parser.parse_args()
    config=json.loads(args.config.read_text())['forme']
    paths=[ROOT/'data/parcelles/contours.geojson',ROOT/'data/parcelles/audit_correspondances.json']
    features=json.loads(paths[0].read_text())['features']
    geometries={f['id']:f['geometry'] for f in features}
    audits=json.loads(paths[1].read_text())
    if len(geometries)!=len(features) or len({a['egrid'] for a in audits})!=len(audits):
        raise ValueError('EGRID dupliqués')
    to_m=Transformer.from_crs(4326,2056,always_xy=True).transform
    to_ll=Transformer.from_crs(2056,4326,always_xy=True).transform
    rows=[];envelopes=[]
    for audit in audits:
        row=dict(egrid=audit['egrid'],numero_parcelle=audit['numero_parcelle'],
                 statut_forme='non_calculable',retrait_m=config['retrait_m'],
                 source_hypothese=config['source'])
        flags=[]
        if audit['statut']!='apparie' or audit['egrid'] not in geometries:
            flags.append('contour_absent_ou_invalide')
        else:
            polygon=transform(shape(geometries[audit['egrid']]),to_m,interleaved=False)
            values,envelope=calculer_forme(polygon,config['retrait_m'])
            row.update(values)
            if abs(audit.get('ecart_surface_relatif') or 0)>.01:
                flags.append('ecart_surface_superieur_1pct')
            row['statut_forme']='calcule_a_verifier' if flags else 'calcule'
            if not envelope.is_empty:
                envelopes.append(dict(type='Feature',id=row['egrid'],properties=dict(row),
                                      geometry=mapping(transform(envelope,to_ll,interleaved=False))))
        row['alertes_json']=json.dumps(flags,ensure_ascii=False)
        rows.append(row)
    args.output.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (args.output/'formes_parcelles.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    (args.output/'enveloppes_simulees.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=envelopes),ensure_ascii=False)+'\n')
    report=dict(date_calcul_utc=datetime.now(timezone.utc).isoformat(),hypothese=config,
                parcelles=len(rows),effectifs=dict(Counter(r['statut_forme'] for r in rows)),
                enveloppes_vides=sum(r.get('surface_apres_retrait_m2')==0 for r in rows),
                sources_sha256={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths,args.config]},
                limite='Simulation avec retrait uniforme, pas une règle réglementaire vérifiée. Pas de contrainte arbres, routes, eau, forêt ni de placement des bâtiments.')
    (args.output/'resume.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
