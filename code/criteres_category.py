"""Filtrage explicable des parcelles selon ``code/criteres.json``.

Module autonome (Python 3.10+, bibliothèque standard), compatible avec le dépôt
DIW26. Aucune écriture dans ``classification.py`` ou ``prospection.py``.

Les champs non établis (pleine terre, distances réglementaires, dangers, accès,
ISOS et ratio RD) ne sont JAMAIS supposés favorables. Le filtrage retourne :
``rouge`` si exclusion confirmée, ``jaune`` si information obligatoire
manquante ou couverture défavorable, et ``vert`` si toutes les règles actives passent.

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


def evaluate_parcel(row: dict, cfg: dict, slope_row: dict | None = None) -> dict:
    """Evaluate a cadastral row and optional slope row against *all* JSON criteria.

    Each check returns ``ok``, ``echec``, ``inconnu``, ``alerte``, ``note``, or ``sans_objet``.
    ``obligatoire`` indicates a hard filter (unknown makes overall status grey).
    Coverage and pleine-terre thresholds are evaluation criteria, not exclusions.
    Forest, water and road setbacks are advisory notes only.
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


    # These are measured *distances*, not layer intersection areas.
    distances = (
        ("lisiere_foret", "distance_lisiere_foret_m", "Distance à la lisière de forêt (m)"),
        ("cours_d_eau", "distance_cours_d_eau_m", "Distance au cours d'eau (m)"),
        ("route", "recul_route_m", "Recul depuis la route (m)"),
    )
    for key, field, label in distances:
        value = number(pick(row, field))
        if value is not None and value < 0:
            value = None
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

    failed = [k for k, v in checks.items() if v["etat"] == "echec" and v["obligatoire"]]
    unknown = [k for k, v in checks.items() if v["etat"] == "inconnu" and v["obligatoire"]]
    alerts = [k for k, v in checks.items() if v["etat"] == "alerte"]
    evaluation_unfavorable = [k for k, v in checks.items()
                              if v["etat"] == "echec" and not v["obligatoire"]]
    advisory_notes = [k for k, v in checks.items() if v["etat"] == "note"]

    # Only building coverage distinguishes green from yellow by default.
    # The 600 m² surface threshold remains exclusively eliminatory.
    evaluation_keys = ["emprise_max"]

    if failed:
        status = "rouge"
    elif unknown:
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
    }


def run(input_csv: Path = DEFAULT_DATA, config: Path = DEFAULT_CONFIG,
        slopes_csv: Path | None = DEFAULT_SLOPES, output: Path | None = None) -> dict:
    cfg = load_criteria(config)
    slope_index: dict[str, dict] = {}
    if slopes_csv is not None and slopes_csv.exists():
        with slopes_csv.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("egrid"):
                    slope_index[r["egrid"]] = r
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        results = [evaluate_parcel(r, cfg, slope_index.get(r.get("egrid"))) for r in csv.DictReader(f)]
    summary = {"total": len(results), "effectifs": dict(Counter(r["statut_filtrage_criteres"] for r in results)),
               "regle": "Rouge: exclusion confirmée; jaune: condition obligatoire inconnue ou couverture défavorable; vert: conditions vérifiées et couverture <= seuil"}
    if output is not None:
        if output.resolve() in {input_csv.resolve(), config.resolve()}:
            raise ValueError("La sortie ne peut pas écraser une entrée")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["egrid", "numero_parcelle", "zone_dominante", "statut_filtrage_criteres", "filtres_echoues", "filtres_inconnus", "alertes", "criteres_evaluation_defavorables", "notes_reglementaires", "filtres", "surface_m2", "emprise_ratio", "pleine_terre_pct", "ratio_rd", "pente_mediane_pct"]
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
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.config, args.pentes, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


