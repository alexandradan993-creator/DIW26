"""Filtrage explicable des parcelles selon ``code/criteres.json``.

Module autonome (Python 3.10+, bibliothèque standard), compatible avec le dépôt
DIW26. Aucune écriture dans ``classification.py`` ou ``prospection.py``.

Les champs non établis (pleine terre, distances réglementaires, dangers, accès,
ISOS et ratio RD) ne sont JAMAIS supposés favorables. Le filtrage retourne :
``rouge`` si exclusion confirmée, ``jaune`` si information obligatoire
manquante, couverture défavorable, intersection forestière mesurée ou voisinage
de parcelle contenant de la forêt (si contours disponibles), et
``vert`` si toutes les règles actives passent sans alerte forestière détectée.

Les seuils de potentiel fort/moyen et ratio RD sont des SIGNAUX, pas des couleurs.
Ce fichier ne certifie pas la constructibilité.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).with_name("criteres.json")
DEFAULT_DATA = Path(__file__).resolve().parents[1] / "pully_parcelles.csv"
DEFAULT_SLOPES = Path(__file__).resolve().parents[1] / "data" / "pentes_parcelles" / "pentes_parcelles.csv"
DEFAULT_CONTOURS = Path(__file__).resolve().parents[1] / "data" / "parcelles" / "contours.geojson"


def number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(str(raw).strip().replace(",", "."))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def flag(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    value = str(raw).strip().casefold()
    if value in ("true", "vrai", "oui", "yes", "1"):
        return True
    if value in ("false", "faux", "non", "no", "0"):
        return False
    return None


def pick(row: dict, *keys: str) -> Any:
    """Return first nonblank available value; never infer a missing field."""
    for key in keys:
        value = row.get(key)
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
    return None


def validate_config(cfg: dict) -> None:
    required = {
        "surface_min_m2", "emprise_max", "surface_parcelle",
        "patrimoine_recensement", "zone_reservee_pleine_terre",
        "ratio_sous_exploitation_rd", "reculs_rdppf_metres", "zonage_et_dangers",
    }
    if not isinstance(cfg, dict) or set(cfg) != required:
        raise ValueError("criteres.json: clés absentes ou inattendues")
    for section, keys in {
        "surface_parcelle": ("seuil_fort_potentiel_m2", "seuil_moyen_potentiel_m2"),
        "patrimoine_recensement": ("notes_exclues",),
        "zone_reservee_pleine_terre": ("seuil_exclusion_pourcentage", "seuil_malus_pourcentage"),
        "ratio_sous_exploitation_rd": ("seuil_fort_potentiel", "seuil_moyen_potentiel"),
        "reculs_rdppf_metres": ("lisiere_foret", "cours_d_eau", "route"),
        "zonage_et_dangers": ("pente_max_autorisee_pourcentage", "penalite_isos", "exclure_dangers_naturels", "exclure_acces_complique"),
    }.items():
        if not isinstance(cfg[section], dict) or set(cfg[section]) != set(keys):
            raise ValueError(f"criteres.json: section invalide {section}")
    numeric = [cfg["surface_min_m2"], cfg["emprise_max"]]
    for name in ("surface_parcelle", "zone_reservee_pleine_terre", "ratio_sous_exploitation_rd", "reculs_rdppf_metres"):
        numeric.extend(cfg[name].values())
    numeric.append(cfg["zonage_et_dangers"]["pente_max_autorisee_pourcentage"])
    if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in numeric):
        raise ValueError("Les seuils doivent être des nombres finis positifs ou nuls")
    if cfg["emprise_max"] > 1:
        raise ValueError("emprise_max est une proportion 0..1")
    if any(v > 100 for v in cfg["zone_reservee_pleine_terre"].values()):
        raise ValueError("Les seuils de pleine terre sont des pourcentages 0..100")
    if any(v > 1 for v in cfg["ratio_sous_exploitation_rd"].values()):
        raise ValueError("Le ratio RD doit être compris entre 0 et 1")
    notes = cfg["patrimoine_recensement"]["notes_exclues"]
    if not isinstance(notes, list) or any(type(n) is not int for n in notes):
        raise ValueError("notes_exclues doit être une liste d'entiers")
    for key in ("penalite_isos", "exclure_dangers_naturels", "exclure_acces_complique"):
        if type(cfg["zonage_et_dangers"][key]) is not bool:
            raise ValueError(f"{key} doit être un booléen")


def load_criteria(path: str | Path = DEFAULT_CONFIG) -> dict:
    with Path(path).open(encoding="utf-8-sig") as f:
        result = json.load(f)
    validate_config(result)
    return result


def _heritage_blocked(row: dict, notes: list[int]) -> bool | None:
    """Use recorded note arrays; shortcut summary flags only for notes 1,2,3."""
    sources = (
        "notes_batiment_existante_json", "notes_batiment_provisoire_json",
        "notes_site_existante_json", "notes_site_provisoire_json",
    )
    known = False
    for key in sources:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        try:
            note_list = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(note_list, list):
            continue
        known = True
        if any(number(n) in notes for n in note_list):
            return True
    if set(notes) == {1, 2, 3}:
        flag_keys = (
            "presence_note_1_3_batiment_existante", "presence_note_1_3_batiment_provisoire",
            "presence_note_1_3_site_existante", "presence_note_1_3_site_provisoire",
        )
        states = [flag(row.get(key)) for key in flag_keys]
        if True in states:
            return True
        if all(v is False for v in states):
            return False
    return False if known else None


# Zoning is a fixed eliminatory rule (not a configurable score).
# Only these three zoning designations are eligible, irrespective of accents or case.
ALLOWED_ZONES = {
    "zone de faible densite",
    "zone de moyenne densite",
    "zone de villas",
}


def normalized_zone(raw: Any) -> str | None:
    """Normalize zoning labels without conflating distinct zoning categories."""
    if raw is None or not str(raw).strip():
        return None
    label = unicodedata.normalize("NFKD", str(raw).strip().casefold())
    label = "".join(char for char in label if not unicodedata.combining(char))
    label = " ".join(label.split())
    return label


def eligible_zone(row: dict) -> bool | None:
    """Check the parcel's dominant zone; unknown is not a confirmed exclusion.

    Do not fall back to a minor intersecting zone: the eligible category must be
    the parcel's dominant zone. This prevents a forest/industrial parcel from
    qualifying merely because it overlaps a small residential area.
    """
    label = normalized_zone(pick(row, "zone_dominante"))
    return None if label is None else label in ALLOWED_ZONES


# Informations prouvables depuis pully_parcelles.csv ; aucun registre externe.
# Les indicateurs cadastraux sont descriptifs. Les alertes forestières
# (intersection ou voisinage proxy) peuvent modifier vert -> jaune.
INDICATOR_FIELDS = [
    "genre_parcelle", "domaine_cadastral", "domaine_public_communal",
    "domaine_public_cantonal", "proprietaire_communal_confirme",
    "nombre_batiments", "emprise_batie_m2", "emprise_batie_pct",
    "surface_hors_emprise_m2", "surface_verte_cartographiee_m2",
    "surface_verte_cartographiee_pct", "surface_dure_cartographiee_m2",
    "surface_dure_cartographiee_pct", "intersection_foret",
    "surface_intersection_foret_m2", "part_intersection_foret_pct",
    "intersection_eaux", "surface_intersection_eaux_m2",
    "part_intersection_eaux_pct", "distance_lisiere_foret_m",
    "distance_cours_d_eau_m", "source_indicateurs",
    "voisine_parcelle_avec_foret", "distance_parcelle_forestiere_m",
    "egrid_voisin_forestier", "methode_voisinage_foret",
    "bordure_foret_confirmee",
]


def csv_indicators(row: dict) -> dict:
    """Mesures et catégories cadastrales directement établies par le CSV.

    Une intersection positive signifie une distance géométrique de 0 m entre
    parcelle et objet intersecté, mais le CSV ne permet PAS de mesurer une
    distance non nulle ni de conclure sur la propriété juridique du terrain.
    """
    type_key = normalized_zone(pick(row, "genre_parcelle"))
    domains = {
        "parcelle privee": ("Privé (catégorie cadastrale)", "Non", "Non"),
        "dp communal": ("Communal (domaine public)", "Oui", "Non"),
        "dp cantonal": ("Cantonal (domaine public)", "Non", "Oui"),
        "ddp superficie": ("DDP superficie (domaine non déterminé)", "Indéterminé", "Indéterminé"),
    }
    domain, commune, canton = domains.get(type_key, ("Indéterminé", "Indéterminé", "Indéterminé"))
    area = number(pick(row, "surface_geometrique_m2"))
    if area is not None and area <= 0:
        area = None
    footprint = number(pick(row, "emprise_batie_m2"))
    green = number(pick(row, "sigip_surfaces_vertes_surface_intersection_m2"))
    hard = number(pick(row, "sigip_surfaces_dures_surface_intersection_m2"))
    forest = number(pick(row, "sigip_forets_surface_intersection_m2"))
    water = number(pick(row, "sigip_eaux_surface_intersection_m2"))
    count = number(pick(row, "batiments_nombre"))
    outside = number(pick(row, "surface_hors_emprise_batiments_m2"))

    def pct(v: float | None) -> float | None:
        return round(100 * v / area, 2) if v is not None and area is not None and v >= 0 else None

    def yes_no(v: float | None) -> str:
        return "Inconnu" if v is None or v < 0 else ("Oui" if v > 0 else "Non")

    def measured(v: float | None) -> float | None:
        return round(v, 2) if v is not None and v >= 0 else None

    coverage = pct(footprint) if (area is not None and footprint is not None and 0 <= footprint <= area) else None
    # Les distances hors intersection ne sont pas déductibles du CSV.
    forest_dist = 0.0 if forest is not None and forest > 0 else None
    water_dist = 0.0 if water is not None and water > 0 else None
    return {
        "genre_parcelle": pick(row, "genre_parcelle"),
        "domaine_cadastral": domain,
        "domaine_public_communal": commune,
        "domaine_public_cantonal": canton,
        "proprietaire_communal_confirme": "Non établi",
        "nombre_batiments": int(count) if count is not None and count >= 0 else None,
        "emprise_batie_m2": measured(footprint),
        "emprise_batie_pct": coverage,
        "surface_hors_emprise_m2": measured(outside),
        "surface_verte_cartographiee_m2": measured(green),
        "surface_verte_cartographiee_pct": pct(green),
        "surface_dure_cartographiee_m2": measured(hard),
        "surface_dure_cartographiee_pct": pct(hard),
        "intersection_foret": yes_no(forest),
        "surface_intersection_foret_m2": measured(forest),
        "part_intersection_foret_pct": pct(forest),
        "intersection_eaux": yes_no(water),
        "surface_intersection_eaux_m2": measured(water),
        "part_intersection_eaux_pct": pct(water),
        "distance_lisiere_foret_m": forest_dist,
        "distance_cours_d_eau_m": water_dist,
        "source_indicateurs": "pully_parcelles.csv",
    }



def compute_forest_neighbor_index(rows: list[dict], contours_path: Path,
                                  tolerance_m: float = 1.0) -> dict[str, dict]:
    """Conservative proximity *proxy* based on parcel polygons, NOT forest borders.

    Parcel contours are WGS84 GeoJSON. Project to Swiss LV95 (metres) before
    measuring. A neighbouring cadastral parcel whose CSV forest-overlap area is
    positive is a signal for caution; its actual forest may be on the other side
    of that parcel. Never label the result a forest-boundary distance.

    Requires shapely>=2 and pyproj. Does not download external data.
    """
    if tolerance_m < 0 or not math.isfinite(tolerance_m):
        raise ValueError("tolerance_m doit être un nombre >= 0")
    try:
        from shapely.geometry import shape
        from shapely.ops import transform
        from shapely.strtree import STRtree
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("Pour --contours: pip install shapely pyproj") from exc

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
    with contours_path.open(encoding="utf-8") as f:
        collection = json.load(f)
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Le fichier des contours doit être un FeatureCollection GeoJSON WGS84")
    source = {}
    for r in rows:
        egrid = str(r.get("egrid", "")).strip()
        forest = number(r.get("sigip_forets_surface_intersection_m2"))
        if egrid:
            source[egrid] = forest
    geometries = {}
    for feat in collection.get("features", []):
        egrid = str((feat.get("properties") or {}).get("egrid") or "").strip()
        if egrid not in source or not feat.get("geometry"):
            continue
        geom = transform(transformer.transform, shape(feat["geometry"]))
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            continue
        if egrid in geometries:
            geometries[egrid] = geometries[egrid].union(geom)
        else:
            geometries[egrid] = geom

    forest_egrids = [e for e, g in geometries.items() if source.get(e) is not None and source[e] > 0]
    forest_geoms = [geometries[e] for e in forest_egrids]
    tree = STRtree(forest_geoms) if forest_geoms else None
    result = {}
    for egrid, overlap in source.items():
        if overlap is not None and overlap > 0:
            result[egrid] = {"voisine_parcelle_avec_foret": "Sans objet (intersection sur parcelle)",
                             "distance_parcelle_forestiere_m": None,
                             "egrid_voisin_forestier": "", "methode_voisinage_foret": "intersection CSV"}
            continue
        if egrid not in geometries:
            result[egrid] = {"voisine_parcelle_avec_foret": "Inconnu (contour absent)",
                             "distance_parcelle_forestiere_m": None,
                             "egrid_voisin_forestier": "", "methode_voisinage_foret": "contour absent"}
            continue
        current = geometries[egrid]
        best = (float("inf"), "")
        if tree is not None:
            search = current.buffer(tolerance_m) if tolerance_m else current
            for i in tree.query(search):
                j = int(i)
                if forest_egrids[j] == egrid:
                    continue
                d = current.distance(forest_geoms[j])
                if d <= tolerance_m and d < best[0]:
                    best = (d, forest_egrids[j])
        has_neighbor = bool(best[1])
        result[egrid] = {
            "voisine_parcelle_avec_foret": "Oui" if has_neighbor else "Non détectée (dans le jeu de données)",
            "distance_parcelle_forestiere_m": round(best[0], 2) if has_neighbor else None,
            "egrid_voisin_forestier": best[1],
            "methode_voisinage_foret": f"proxy: contour voisin avec intersection forêt CSV, distance <= {tolerance_m:g} m",
        }
    return result

def evaluate_parcel(row: dict, cfg: dict, slope_row: dict | None = None,
                    forest_neighbor_info: dict | None = None) -> dict:
    """Evaluate a cadastral row and optional slope row against *all* JSON criteria.

    Each check returns ``ok``, ``echec``, ``inconnu``, ``alerte``, ``note``, or ``sans_objet``.
    ``obligatoire`` indicates a hard filter (unknown makes overall status grey).
    Coverage and pleine-terre thresholds are evaluation criteria, not exclusions.
    Water and road setbacks are advisory notes only. Forest overlap and
    adjacency to a forest-overlapping PARCEL (proxy) trigger yellow caution.
    Measured positive forest intersection additionally makes an otherwise-green parcel yellow.
    The configurable risk/access flags are only used with explicit observations.
    """
    validate_config(cfg)
    checks: dict[str, dict] = {}

    def add(key: str, label: str, actual: Any, threshold: Any, state: str,
            mandatory: bool = False, detail: str = "") -> None:
        checks[key] = dict(label=label, valeur=actual, seuil=threshold, etat=state,
                           obligatoire=mandatory, detail=detail)

    zoning = eligible_zone(row)
    add(
        "zonage_residentiel", "Zone autorisée (faible densité, moyenne densité, villas)",
        pick(row, "zone_dominante"), sorted(ALLOWED_ZONES),
        "inconnu" if zoning is None else "ok" if zoning else "echec",
        True,
        "Toute autre zone dominante est éliminatoire (rouge).",
    )

    def minimum(key: str, label: str, value: float | None, threshold: float, mandatory: bool = True):
        add(key, label, value, threshold, "inconnu" if value is None else "ok" if value >= threshold else "echec", mandatory)

    def maximum(key: str, label: str, value: float | None, threshold: float, mandatory: bool = True):
        add(key, label, value, threshold, "inconnu" if value is None else "ok" if value <= threshold else "echec", mandatory)

    area = number(pick(row, "surface_geometrique_m2", "surface_parcelle_m2"))
    if area is not None and area <= 0:
        area = None
    footprint = number(pick(row, "emprise_batie_m2", "emprise_cadastrale_m2"))
    coverage = None if area is None or footprint is None or not 0 <= footprint <= area else footprint / area
    minimum("surface_min_m2", "Surface de parcelle minimale (m²)", area, cfg["surface_min_m2"])
    maximum("emprise_max", "Rapport emprise bâtie / parcelle", coverage, cfg["emprise_max"], False)

    # Area tiers are purely informational and never create a red exclusion.
    tiers = cfg["surface_parcelle"]
    minimum("surface_fort_potentiel_m2", "Surface: seuil fort potentiel", area, tiers["seuil_fort_potentiel_m2"], False)
    minimum("surface_moyen_potentiel_m2", "Surface: seuil moyen potentiel", area, tiers["seuil_moyen_potentiel_m2"], False)

    heritage = _heritage_blocked(row, cfg["patrimoine_recensement"]["notes_exclues"])
    add("patrimoine", "Note architecturale interdite", heritage,
        cfg["patrimoine_recensement"]["notes_exclues"],
        "inconnu" if heritage is None else "echec" if heritage else "ok", True)

    earth_area = number(pick(row, "pleine_terre_reglementaire_m2"))
    earth_pct = number(pick(row, "pleine_terre_pct", "zone_reservee_pleine_terre_pct"))
    if earth_pct is None and earth_area is not None and area is not None and 0 <= earth_area <= area:
        earth_pct = 100 * earth_area / area
    if earth_pct is not None and not 0 <= earth_pct <= 100:
        earth_pct = None
    earth_cfg = cfg["zone_reservee_pleine_terre"]
    minimum("pleine_terre_exclusion", "Pleine terre minimale (%)", earth_pct,
            earth_cfg["seuil_exclusion_pourcentage"], False)
    add("pleine_terre_malus", "Alerte pleine terre (%)", earth_pct,
        earth_cfg["seuil_malus_pourcentage"],
        "inconnu" if earth_pct is None else "alerte" if earth_pct < earth_cfg["seuil_malus_pourcentage"] else "ok", False)

    # Ratio RD: only explicitly supplied validated ratios. Do not confuse with
    # cadastral coverage (footprint / parcel area).
    ratio = number(pick(row, "ratio_sous_exploitation_rd", "ratio_emprise_sur_maximum_simule"))
    if ratio is not None and not 0 <= ratio <= 1:
        ratio = None
    ratio_cfg = cfg["ratio_sous_exploitation_rd"]
    maximum("ratio_rd_fort", "Ratio d'occupation RD, seuil fort", ratio,
            ratio_cfg["seuil_fort_potentiel"], False)
    maximum("ratio_rd_moyen", "Ratio d'occupation RD, seuil moyen", ratio,
            ratio_cfg["seuil_moyen_potentiel"], False)


    # These are measured distances, except a proven polygon intersection gives 0 m.
    distances = (
        ("lisiere_foret", "distance_lisiere_foret_m", "Distance à la lisière de forêt (m)"),
        ("cours_d_eau", "distance_cours_d_eau_m", "Distance au cours d'eau (m)"),
        ("route", "recul_route_m", "Recul depuis la route (m)"),
    )
    for key, field, label in distances:
        value = number(pick(row, field))
        if value is not None and value < 0:
            value = None
        if value is None and key in ("lisiere_foret", "cours_d_eau"):
            # A positive recorded intersection proves geometric distance 0 m.
            # Zero overlap never proves the forest/watercourse is far away.
            overlap_field = ("sigip_forets_surface_intersection_m2" if key == "lisiere_foret"
                             else "sigip_eaux_surface_intersection_m2")
            overlap = number(pick(row, overlap_field))
            if overlap is not None and overlap > 0:
                value = 0.0
        threshold = cfg["reculs_rdppf_metres"][key]
        add(
            "recul_" + key, label, value, threshold,
            "inconnu" if value is None else "note" if value < threshold else "ok",
            False,
            "Recul indicatif à vérifier selon les règles applicables; non éliminatoire.",
        )

    slope_data = slope_row or {}
    slope = number(pick(slope_data, "pente_mediane_pct"))
    valid = str(slope_data.get("statut_calcul", "")).strip() in ("calcule", "calcule_a_verifier")
    if slope is None or not valid or slope < 0:
        slope = number(pick(row, "pente_mediane_pct", "pente_pct"))
    if slope is not None and slope < 0:
        slope = None
    maximum("pente_max", "Pente médiane maximale (%)", slope,
            cfg["zonage_et_dangers"]["pente_max_autorisee_pourcentage"])

    zone_cfg = cfg["zonage_et_dangers"]
    isos = flag(pick(row, "isos_present", "dans_perimetre_isos"))
    add("isos", "Présence ISOS (alerte)", isos, zone_cfg["penalite_isos"],
        "sans_objet" if not zone_cfg["penalite_isos"] else
        "inconnu" if isos is None else "alerte" if isos else "ok", False)

    danger = flag(pick(row, "danger_naturel_bloquant", "blocking_natural_hazard"))
    add("dangers_naturels", "Danger naturel bloquant", danger,
        zone_cfg["exclure_dangers_naturels"],
        "sans_objet" if not zone_cfg["exclure_dangers_naturels"] else
        "inconnu" if danger is None else "echec" if danger else "ok",
        zone_cfg["exclure_dangers_naturels"])

    access = flag(pick(row, "acces_complique", "complicated_access"))
    if access is None:
        road_access = flag(pick(row, "road_access_ok"))
        access = None if road_access is None else not road_access
    add("acces_complique", "Accès compliqué vérifié", access,
        zone_cfg["exclure_acces_complique"],
        "sans_objet" if not zone_cfg["exclure_acces_complique"] else
        "inconnu" if access is None else "echec" if access else "ok",
        zone_cfg["exclure_acces_complique"])

    # Forest intersection: screening alert, not a confirmed legal exclusion.
    # Only a strictly positive observed area proves intersection; missing data
    # does not by itself change an otherwise-green parcel to yellow.
    forest_area = number(pick(row, "sigip_forets_surface_intersection_m2"))
    forest_intersects = forest_area is not None and forest_area > 0
    add(
        "intersection_foret", "Intersection avec la forêt (surface mesurée)",
        forest_area if forest_area is not None and forest_area >= 0 else None,
        0,
        "alerte" if forest_intersects else "inconnu" if forest_area is None or forest_area < 0 else "ok",
        False,
        "Intersection positive : vigilance forestière, classement jaune sauf exclusion rouge.",
    )

    # Mesure de voisinage cadastrale = INDICE, pas lisière forestière prouvée.
    neighbor = forest_neighbor_info or {}
    near_forest_parcel = neighbor.get("voisine_parcelle_avec_foret") == "Oui"
    add(
        "voisin_parcelle_forestiere", "Voisin d'une parcelle contenant de la forêt (indice)",
        neighbor.get("distance_parcelle_forestiere_m"), None,
        "alerte" if near_forest_parcel else "inconnu" if not neighbor or
        str(neighbor.get("voisine_parcelle_avec_foret", "")).startswith("Inconnu") else "ok",
        False,
        "Distance entre contours cadastraux, NON distance à la forêt. Alerte jaune de précaution.",
    )

    failed = [k for k, v in checks.items() if v["etat"] == "echec" and v["obligatoire"]]
    unknown = [k for k, v in checks.items() if v["etat"] == "inconnu" and v["obligatoire"]]
    alerts = [k for k, v in checks.items() if v["etat"] == "alerte"]
    evaluation_unfavorable = [k for k, v in checks.items()
                              if v["etat"] == "echec" and not v["obligatoire"]]
    advisory_notes = [k for k, v in checks.items() if v["etat"] == "note"]

    # Area remains exclusively eliminatory; coverage + forest affect green/yellow.
    evaluation_keys = ["emprise_max"]

    if failed:
        status = "rouge"
    elif unknown or forest_intersects or near_forest_parcel:
        status = "jaune"
    elif all(checks[key]["etat"] == "ok" for key in evaluation_keys):
        status = "vert"
    else:
        status = "jaune"
    return {
        "egrid": row.get("egrid", ""), "numero_parcelle": row.get("numero_parcelle", ""),
        "statut_filtrage_criteres": status, "filtres": checks,
        "filtres_echoues": failed, "filtres_inconnus": unknown, "alertes": alerts,
        "criteres_evaluation_defavorables": evaluation_unfavorable, "notes_reglementaires": advisory_notes,
        "zone_dominante": pick(row, "zone_dominante"), "surface_m2": area, "emprise_ratio": coverage, "pleine_terre_pct": earth_pct,
        "ratio_rd": ratio, "pente_mediane_pct": slope,
        **csv_indicators(row),
        **{k: neighbor.get(k) for k in ("voisine_parcelle_avec_foret",
            "distance_parcelle_forestiere_m", "egrid_voisin_forestier", "methode_voisinage_foret")},
        "bordure_foret_confirmee": "Inconnu (pas de géométrie forestière)",
    }


def run(input_csv: Path = DEFAULT_DATA, config: Path = DEFAULT_CONFIG,
        slopes_csv: Path | None = DEFAULT_SLOPES, output: Path | None = None,
        contours_geojson: Path | None = DEFAULT_CONTOURS,
        tolerance_voisin_m: float = 1.0) -> dict:
    cfg = load_criteria(config)
    slope_index: dict[str, dict] = {}
    if slopes_csv is not None and slopes_csv.exists():
        with slopes_csv.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("egrid"):
                    slope_index[r["egrid"]] = r
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    neighbor_index = {}
    geometry_used = bool(contours_geojson is not None and contours_geojson.is_file())
    if geometry_used:
        neighbor_index = compute_forest_neighbor_index(rows, contours_geojson, tolerance_voisin_m)
    results = [evaluate_parcel(r, cfg, slope_index.get(r.get("egrid")),
                               neighbor_index.get(r.get("egrid"))) for r in rows]
    summary = {"total": len(results), "effectifs": dict(Counter(r["statut_filtrage_criteres"] for r in results)),
               "voisinage_calcule": geometry_used,
               "nombre_voisins_parcelles_forestieres": sum(r["voisine_parcelle_avec_foret"] == "Oui" for r in results),
               "regle": "Rouge: exclusion confirmée; jaune: inconnus obligatoires, emprise défavorable, intersection de forêt ou voisin d'une parcelle avec forêt (proxy, si contours disponibles); vert: autres critères favorables"}
    if output is not None:
        if output.resolve() in {input_csv.resolve(), config.resolve()}:
            raise ValueError("La sortie ne peut pas écraser une entrée")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["egrid", "numero_parcelle", "zone_dominante", "statut_filtrage_criteres", "filtres_echoues", "filtres_inconnus", "alertes", "criteres_evaluation_defavorables", "notes_reglementaires", "filtres", "surface_m2", "emprise_ratio", "pleine_terre_pct", "ratio_rd", "pente_mediane_pct"] + INDICATOR_FIELDS
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow({k: json.dumps(r[k], ensure_ascii=False) if isinstance(r[k], (list, dict)) else r[k] for k in fields})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--pentes", type=Path, default=DEFAULT_SLOPES)
    parser.add_argument("--output", type=Path, default=Path("code/resultats_criteres_category.csv"))
    parser.add_argument("--contours", type=Path, default=DEFAULT_CONTOURS,
                        help="GeoJSON contours cadastraux WGS84; absent = pas de voisinage calculé")
    parser.add_argument("--tolerance-voisin-m", type=float, default=1.0,
                        help="Tolérance entre contours cadastraux, en mètres (défaut: 1)")
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.config, args.pentes, args.output,
                             args.contours, args.tolerance_voisin_m), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
