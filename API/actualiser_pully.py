"""Recrée la base pully_parcelles.csv depuis GEO.vd et SIGIP.

Le script produit un NOUVEAU fichier, pully_parcelles_AAAA-MM-JJ_HHMM.csv, avec
exactement les mêmes 76 colonnes et les mêmes clés JSON que la base actuelle.
Il ne remplace jamais une base existante. L'application lit le fichier d'état
(etat_actualisation.json) pour afficher l'avancement puis la notification.

Usage (depuis le dossier de ce script) :
    python actualiser_pully.py --diagnostic
        teste seulement l'accès à chaque source, sans rien produire
    python actualiser_pully.py --sortie versions --reference ../pully_parcelles.csv
        produit la nouvelle base et un rapport de différences avec la référence

Dépendance externe unique : shapely  (pip install shapely)
Tout le reste est dans la bibliothèque standard de Python 3.10+.

Coordonnées : tout est demandé et calculé en MN95 / EPSG:2056, en mètres.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import tempfile
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
SCHEMA = json.loads((ICI / "schema_pully_parcelles.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Configuration des sources (modifiable sans toucher au reste du code)
# ---------------------------------------------------------------------------
GEOVD = "https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer"
SIGIP_WFS = "https://www.sigip.ch/mapserv_proxy"
NO_COM_CANT_PULLY = 136
NO_COM_OFS_PULLY = 5590

COUCHES_GEOVD = {
    "parcelles": 272,          # vd.bien_fond
    "batiments": 276,          # vd.batiment
    "zones_affectation": 36,   # vd.zone_affectation
    "adresses": 241,           # vd.adresse (points)
}

# Couches SIGIP : nom WFS -> type de géométrie attendu
COUCHES_SIGIP = {
    "pully_recensement_provisoire_batiments": "surface",
    "pully_recensement_provisoire_sites": "surface",
    "rec_arch_s": "surface",
    "rec_arch_p": "point",
    "rec_arch_site": "surface",
    "zone_reservee": "surface",
    "pga_zones_affectation": "surface",
    "surfaces_vertes": "surface",
    "surfaces_dures": "surface",
    "forets": "surface",
    "eaux": "surface",
    "rcb_bat": "point",
    "jardins_historiques": "surface",
}

# Colonnes qui ont aussi une surface totale d'intersection (union des objets)
TOTAUX_SURFACE = {
    "batiments": "batiments_surface_intersection_m2",
    "sigip_zone_reservee": "sigip_zone_reservee_surface_intersection_m2",
    "sigip_surfaces_vertes": "sigip_surfaces_vertes_surface_intersection_m2",
    "sigip_surfaces_dures": "sigip_surfaces_dures_surface_intersection_m2",
    "sigip_forets": "sigip_forets_surface_intersection_m2",
    "sigip_eaux": "sigip_eaux_surface_intersection_m2",
}

SEUIL_INTERSECTION_M2 = 0.1   # les objets qui ne touchent que le bord sont ignorés
TIMEOUT_S = 90
ESSAIS = 3
URL_RE = re.compile(r"https?://[^'\"\s<>)]+")


# ---------------------------------------------------------------------------
# Fichier d'état lu par l'interface
# ---------------------------------------------------------------------------
class Etat:
    ETAPES = ["Vérification des sources", "Récupération", "Contrôle",
              "Calcul des attributs", "Écriture"]

    def __init__(self, dossier: Path):
        self.chemin = dossier / "etat_actualisation.json"
        self.data = {"statut": "en_cours", "etape": None,
                     "debut_utc": maintenant(), "fin_utc": None,
                     "fichier": None, "sources": {}, "alertes": [],
                     "bilan": None, "erreur": None}

    def maj(self, **kv):
        self.data.update(kv)
        ecrire_atomique(self.chemin, json.dumps(self.data, ensure_ascii=False, indent=2))

    def alerte(self, texte):
        print("ALERTE :", texte)
        self.data["alertes"].append(texte)
        self.maj()


def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ecrire_atomique(chemin: Path, texte: str, encoding="utf-8"):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
        f.write(texte)
    os.replace(tmp, chemin)


# ---------------------------------------------------------------------------
# Accès réseau
# ---------------------------------------------------------------------------
def telecharger(url: str, params: dict | None = None, post: bool = False) -> bytes:
    data = None
    if params:
        enc = urllib.parse.urlencode(params)
        if post:
            data = enc.encode()
        else:
            url = f"{url}?{enc}"
    dernier = None
    for essai in range(ESSAIS):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "DIW26-actualisation/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return r.read()
        except Exception as e:  # réseau, HTTP, délai
            dernier = e
            time.sleep(2 * (essai + 1))
    raise RuntimeError(f"Échec de téléchargement : {url[:150]} ({dernier})")


# --- GEO.vd : ArcGIS REST ---------------------------------------------------
def arcgis_info(layer_id: int) -> dict:
    return json.loads(telecharger(f"{GEOVD}/{layer_id}", {"f": "json"}))


def arcgis_requete(layer_id: int, where: str, bbox=None) -> list[dict]:
    """Toutes les entités d'une couche, en MN95, par paquets d'OBJECTID."""
    base = {"where": where, "f": "json", "outSR": 2056}
    if bbox:
        base.update(geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope",
                    inSR=2056, spatialRel="esriSpatialRelIntersects")
    ids = json.loads(telecharger(f"{GEOVD}/{layer_id}/query", {**base, "returnIdsOnly": "true"}, post=True))
    if "error" in ids:
        raise RuntimeError(f"GEO.vd couche {layer_id} : {ids['error']}")
    oids = sorted(ids.get("objectIds") or [])
    entites, types = [], {}
    for i in range(0, len(oids), 200):
        paquet = oids[i:i + 200]
        rep = json.loads(telecharger(f"{GEOVD}/{layer_id}/query", {
            "objectIds": ",".join(map(str, paquet)), "outFields": "*",
            "returnGeometry": "true", "outSR": 2056, "f": "json"}, post=True))
        if "error" in rep:
            raise RuntimeError(f"GEO.vd couche {layer_id} : {rep['error']}")
        for f in rep.get("fields", []):
            types[f["name"]] = f["type"]
        for f in rep.get("features", []):
            attrs = {k: typer_arcgis(v, types.get(k)) for k, v in f["attributes"].items()}
            entites.append({"attributs": attrs, "geometrie": geom_arcgis(f.get("geometry"))})
    return entites


def typer_arcgis(v, t):
    if v is None:
        return None
    if t in ("esriFieldTypeDouble", "esriFieldTypeSingle"):
        return float(v)
    if t in ("esriFieldTypeInteger", "esriFieldTypeSmallInteger", "esriFieldTypeOID"):
        return int(v)
    return v


def geom_arcgis(g):
    from shapely.geometry import Point, Polygon, MultiPolygon
    from shapely.validation import make_valid
    if not g:
        return None
    if "x" in g:
        return Point(g["x"], g["y"])
    if "rings" in g:
        # ArcGIS : anneaux extérieurs dans le sens horaire, trous dans le sens inverse
        exterieurs, trous = [], []
        for ring in g["rings"]:
            aire = sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:] + ring[:1]))
            (exterieurs if aire < 0 else trous).append([(p[0], p[1]) for p in ring])
        polys = [Polygon(e) for e in exterieurs]
        for t in trous:
            tp = Polygon(t)
            for i, p in enumerate(polys):
                if p.contains(tp.representative_point()):
                    polys[i] = Polygon(p.exterior.coords, list(p.interiors) + [t])
                    break
        geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
        return geom if geom.is_valid else make_valid(geom)
    return None


# --- SIGIP : WFS ------------------------------------------------------------
NS_GML = "http://www.opengis.net/gml"


def wfs_types(couche: str) -> dict:
    """Types des attributs via DescribeFeatureType (pour lire 1957.0 en nombre)."""
    try:
        xml = telecharger(SIGIP_WFS, {"SERVICE": "WFS", "VERSION": "1.1.0",
                                      "REQUEST": "DescribeFeatureType", "TYPENAME": couche})
        racine = ET.fromstring(xml)
    except Exception:
        return {}
    types = {}
    for el in racine.iter():
        if el.tag.endswith("element") and el.get("name") and el.get("type"):
            types[el.get("name")] = el.get("type").split(":")[-1].lower()
    return types


def wfs_requete(couche: str, bbox, max_par_requete=5000, profondeur=0) -> list[dict]:
    xml = telecharger(SIGIP_WFS, {
        "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
        "TYPENAME": couche, "SRSNAME": "EPSG:2056", "MAXFEATURES": max_par_requete,
        "BBOX": ",".join(map(str, bbox)) + ",EPSG:2056"})
    racine = ET.fromstring(xml)
    if racine.tag.endswith("ExceptionReport") or racine.tag.endswith("ServiceExceptionReport"):
        raise RuntimeError(f"SIGIP {couche} : {ET.tostring(racine, encoding='unicode')[:300]}")
    entites = []
    for membre in racine.iter():
        if not (membre.tag.endswith("featureMember") or membre.tag.endswith("featureMembers")):
            continue
        for feat in list(membre):
            entites.append(lire_feature_gml(feat))
    if len(entites) >= max_par_requete and profondeur < 6:
        # trop d'objets : on découpe la zone en 4 et on dédoublonne
        x0, y0, x1, y1 = bbox
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        vus, resultat = set(), []
        for b in [(x0, y0, xm, ym), (xm, y0, x1, ym), (x0, ym, xm, y1), (xm, ym, x1, y1)]:
            for e in wfs_requete(couche, b, max_par_requete, profondeur + 1):
                cle = e["gml_id"] or (e["geometrie"].wkb if e["geometrie"] is not None else None,
                                      json.dumps(e["attributs"], sort_keys=True, default=str))
                if cle not in vus:
                    vus.add(cle)
                    resultat.append(e)
        return resultat
    return entites


def lire_feature_gml(feat) -> dict:
    gml_id = feat.get(f"{{{NS_GML}}}id") or feat.get("fid")
    attrs, geom = {}, None
    for enfant in feat:
        nom = enfant.tag.split("}")[-1]
        sous = list(enfant)
        if sous and sous[0].tag.startswith(f"{{{NS_GML}}}"):
            if nom in ("boundedBy",):
                continue
            geom = geom_gml(sous[0])
        else:
            attrs[nom] = enfant.text if enfant.text not in (None, "") else None
    return {"gml_id": gml_id, "attributs": attrs, "geometrie": geom}


def _coords(el):
    pos = el.find(f".//{{{NS_GML}}}posList")
    if pos is not None:
        v = list(map(float, pos.text.split()))
        dim = int(pos.get("srsDimension") or el.get("srsDimension") or 2)
        return [(v[i], v[i + 1]) for i in range(0, len(v), dim)]
    pts = el.findall(f".//{{{NS_GML}}}pos")
    if pts:
        return [tuple(map(float, p.text.split()[:2])) for p in pts]
    c = el.find(f".//{{{NS_GML}}}coordinates")
    if c is not None:
        return [tuple(map(float, xy.split(",")[:2])) for xy in c.text.split()]
    return []


def geom_gml(el):
    from shapely.geometry import Point, Polygon, MultiPolygon, LineString
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    tag = el.tag.split("}")[-1]
    if tag == "Point":
        return Point(_coords(el)[0])
    if tag in ("Polygon", "PolygonPatch"):
        ext = el.find(f"{{{NS_GML}}}exterior")
        if ext is None:
            ext = el.find(f"{{{NS_GML}}}outerBoundaryIs")
        ints = el.findall(f"{{{NS_GML}}}interior") + el.findall(f"{{{NS_GML}}}innerBoundaryIs")
        p = Polygon(_coords(ext), [_coords(i) for i in ints])
        return p if p.is_valid else make_valid(p)
    if tag in ("MultiSurface", "MultiPolygon", "Surface", "CompositeSurface"):
        polys = [geom_gml(p) for p in el.iter() if p.tag.split("}")[-1] in ("Polygon", "PolygonPatch")]
        return unary_union([p for p in polys if p is not None]) if polys else None
    if tag in ("MultiPoint",):
        pts = [Point(_coords(p)[0]) for p in el.iter() if p.tag.endswith("}Point")]
        return unary_union(pts)
    if tag in ("LineString", "MultiCurve", "MultiLineString", "Curve"):
        return LineString(_coords(el))
    return None


DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}:\d{2}))?")


def typer_wfs(v, t):
    if v is None:
        return None
    if t in ("int", "integer", "long", "short", "byte"):
        try:
            return int(v)
        except ValueError:
            return float(v)
    if t in ("double", "float", "decimal", "real"):
        return float(v)
    if t in ("date", "datetime"):
        m = DATE_RE.match(v)
        if m:
            return f"{m.group(1)} {m.group(2) or '00:00:00'}"
    return v


# ---------------------------------------------------------------------------
# Construction de la base
# ---------------------------------------------------------------------------
def objet_json(cles: list[str], valeurs: dict, inter, source_layer=None) -> dict:
    """Ordonne les clés comme dans la base de référence."""
    o = {}
    for k in cles:
        if k == "surface_intersection_m2":
            o[k] = inter
        elif k == "source_layer":
            o[k] = source_layer
        elif k.endswith("_urls"):
            base = valeurs.get(k[:-5])
            if isinstance(base, str) and URL_RE.search(base):
                o[k] = URL_RE.findall(base)
        else:
            o[k] = valeurs.get(k)
    return o


def rattacher(parcelle, index, entites, ponctuel: bool):
    """Objets touchant la parcelle, avec leur surface d'intersection."""
    resultat, morceaux = [], []
    for i in index.query(parcelle):
        e = entites[i]
        g = e["geometrie"]
        if g is None:
            continue
        if ponctuel or g.geom_type in ("Point", "MultiPoint"):
            if parcelle.covers(g):
                resultat.append((e, None))
            continue
        inter = parcelle.intersection(g)
        if inter.area >= SEUIL_INTERSECTION_M2:
            resultat.append((e, round(inter.area, 3)))
            morceaux.append(inter)
    return resultat, morceaux


