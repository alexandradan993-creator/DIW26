"""Adaptation d'une version serveur au canevas de l'interface fournie."""
import csv
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import mapping
from croisements_contraintes import polygon_esri

ROOT=Path(__file__).resolve().parents[1]


def nombre(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):
        return None


def valeurs(v):
    return json.loads(v) if isinstance(v,str) and v else v or []


def voisinage(rows, contours, criteria):
    """Même contour MN95 que l'affichage, converti pour le contrat GeoJSON de l'équipe."""
    from shapely import transform
    raw=json.loads(contours.read_text())
    if raw.get('sr')!=2056:
        raise ValueError('Contours MN95 requis pour le voisinage')
    to_wgs=Transformer.from_crs(2056,4326,always_xy=True).transform
    features=[];seen=set()
    for item in raw['results']:
        egrid=item['attributes'].get('egris_egrid')
        if not egrid or egrid in seen:raise ValueError('Contour EGRID absent ou dupliqué')
        seen.add(egrid)
        try:polygon=polygon_esri(item.get('geometry'))
        except ValueError:continue
        features.append(dict(type='Feature',properties={'egrid':egrid},geometry=mapping(transform(polygon,to_wgs,interleaved=False))))
    with tempfile.TemporaryDirectory(prefix='voisinage-') as folder:
        path=Path(folder)/'contours.geojson'
        path.write_text(json.dumps(dict(type='FeatureCollection',features=features)),encoding='utf-8')
        return criteria.compute_forest_neighbor_index(rows,path,tolerance_m=1.0)


