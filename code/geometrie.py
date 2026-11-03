"""Enveloppes exploratoires après retrait uniforme, en coordonnées métriques."""
import math

from shapely.geometry import Polygon


def calculer_forme(polygon, retrait_m):
    if type(retrait_m) not in (int,float) or not math.isfinite(retrait_m) or retrait_m<0:
        raise ValueError('Retrait : nombre fini positif ou nul attendu')
    if polygon.geom_type not in ('Polygon','MultiPolygon') or not polygon.is_valid or polygon.is_empty or polygon.area<=0:
        raise ValueError('Contour surfacique valide requis ; aucune réparation automatique')
    envelope=polygon.buffer(-retrait_m,quad_segs=32) if retrait_m else polygon
    parts=[] if envelope.is_empty else [envelope] if isinstance(envelope,Polygon) else list(envelope.geoms)
    area=sum(p.area for p in parts)
    rectangle=polygon.minimum_rotated_rectangle
    coords=list(rectangle.exterior.coords)
    sides=[math.dist(coords[i],coords[i+1]) for i in range(4)]
    return dict(surface_contour_m2=polygon.area,retrait_m=retrait_m,
                surface_apres_retrait_m2=area,
                part_terrain_apres_retrait_pct=100*area/polygon.area,
                nombre_enveloppes=len(parts),
                plus_grande_enveloppe_m2=max((p.area for p in parts),default=0),
                compacite=4*math.pi*polygon.area/polygon.length**2,
                allongement_rectangle_englobant=max(sides)/min(sides)), envelope
