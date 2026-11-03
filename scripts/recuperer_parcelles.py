"""Extraction CadastralWebMap par EGRID, sans modifier le CSV ni le pipeline.

Depuis la racine : python scripts/recuperer_parcelles.py
Dépendances : shapely, pyproj (voir requirements-parcelles.txt).
"""
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from shapely.ops import transform
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/parcelles'
LAYER = 'ch.kantone.cadastralwebmap-farbe'
BASE = 'https://api3.geo.admin.ch/rest/services/api/MapServer/'


def request(endpoint, **parameters):
    url = BASE + endpoint + '?' + urlencode(parameters)
    with urlopen(url, timeout=90) as response:
        result = json.load(response)
    if 'error' in result or 'results' not in result:
        raise ValueError(f'Réponse inattendue : {url}')
    return result['results']


def rectangle(bounds):
    return request('identify', geometry=','.join(map(str, bounds)),
                   geometryType='esriGeometryEnvelope', sr=2056,
                   layers='all:' + LAYER, tolerance=0, returnGeometry='true', limit=200)


def exact(egrid):
    return request('find', layer=LAYER, searchText=egrid, searchField='egris_egrid',
                   contains='false', returnGeometry='true', sr=2056)


def main():
    with (ROOT / 'pully_parcelles.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {row['egrid']: row for row in rows}
    if len(expected) != len(rows):
        raise ValueError('EGRID source dupliqué')
    found = {}
    requests = 0

    def retain(objects):
        for obj in objects:
            egrid = obj.get('attributes', {}).get('egris_egrid')
            if egrid in expected:
                found.setdefault(egrid, {})[str(obj['featureId'])] = obj

    # Découpage adaptatif : toute réponse au plafond est subdivisée.
    pending = [(2538000, 1149000, 2544000, 1157000)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        while pending:
            current, pending = pending, []
            for bounds, objects in zip(current, pool.map(rectangle, current)):
                requests += 1
                retain(objects)
                if len(objects) >= 200:
                    x0, y0, x1, y1 = bounds
                    if min(x1-x0, y1-y0) < 20:
                        raise ValueError('Réponse potentiellement tronquée même après subdivision')
                    xm, ym = (x0+x1)/2, (y0+y1)/2
                    pending.extend([(x0,y0,xm,ym),(xm,y0,x1,ym),
                                    (x0,ym,xm,y1),(xm,ym,x1,y1)])
            print('Requêtes', requests, 'EGRID trouvés', len(found), flush=True)
        missing = sorted(set(expected)-set(found))
        for objects in pool.map(exact, missing):
            requests += 1
            retain(objects)

    converter = Transformer.from_crs(2056, 4326, always_xy=True).transform
    features, audit, raw = [], [], []
    for egrid, row in expected.items():
        objects = list(found.get(egrid, {}).values())
        record = {'egrid':egrid, 'numero_parcelle':row['numero_parcelle'],
                  'genre_parcelle':row['genre_parcelle'], 'nombre_objets':len(objects)}
        if len(objects) != 1:
            record['statut'] = 'absent' if not objects else 'plusieurs_objets_a_verifier'
            audit.append(record)
            continue
        obj = objects[0]
        raw.append(obj)
        rings = obj.get('geometry', {}).get('rings', [])
        polygon = None
        try:
            # Les anneaux ESRI peuvent inclure des trous et des parties disjointes.
            # XOR conserve ces relations indépendamment de leur orientation.
            for ring in rings:
                part = Polygon(ring)
                if not part.is_valid:
                    raise ValueError(explain_validity(part))
                polygon = part if polygon is None else polygon.symmetric_difference(part)
            if polygon is None or polygon.is_empty or not polygon.is_valid:
                raise ValueError('Géométrie absente, vide ou invalide')
            if polygon.geom_type not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Géométrie non surfacique')
        except ValueError as error:
            record.update(statut='geometrie_a_verifier', detail=str(error))
            audit.append(record)
            continue
        attributes = obj['attributes']
        source_area = float(row['surface_geometrique_m2'])
        record.update(statut='apparie', numero_service=str(attributes.get('number')),
                      numero_concordant=str(attributes.get('number'))==row['numero_parcelle'],
                      surface_csv_m2=source_area, surface_contour_m2=polygon.area,
                      ecart_surface_m2=polygon.area-source_area,
                      ecart_surface_relatif=(polygon.area-source_area)/source_area if source_area else None,
                      bounds_lv95=list(polygon.bounds))
        features.append({'type':'Feature', 'id':egrid,
                         'properties':dict(record, source=LAYER, feature_id=obj['featureId']),
                         'geometry':mapping(transform(converter, polygon))})
        audit.append(record)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in [
        ('contours.geojson', {'type':'FeatureCollection','features':features}),
        ('source_esri_lv95.json', {'layer':LAYER,'sr':2056,'results':raw}),
        ('audit_correspondances.json', audit),
    ]:
        (OUT/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    report = {'date_extraction_utc':datetime.now(timezone.utc).isoformat(),
              'source':BASE+LAYER, 'source_csv_sha256':hashlib.sha256((ROOT/'pully_parcelles.csv').read_bytes()).hexdigest(),
              'parcelles_csv':len(rows),'contours_valides':len(features),
              'requêtes':requests,'non_apparies':[r for r in audit if r['statut']!='apparie'],
              'numeros_divergents':[r['egrid'] for r in audit if r.get('numero_concordant') is False],
              'ecarts_surface_superieurs_1pct':[r['egrid'] for r in audit if abs(r.get('ecart_surface_relatif') or 0)>0.01],
              'limite':'Contours du service cartographique, non substituables à un extrait officiel. Aucun rapprochement approximatif ni réparation automatique.'}
    (OUT/'resume.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__':
    main()