def derivations(stage, etat):
    """Recalcul des pentes sur le MNT local, jamais présentées comme un nouveau MNT."""
    raster=ROOT/'data/terrain/pente_degres_2m.tif'
    if not raster.exists():
        raise ValueError('Raster de pente local absent ; version précédente conservée')
    spec=importlib.util.spec_from_file_location('_pentes_application',ROOT/'scripts/calculer_pentes_parcelles.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    import rasterio
    raw=json.loads((stage/'contours.json').read_text())
    rows=[]
    etat.maj(etape='Recalcul des pentes sur les contours actualisés')
    with rasterio.open(raster) as dataset:
        if dataset.crs.to_epsg()!=2056 or dataset.res!=(2.,2.):
            raise ValueError('Raster de pente : MN95 à 2 m requis')
        for feature in raw['results']:
            row={'egrid':feature['attributes']['egris_egrid'],'statut_calcul':'non_calculable'}
            try:
                polygon=polygon_esri(feature.get('geometry'))
            except ValueError:
                rows.append(row);continue
            row.update(mod.statistics(dataset,polygon))
            if row['pixels_valides']:
                row['statut_calcul']='calcule' if row['part_pixels_valides_pct']==100 and row['couverture_emprise_raster_pct']==100 else 'calcule_a_verifier'
            rows.append(row)
    with (stage/'pentes.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader();writer.writerows(rows)
    etat.alerte('Pentes recalculées avec le modèle de terrain local ; acquisition d’un nouveau millésime du MNT non automatisée.')


def preparer(stage,rows,fiches,contours,slopes,configuration):
    spec=importlib.util.spec_from_file_location('_forme_interface',ROOT/'code/geometrie.py')
    forme=importlib.util.module_from_spec(spec);spec.loader.exec_module(forme)
    sys.path.insert(0,str(ROOT/'code'))
    try:
        spec=importlib.util.spec_from_file_location('_simulation_interface',ROOT/'code/classification.py')
        simulation=importlib.util.module_from_spec(spec);spec.loader.exec_module(simulation)
    finally:sys.path.pop(0)
    simulation.validate_config(configuration)
    raw=json.loads(contours.read_text())
    polygons={};raw_by_id={}
    for f in raw['results']:
        e=f['attributes'].get('egris_egrid');raw_by_id[e]=f.get('geometry')
        if e in polygons:raise ValueError('Contour EGRID dupliqué')
        try:polygons[e]=polygon_esri(f.get('geometry'))
        except ValueError:polygons[e]=None
    geometries=[g for e,g in polygons.items() if g is not None and e!='CH298395274555'] or [g for g in polygons.values() if g is not None]
    if not geometries:raise ValueError('Aucun contour valide pour la carte')
    minx=min(g.bounds[0] for g in geometries);miny=min(g.bounds[1] for g in geometries)
    maxx=max(g.bounds[2] for g in geometries);maxy=max(g.bounds[3] for g in geometries)
    scale=min(790/(maxx-minx),517/(maxy-miny))
    def xy(p):return [round((p[0]-minx)*scale,5),round((maxy-p[1])*scale,5)]
    slope_rows={}
    if slopes.exists():
        with slopes.open(encoding='utf-8-sig',newline='') as f:slope_rows={r['egrid']:r for r in csv.DictReader(f)}
    project=Transformer.from_crs(2056,4326,always_xy=True)
    statuses={'vert':'retenue_filtres_connus','jaune':'a_verifier_filtres','rouge':'exclue_cible'}
    result=[];addresses={};measures={};unmapped=[]
    for row in rows:
        e=row['egrid'];g=polygons.get(e)
        ficha=fiches[e];classified=ficha['classement']
        if g is None:
            unmapped.append(e)
            raw_geometry=raw_by_id.get(e) or {}
            rings=raw_geometry.get('rings',[])
            center=list(rings[0][0][:2]) if rings and rings[0] else None
            polys=[rings] if rings else []
        else:
            center=list(g.representative_point().coords[0])
            geo=mapping(g);polys=geo['coordinates'] if geo['type']=='MultiPolygon' else [geo['coordinates']]
        cx,cy=xy(center) if center else (None,None)
        polys=[[[xy(p) for p in ring] for ring in poly] for poly in polys]
        area=nombre(row.get('surface_geometrique_m2'));foot=nombre(row.get('emprise_batie_m2'))
        ratio=nombre(row.get('taux_emprise_geometrique'))
        retreat=configuration['forme']['retrait_m']
        shape={'statut_forme':'non_calculable','retrait_m':retreat}
        if g is not None:
            shape_values,_=forme.calculer_forme(g,retreat)
            mismatch=area is None or area<=0 or abs(g.area-area)/area>.01
            shape.update(shape_values,statut_forme='calcule_a_verifier' if mismatch else 'calcule')
        slope=slope_rows.get(e,{})
        indicators=simulation.analyse(row,configuration,slope=slope,form=shape)
        ficha['donnees']=row
        ficha['indicateurs']=indicators
        margin=indicators['marge_emprise_cos_pct'];gap=indicators['ecart_apparent_simule_m2']
        notes=sorted(set(n for key in ('notes_batiment_existante_json','notes_batiment_provisoire_json','notes_site_existante_json','notes_site_provisoire_json') for n in valeurs(row.get(key))),key=str)
        slope=slope_rows.get(e,{})
        measures[e]=[ratio,nombre(slope.get('pente_mediane_pct'))]
        addresses[e]=[' '.join(str(a.get(k) or '') for k in ('rue','numero')).strip() for a in valeurs(row.get('adresses_json'))]
        facts=[row.get('genre_parcelle'),foot,ratio,nombre(row.get('batiments_nombre')),indicators['logements_rattachement_declare'],nombre(row.get('surface_plancher_verifiee_m2')),None,
            nombre(slope.get('pente_mediane_pct')),nombre(slope.get('part_pixels_valides_pct')),indicators['part_terrain_apres_retrait_pct'],shape.get('surface_apres_retrait_m2'),indicators['forme_statut'],margin,notes,None,None,None,None,None,None,gap]
        def labels(keys,prefix):return [prefix+classified['filtres'][key].get('label',key) for key in keys]
        checks=labels(classified.get('filtres_inconnus',[]),'Information manquante · ')+labels(classified.get('alertes',[]),'Alerte · ')+labels(classified.get('criteres_evaluation_defavorables',[]),'Évaluation · ')+labels(classified.get('notes_reglementaires',[]),'Information · ')+indicators['anomalies_bati_json']
        if not ficha['presente_derniere_collecte']:
            checks.insert(0,'Absente de la dernière collecte : parcelle conservée pour examen, pas une suppression confirmée.')
        descriptor_keys=('domaine_cadastral','domaine_public_communal','domaine_public_cantonal',
            'surface_hors_emprise_m2','surface_verte_cartographiee_m2','surface_verte_cartographiee_pct',
            'surface_dure_cartographiee_m2','surface_dure_cartographiee_pct','intersection_foret',
            'surface_intersection_foret_m2','part_intersection_foret_pct','intersection_eaux',
            'surface_intersection_eaux_m2','part_intersection_eaux_pct','distance_lisiere_foret_m',
            'distance_cours_d_eau_m','voisine_parcelle_avec_foret','distance_parcelle_forestiere_m','egrid_voisin_forestier')
        descriptors=[classified.get(k) for k in descriptor_keys]
        current={k:classified.get(k) for k in ('cos_zone_dominante','surface_exploitable_avec_batiment_m2',
            'surface_exploitable_sans_batiment_m2','surface_exploitable_statut','ius_zone_dominante',
            'plancher_max_theorique_ius_m2','hauteur_reglementaire_max_m','hauteur_batiment_existant_m',
            'piste_surelevation','surelevation_etude_applicable','motif_surelevation','hauteur_reference_scenario_m',
            'niveaux_reference_scenario_min','niveaux_reference_scenario_max','niveaux_supplementaires_scenario_min',
            'niveaux_supplementaires_scenario_max')}
        constraints=ficha['contraintes']
        official={k:constraints[k] for k in constraints}
        forest_alone=(nombre(classified.get('surface_intersection_foret_m2')) or 0)>0 and not classified['filtres_echoues'] and not classified['filtres_inconnus'] and classified['filtres']['emprise_max']['etat']=='ok'
        info=[area,row.get('zone_dominante'),labels(classified.get('filtres_echoues',[]),'Échec · '),checks,row.get('url_rdppf'),facts,official,descriptors,current,forest_alone]
        status=statuses.get(classified['statut_filtrage_criteres'],'a_verifier_filtres')
        result.append([str(row.get('numero_parcelle') or ''),e,status,polys,cx,cy,info,center,list(project.transform(*center)) if center else None,None])
    (stage/'interface.json').write_text(json.dumps(dict(schema_version=2,version=next(iter(fiches.values()))['version'],parcels=result,addresses=addresses,measures=measures,non_cartographiees=unmapped,total=len(rows),masquees_par_defaut=[r['egrid'] for r in rows if r['egrid']=='CH298395274555']),ensure_ascii=False,allow_nan=False),encoding='utf-8')