def construire(etat: Etat, bbox_force=None) -> list[dict]:
    from shapely.strtree import STRtree
    from shapely.ops import unary_union

    cols = SCHEMA["colonnes"]
    cles = SCHEMA["cles_json"]

    # 1. Parcelles -----------------------------------------------------------
    etat.maj(etape="Récupération")
    print("Parcelles (GEO.vd)…")
    try:
        parcelles = arcgis_requete(COUCHES_GEOVD["parcelles"], f"NO_COM_CANT = {NO_COM_CANT_PULLY}")
    except RuntimeError:  # champ stocké en texte
        parcelles = arcgis_requete(COUCHES_GEOVD["parcelles"], f"NO_COM_CANT = '{NO_COM_CANT_PULLY}'")
    if not parcelles:
        raise RuntimeError("Aucune parcelle reçue de GEO.vd")
    geoms = [p["geometrie"] for p in parcelles if p["geometrie"] is not None]
    minx, miny, maxx, maxy = unary_union(geoms).bounds
    bbox = bbox_force or (minx - 50, miny - 50, maxx + 50, maxy + 50)

    # 2. Couches -------------------------------------------------------------
    sources = {}
    print("Bâtiments, zones, adresses (GEO.vd)…")
    sources["batiments"] = arcgis_requete(COUCHES_GEOVD["batiments"], "1=1", bbox)
    sources["zones_affectation"] = arcgis_requete(COUCHES_GEOVD["zones_affectation"], "1=1", bbox)
    sources["adresses"] = arcgis_requete(COUCHES_GEOVD["adresses"], "1=1", bbox)
    for couche in COUCHES_SIGIP:
        print(f"SIGIP {couche}…")
        types = wfs_types(couche)
        ents = wfs_requete(couche, bbox)
        for e in ents:
            e["attributs"] = {k: typer_wfs(v, types.get(k)) for k, v in e["attributs"].items()}
        sources[f"sigip_{couche}"] = ents
    for nom, ents in sources.items():
        etat.data["sources"][nom] = {"objets": len(ents), "verifie_utc": maintenant()}
        if not ents:
            raise RuntimeError(f"Source vide : {nom}. Mise à jour non appliquée — vérification nécessaire.")
    etat.maj()

    # 3. Contrôle ------------------------------------------------------------
    etat.maj(etape="Contrôle")
    index = {}
    for nom, ents in sources.items():
        valides = [i for i, e in enumerate(ents) if e["geometrie"] is not None]
        if len(valides) < len(ents):
            etat.alerte(f"{nom} : {len(ents) - len(valides)} objets sans géométrie ignorés")
        arbre = STRtree([ents[i]["geometrie"] for i in valides])
        index[nom] = (arbre, valides)
    champs_attendus = {
        "batiments": cles["batiments_json"], "zones_affectation": cles["zones_affectation_json"],
        **{f"sigip_{c}": cles[f"sigip_{c}_json"] for c in COUCHES_SIGIP}}
    for nom, attendus in champs_attendus.items():
        recus = set().union(*(e["attributs"].keys() for e in sources[nom]))
        manquants = [k for k in attendus if k not in recus and k not in
                     ("surface_intersection_m2", "source_layer", "gml_id") and not k.endswith("_urls")]
        if manquants:
            etat.alerte(f"{nom} : champs absents de la source, laissés vides : {manquants}")

    # 4. Calcul --------------------------------------------------------------
    etat.maj(etape="Calcul des attributs")
    lignes, egrids = [], set()
    for p in parcelles:
        a, poly = p["attributs"], p["geometrie"]
        if poly is None or poly.is_empty:
            etat.alerte(f"Parcelle {a.get('NUMERO')} sans géométrie : ignorée")
            continue
        egrid = trouver_egrid(a)
        if not egrid:
            etat.alerte(f"Parcelle {a.get('NUMERO')} sans EGRID : ignorée")
            continue
        if egrid in egrids:
            etat.alerte(f"EGRID en double {egrid} : seconde occurrence ignorée")
            continue
        egrids.add(egrid)
        surf = poly.area
        L = {c: None for c in cols}
        L.update({
            "egrid": egrid,
            "numero_parcelle": str(a.get("NUMERO")),
            "genre_parcelle": a.get("GENRE_TXT"),
            "surface_mo_m2": surface_mo(a, surf),
            "surface_rf_m2": None if a.get("SUPERFICIE_RF") is None else float(a["SUPERFICIE_RF"]),
            "surface_geometrique_m2": surf,
            "url_rdppf": f"https://www.rdppf.vd.ch/ws/RdppfSVC.svc/extract/url/?EGRID={egrid}",
            "url_extrait_rdppf": f"https://www.rdppf.vd.ch/ws/RdppfSVC.svc/extract/pdf/?EGRID={egrid}",
            "statut_potentiel": "a_evaluer",
        })

        # couches surfaciques et ponctuelles
        for nom, ents in sources.items():
            col = f"{nom}_json"
            if col not in cles or nom == "adresses":
                continue
            arbre, valides = index[nom]
            sous = [ents[i] for i in valides]
            ponctuel = nom.startswith("sigip_") and COUCHES_SIGIP.get(nom[6:]) == "point"
            trouves, morceaux = rattacher(poly, arbre, sous, ponctuel)
            couche_sigip = nom[6:] if nom.startswith("sigip_") else None
            objets = []
            for e, inter in trouves:
                valeurs = dict(e["attributs"])
                if couche_sigip:
                    valeurs["gml_id"] = e["gml_id"]
                elif nom == "zones_affectation":
                    g = e["geometrie"]
                    valeurs.setdefault("SHAPE.AREA", g.area)
                    valeurs.setdefault("SHAPE.LEN", g.length)
                objets.append(objet_json(cles[col], valeurs, inter, couche_sigip))
            L[col] = objets
            L[f"{nom}_nombre"] = len(objets)
            if nom in TOTAUX_SURFACE:
                L[TOTAUX_SURFACE[nom]] = round(unary_union(morceaux).area, 3) if morceaux else 0.0

        # adresses (points GEO.vd)
        arbre, valides = index["adresses"]
        adr, _ = rattacher(poly, arbre, [sources["adresses"][i] for i in valides], True)
        L["adresses_json"] = [{"rue": e["attributs"].get("VOIE_TXT"),
                               "numero": none_str(e["attributs"].get("NO_ENTREE")),
                               "egid": entier(e["attributs"].get("EGID"))} for e, _ in adr]
        L["adresses_nombre"] = len(L["adresses_json"])

        deriver(L)
        lignes.append(L)
    return lignes


