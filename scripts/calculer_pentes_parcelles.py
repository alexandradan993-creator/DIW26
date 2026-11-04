import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask, geometry_window
from rasterio.errors import WindowError
from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]

def statistics(dataset, polygon):
    extent = box(*dataset.bounds)
    coverage = min(100.0, 100 * polygon.intersection(extent).area / polygon.area)
    result = dict(couverture_emprise_raster_pct=coverage, pixels_interieurs=0,
                  pixels_valides=0, pixels_nodata=0, part_pixels_valides_pct=None,
                  pente_moyenne_degres=None, pente_mediane_degres=None,
                  pente_p90_degres=None, pente_max_degres=None,
                  pente_moyenne_pct=None, pente_mediane_pct=None,
                  pente_p90_pct=None, pente_max_pct=None,
                  part_pixels_pente_inf_10pct=None,
                  part_pixels_pente_10_a_25pct=None,
                  part_pixels_pente_sup_25pct=None)
    if not polygon.intersects(extent):
        return result
    try:
        window = geometry_window(dataset, [mapping(polygon)])
    except WindowError:
        return result
    values = dataset.read(1, window=window, masked=True)
    inside = geometry_mask([mapping(polygon)], out_shape=values.shape,
                           transform=dataset.window_transform(window),
                           invert=True, all_touched=False)
    valid = inside & ~np.ma.getmaskarray(values) & np.isfinite(values.data)
    n, count = int(inside.sum()), int(valid.sum())
    result.update(pixels_interieurs=n, pixels_valides=count, pixels_nodata=n-count,
                  part_pixels_valides_pct=100 * count/n if n else None)
    if not count:
        return result
    degrees = values.data[valid].astype('float64')
    if np.any((degrees < 0) | (degrees >= 90)):
        raise ValueError('Pentes source hors intervalle [0, 90[ degrés')
    percent = 100 * np.tan(np.radians(degrees))
    for suffix, samples in [('degres', degrees), ('pct', percent)]:
        result.update({
            'pente_moyenne_'+suffix:float(np.mean(samples)),
            'pente_mediane_'+suffix:float(np.median(samples)),
            'pente_p90_'+suffix:float(np.percentile(samples,90)),
            'pente_max_'+suffix:float(np.max(samples)),
        })
    low = degrees < np.degrees(np.arctan(0.10))
    high = degrees > np.degrees(np.arctan(0.25))
    result.update(part_pixels_pente_inf_10pct=100*float(np.mean(low)),
                  part_pixels_pente_10_a_25pct=100*float(np.mean(~low & ~high)),
                  part_pixels_pente_sup_25pct=100*float(np.mean(high)))
    return result


def main():
    csv_path = ROOT/'pully_parcelles.csv'
    geometry_path = ROOT/'data/parcelles/contours.geojson'
    audit_path = ROOT/'data/parcelles/audit_correspondances.json'
    raster_path = ROOT/'data/terrain/pente_degres_2m.tif'
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    features = json.loads(geometry_path.read_text())['features']
    geometries = {f['id']: f['geometry'] for f in features}
    audit_rows = json.loads(audit_path.read_text())
    audits = {a['egrid']:a for a in audit_rows}
    expected = {r['egrid'] for r in rows}
    if (len(expected)!=len(rows) or len(audits)!=len(audit_rows)
            or len(geometries)!=len(features) or set(audits)!=expected
            or not set(geometries)<=expected):
        raise ValueError('Identifiants manquants, supplémentaires ou dupliqués')
    converter = Transformer.from_crs(4326,2056,always_xy=True).transform
    output = []
    with rasterio.open(raster_path) as raster:
        if raster.crs.to_epsg()!=2056 or raster.res!=(2.,2.):
            raise ValueError('Le raster doit être en EPSG:2056, résolution 2 m')
        for row in rows:
            egrid = row['egrid']
            audit = audits[egrid]
            result = dict(egrid=egrid, numero_parcelle=row['numero_parcelle'],
                          genre_parcelle=row['genre_parcelle'],
                          statut_calcul='non_calculable',
                          ecart_surface_relatif=audit.get('ecart_surface_relatif'))
            flags = []
            if audit['statut']!='apparie' or egrid not in geometries:
                flags.append('contour_absent_ou_invalide')
            else:
                polygon = transform(converter, shape(geometries[egrid]))
                if not polygon.is_valid or polygon.is_empty or polygon.area<=0:
                    flags.append('contour_absent_ou_invalide')
                else:
                    stats = statistics(raster, polygon)
                    result.update(stats)
                if abs(audit.get('ecart_surface_relatif') or 0)>0.01:
                    flags.append('ecart_surface_superieur_1pct')
                if stats['couverture_emprise_raster_pct']<99.999999:
                    flags.append('couverture_spatiale_partielle')
                if stats['pixels_nodata']:
                    flags.append('pixels_nodata')
                if not stats['pixels_valides']:
                    flags.append('aucun_pixel_valide')
                else:
                    result['statut_calcul']='calcule_a_verifier' if flags else 'calcule'
            result['alertes_json']=flags
            output.append(result)
    out = ROOT/'data/pentes_parcelles'
    out.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in output for k in row))
    with (out/'pentes_parcelles.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        for row in output:
            writer.writerow(dict(row,alertes_json=json.dumps(row['alertes_json'],ensure_ascii=False)))
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(date_calcul_utc=datetime.now(timezone.utc).isoformat(),
                  parcelles_total=len(output),effectifs=dict(Counter(r['statut_calcul'] for r in output)),
                  alertes=dict(Counter(flag for r in output for flag in r['alertes_json'])),
                  parcelle_607=next(r for r in output if r['numero_parcelle']=='607'),
                  sources_sha256={str(p.relative_to(ROOT)):digest(p) for p in
                                  [csv_path,geometry_path,audit_path,raster_path]},
                  resultat_sha256=digest(out/'pentes_parcelles.csv'),
                  methode='Pixels de 2 m sélectionnés par rasterisation all_touched=False ; trous et NoData masqués. Statistiques sur les seuls pixels valides. Pas de pondération surfacique des pixels de bord.',
                  unite='Degrés et pourcentage de pente = 100*tan(angle). Parts des classes en pourcentage des pixels valides.',
                  limites='Les parts ne sont pas des surfaces constructibles. Données terrain 2019/2021, contours cartographiques. Aucun changement du classement de prospection.')
    (out/'resume.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