def trouver_egrid(a: dict):
    for k in ("EGRID", "URL_EXTRAIT_RDPPF", "URL_GUICHET_RDPPF", "URL"):
        m = re.search(r"CH\d{12}", str(a.get(k) or ""))
        if m:
            return m.group(0)
    return None


def surface_mo(a: dict, surf_geom: float):
    for k in ("SUPERFICIE_MO", "SURFACE_MO", "SURFACE", "SUPERFICIE"):
        if a.get(k) is not None:
            return int(round(float(a[k])))
    return int(round(surf_geom))  # approximation documentée dans le README


def none_str(v):
    return None if v is None else str(v)


def entier(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def deriver(L: dict):
    """Colonnes calculées. Règles vérifiées sur les 2 672 lignes de la référence."""
    surf = L["surface_geometrique_m2"]
    empr = L.get("batiments_surface_intersection_m2") or 0.0
    L["emprise_batie_m2"] = empr
    L["taux_emprise_geometrique"] = empr / surf if surf else None
    L["surface_hors_emprise_batiments_m2"] = surf - empr

    zones = L.get("zones_affectation_json") or []
    if zones:
        z = max(zones, key=lambda o: o.get("surface_intersection_m2") or 0)
        L["zone_dominante"] = z.get("DESIGNATION_COM")
        L["zone_dominante_statut"] = z.get("STATUT_JURIDIQUE")
        L["zone_dominante_part_surface"] = (z.get("surface_intersection_m2") or 0) / surf if surf else None
        L["cos_source_zone_dominante"] = z.get("COS")
        L["ius_source_zone_dominante"] = z.get("IUS")
    else:
        L["zone_dominante_part_surface"] = 0.0

    rcb = L.get("sigip_rcb_bat_json") or []
    for champ, prefixe, agg in [("nbre_logements", "rcb_nbre_logements", "somme"),
                                ("nombre_niveaux", "rcb_nombre_niveaux", "max"),
                                ("annee_construction", "rcb_annee_construction", "max"),
                                ("surf_plancher", "rcb_surf_plancher", "somme")]:
        v = [o[champ] for o in rcb if o.get(champ) is not None]
        L[f"{prefixe}_renseignes"] = len(v)
        valeurs_numeriques = [float(x) for x in v if x is not None and str(x).strip() != ""]
        L[f"{prefixe}_{agg}"] = (
            (sum(valeurs_numeriques) if agg == "somme" else max(valeurs_numeriques))
            if valeurs_numeriques
            else None
        )

    notes = {
        "batiment_existante": ("sigip_rec_arch_s_json", "note_detail"),
        "batiment_provisoire": ("sigip_pully_recensement_provisoire_batiments_json", "note_provisoire"),
        "site_existante": ("sigip_rec_arch_site_json", "note_carto"),
        "site_provisoire": ("sigip_pully_recensement_provisoire_sites_json", "note_provisoire"),
    }
    for nom, (col, champ) in notes.items():
        n = [entier(o[champ]) for o in (L.get(col) or []) if o.get(champ) is not None]
        L[f"notes_{nom}_json"] = n
        L[f"presence_note_1_3_{nom}"] = any(isinstance(x, int) and 1 <= x <= 3 for x in n)


# ---------------------------------------------------------------------------
# Écriture et comparaison
# ---------------------------------------------------------------------------
def cellule(v):
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def ecrire_csv(chemin: Path, lignes: list[dict]):
    cols = SCHEMA["colonnes"]
    fd, tmp = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for L in lignes:
            w.writerow([cellule(L.get(c)) for c in cols])
    os.replace(tmp, chemin)


def normaliser(v: str):
    if v == "":
        return None
    try:
        j = json.loads(v)
    except (ValueError, TypeError):
        return v
    if isinstance(j, list):
        return sorted((json.dumps(arrondir(o), sort_keys=True, ensure_ascii=False) for o in j))
    return arrondir(j)


def arrondir(o):
    if isinstance(o, float):
        return round(o, 2) if math.isfinite(o) else o
    if isinstance(o, dict):
        return {k: arrondir(v) for k, v in o.items()}
    if isinstance(o, list):
        return [arrondir(v) for v in o]
    return o


def comparer(nouveau: Path, reference: Path) -> dict:
    """Différences par EGRID. L'ordre des objets dans les listes est ignoré."""
    lire = lambda p: {r["egrid"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig", newline=""))}
    N, R = lire(nouveau), lire(reference)
    colonnes_diff, exemples, modifiees = {}, {}, set()
    for eg in N.keys() & R.keys():
        for c in SCHEMA["colonnes"]:
            if normaliser(N[eg].get(c, "")) != normaliser(R[eg].get(c, "")):
                colonnes_diff[c] = colonnes_diff.get(c, 0) + 1
                modifiees.add(eg)
                exemples.setdefault(c, []).append(
                    {"egrid": eg, "numero": R[eg]["numero_parcelle"],
                     "avant": R[eg].get(c, "")[:300], "apres": N[eg].get(c, "")[:300]})
    return {
        "reference": str(reference), "nouveau": str(nouveau),
        "parcelles_reference": len(R), "parcelles_nouvelles": len(N),
        "ajoutees": sorted(N.keys() - R.keys()), "absentes": sorted(R.keys() - N.keys()),
        "modifiees": len(modifiees),
        "colonnes_differentes": dict(sorted(colonnes_diff.items(), key=lambda x: -x[1])),
        "exemples": {c: v[:5] for c, v in exemples.items()},
    }


# ---------------------------------------------------------------------------
# Diagnostic et programme principal
# ---------------------------------------------------------------------------
def diagnostic() -> bool:
    ok = True
    for nom, lid in COUCHES_GEOVD.items():
        try:
            info = arcgis_info(lid)
            print(f"[OK]     GEO.vd {nom:<22} {info.get('name')}  ({len(info.get('fields', []))} champs)")
        except Exception as e:
            ok = False
            print(f"[ERREUR] GEO.vd {nom:<22} {e}")
    for couche in COUCHES_SIGIP:
        try:
            n = len(wfs_requete(couche, (2540000, 1151500, 2540300, 1151800), 50, profondeur=6))
            print(f"[OK]     SIGIP  {couche:<40} {n} objets dans une zone test")
        except Exception as e:
            ok = False
            print(f"[ERREUR] SIGIP  {couche:<40} {e}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", default="versions", help="dossier des nouvelles bases")
    ap.add_argument("--reference", help="base actuelle à comparer (ex. ../pully_parcelles.csv)")
    ap.add_argument("--diagnostic", action="store_true", help="teste les sources sans rien produire")
    ap.add_argument("--croisements", action="store_true", help="export ISOS/dangers seulement ; aucune base active remplacée")
    ap.add_argument("--diagnostic-croisements", action="store_true", help="affiche les métadonnées et champs des couches 404/422")
    ap.add_argument("--contours", type=Path, default=ICI.parent / "data/parcelles/source_esri_lv95.json")
    ap.add_argument("--champ-site-isos", help="nom exact du champ de site après vérification du schéma")
    ap.add_argument("--champ-classe-danger", help="nom exact du champ de classe après vérification du schéma")
    ap.add_argument("--couverture-isos", type=Path, help="périmètre d'étude sourcé en MN95")
    ap.add_argument("--couverture-dangers", type=Path, help="périmètre d'étude sourcé en MN95")
    args = ap.parse_args()

    if args.diagnostic_croisements:
        from croisements_contraintes import BASE, LAYERS, request_json
        for nom, lid in LAYERS.items():
            info = request_json(f"{BASE}/{lid}?f=json")
            print(json.dumps({"source": nom, "url": f"{BASE}/{lid}",
                              "champs": info.get("fields"), "edition": info.get("editingInfo"),
                              "attribution": info.get("copyrightText")}, ensure_ascii=False, indent=2))
        return

    if args.diagnostic:
        sys.exit(0 if diagnostic() else 1)

    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    verrou = sortie / "actualisation.lock"
    try:
        fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        print("Une actualisation est déjà en cours (fichier actualisation.lock).")
        sys.exit(2)

    etat = Etat(sortie)
    try:
        etat.maj(etape="Vérification des sources")
        if args.croisements:
            from croisements_contraintes import export_crossings
            reference = Path(args.reference) if args.reference else ICI.parent / "pully_parcelles.csv"
            chemin, rapport = export_crossings(reference, args.contours, sortie, etat,
                                               args.champ_site_isos, args.champ_classe_danger,
                                               args.couverture_isos, args.couverture_dangers)
            etat.maj(statut="termine", fin_utc=maintenant(), fichier=str(chemin.relative_to(sortie)),
                     bilan={"parcelles": rapport["parcelles"], "croisements": rapport["bilan"]},
                     alertes=[f"{key} : {count} parcelle(s)" for key, count in rapport["alertes"].items()],
                     etape=None, mode="croisements_seuls",
                     activation_automatique=False)
            print(f"Export à vérifier : {chemin}")
            return
        if not diagnostic():
            raise RuntimeError("Au moins une source est inaccessible. Base actuelle conservée.")
        lignes = construire(etat)
        etat.maj(etape="Écriture")
        nom = f"pully_parcelles_{datetime.now().strftime('%Y-%m-%d_%H%M')}.csv"
        chemin = sortie / nom
        ecrire_csv(chemin, lignes)
        bilan = {"parcelles": len(lignes)}
        if args.reference:
            rapport = comparer(chemin, Path(args.reference))
            ecrire_atomique(sortie / nom.replace(".csv", "_comparaison.json"),
                            json.dumps(rapport, ensure_ascii=False, indent=2))
            bilan.update({k: (len(v) if isinstance(v, list) else v) for k, v in rapport.items()
                          if k in ("ajoutees", "absentes", "modifiees")})
        etat.maj(statut="termine", fin_utc=maintenant(), fichier=nom, bilan=bilan, etape=None)
        print(f"Terminé : {chemin}  {bilan}")
    except Exception as e:
        etat.maj(statut="erreur", fin_utc=maintenant(),
                 erreur=f"Mise à jour non appliquée — vérification nécessaire. {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        verrou.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
