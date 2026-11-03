"""Présélection explicable de parcelles de Pully depuis le CSV existant.

Python 3.10+, bibliothèque standard uniquement. Exécution hors ligne.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Criteria:
    surface_min_m2: float = 1000
    emprise_max: float = 0.20
    logements_max: int = 3

    def validate(self) -> None:
        values = (self.surface_min_m2, self.emprise_max, self.logements_max)
        if not all(type(value) in (int, float) and math.isfinite(value) for value in values):
            raise ValueError("Les seuils doivent être des nombres finis.")
        if self.surface_min_m2 < 0 or not 0 < self.emprise_max <= 1:
            raise ValueError("Surface minimale positive ou nulle, emprise entre 0 exclu et 1 inclus.")
        if self.logements_max < 1 or int(self.logements_max) != self.logements_max:
            raise ValueError("logements_max doit être un entier positif.")


# Chaque groupe doit être présent dans le schéma pour permettre son contrôle.
# La couche ponctuelle est examinée lorsqu'elle est disponible.
HERITAGE_SOURCES = (
    ("batiment_existant", "notes_batiment_existante_json", "sigip_rec_arch_s_json", "note_detail"),
    ("batiment_provisoire", "notes_batiment_provisoire_json", "sigip_pully_recensement_provisoire_batiments_json", "note_provisoire"),
    ("site_existant", "notes_site_existante_json", "sigip_rec_arch_site_json", "note_carto"),
    ("site_provisoire", "notes_site_provisoire_json", "sigip_pully_recensement_provisoire_sites_json", "note_provisoire"),
    ("objet_ponctuel", None, "sigip_rec_arch_p_json", "note_detail"),
)
BLOCKING_FLAGS = (
    "presence_note_1_3_batiment_existante",
    "presence_note_1_3_batiment_provisoire",
    "presence_note_1_3_site_existante",
    "presence_note_1_3_site_provisoire",
)
FILES = {
    "exclue_patrimoine": "exclusions_patrimoine.csv",
    "a_verifier_donnees": "anomalies_a_verifier.csv",
    "hors_cible_exploratoire": "hors_cible_exploratoire.csv",
    "candidate_a_approfondir": "candidates_a_approfondir.csv",
}
FIELDS = (
    "egrid", "numero_parcelle", "statut", "motifs_json", "preuves_patrimoine_json",
    "anomalies_json", "verifications_restantes_json", "surface_geometrique_m2",
    "emprise_batie_m2", "taux_emprise_calcule", "batiments_nombre",
    "logements_rattachement_declare", "logements_objets_renseignes", "logements_objets_total",
    "zone_dominante_source", "zone_reservee_detectee", "aucune_note_interpretable_detectee",
    "url_rdppf", "url_extrait_rdppf", "decision_conti", "motif_conti",
)


def numeric(value: object) -> float | None:
    if value is None or str(value).strip().lower() in ("", "nan", "null", "none"):
        return None
    try:
        result = float(str(value).strip())
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def json_array(row: dict, field: str, issues: list[str]) -> list:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        issues.append(f"Champ JSON manquant ou vide : {field}")
        return []
    try:
        result = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        issues.append(f"JSON illisible : {field}")
        return []
    if not isinstance(result, list):
        issues.append(f"Une liste JSON est attendue : {field}")
        return []
    return result


def heritage(row: dict, issues: list[str]) -> list[dict]:
    evidence = []
    for source, summary, details, attribute in HERITAGE_SOURCES:
        observations = []
        if summary and summary in row:
            observations.extend((value, None) for value in json_array(row, summary, issues))
        if details in row:
            for record in json_array(row, details, issues):
                if not isinstance(record, dict):
                    issues.append(f"Objet patrimonial illisible : {details}")
                    continue
                identifier = record.get("num_eca") or record.get("fiche") or record.get("gml_id")
                observations.append((record.get(attribute), identifier))
                if attribute != "note_carto" and record.get("note_carto") is not None:
                    observations.append((record["note_carto"], identifier))
        for value, identifier in observations:
            # Accepte les notes numériques et les mentions courantes 3V / 3 provisoire.
            match = re.fullmatch(r"\s*([1-7])(?:\.0+)?(?:\s*[vV]|\s+provisoire)?\s*", str(value))
            if not match:
                issues.append(f"Note à clarifier ({source}, objet {identifier}) : {value!r}")
                continue
            evidence.append({"source": source, "objet": identifier, "note": int(match.group(1)), "valeur_source": value})
    for field in BLOCKING_FLAGS:
        if field not in row:
            continue
        value = str(row[field]).strip().lower()
        if value in ("true", "1"):
            evidence.append({"source": field, "objet": None, "note": None, "indicateur_bloquant": True})
        elif value not in ("false", "0"):
            issues.append(f"Indicateur patrimonial à clarifier : {field}={row[field]!r}")
    return evidence


def parcel_identifier(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".")[0]
    return text


def dwelling_count(row: dict, issues: list[str]) -> tuple[float | None, int, int]:
    records = json_array(row, "sigip_rcb_bat_json", issues)
    seen = set()
    total = 0.0
    known = 0
    matched = 0
    for record in records:
        if not isinstance(record, dict):
            issues.append("Objet RCB illisible")
            continue
        egid = record.get("egid")
        if egid is None or str(egid).strip() == "":
            issues.append("Identifiant EGID manquant dans le RCB")
        elif str(egid) in seen:
            issues.append(f"EGID en double dans le RCB : {egid}")
            continue
        else:
            seen.add(str(egid))
        declared = parcel_identifier(record.get("parcelle"))
        if declared != parcel_identifier(row.get("numero_parcelle")):
            issues.append(f"Rattachement RCB divergent : EGID {egid}, parcelle déclarée {declared or 'inconnue'}")
            continue
        if record.get("statut") != "existant":
            issues.append(f"Statut RCB à examiner : EGID {egid}, {record.get('statut')!r}")
            continue
        matched += 1
        count = numeric(record.get("nbre_logements"))
        if count is None or count < 0 or not count.is_integer():
            issues.append(f"Nombre de logements à vérifier : EGID {egid}")
            continue
        total += count
        known += 1
    if not records:
        issues.append("Aucun objet RCB associé à la parcelle")
    return (total if known else None, known, matched)


def analyse(row: dict, criteria: Criteria) -> dict:
    issues: list[str] = []
    evidence = heritage(row, issues)
    excluded = any(item.get("indicateur_bloquant") or item.get("note") in (1, 2, 3) for item in evidence)
    surface = numeric(row.get("surface_geometrique_m2"))
    footprint = numeric(row.get("emprise_batie_m2"))
    buildings = numeric(row.get("batiments_nombre"))
    ratio = None
    if surface is None or surface <= 0 or footprint is None or not 0 <= footprint <= surface:
        issues.append("Surface parcellaire ou emprise manquante ou incohérente")
    else:
        ratio = footprint / surface
        source_ratio = numeric(row.get("taux_emprise_geometrique"))
        if source_ratio is None or abs(ratio - source_ratio) > 0.001:
            issues.append("Taux d’emprise source incohérent avec les surfaces")
    if buildings is None or buildings < 0 or not buildings.is_integer():
        issues.append("Nombre d’objets bâtiments manquant ou incohérent")
    logements, known, matched = dwelling_count(row, issues)
    zone = str(row.get("zone_dominante") or "").strip()
    if not zone:
        issues.append("Zone dominante absente")
    zone_share = numeric(row.get("zone_dominante_part_surface"))
    if zone_share is None or not 0.99 <= zone_share <= 1.001:
        issues.append("Zone dominante couvrant moins de 99 % ou couverture inconnue/incohérente")

    outside = []
    if surface is not None and surface < criteria.surface_min_m2:
        outside.append(f"Terrain inférieur au seuil exploratoire de {criteria.surface_min_m2:g} m²")
    if ratio is not None and ratio > criteria.emprise_max:
        outside.append(f"Emprise supérieure au seuil exploratoire de {criteria.emprise_max:.0%}")
    if logements is not None and logements > criteria.logements_max:
        outside.append(f"Plus de {criteria.logements_max} logements renseignés")
    if buildings == 0 or logements == 0:
        outside.append("La cible exploratoire demande un bâtiment avec au moins un logement renseigné")

    if excluded:
        status = "exclue_patrimoine"
        reasons = ["Note 1, 2 ou 3 détectée sur un bâtiment, un objet ou un site, y compris provisoire"]
    elif issues:
        status = "a_verifier_donnees"
        reasons = ["Clarifier les données avant la présélection"] + outside
    elif outside:
        status = "hors_cible_exploratoire"
        reasons = outside
    else:
        status = "candidate_a_approfondir"
        reasons = [f"Terrain de {surface:.1f} m², emprise de {ratio:.1%}, {logements:g} logement(s) renseigné(s)",
                   "Aucune note 1 à 3 détectée dans les couches patrimoniales fournies"]

    remaining = [
        "Confirmer le recensement et les mesures de protection actuels auprès des sources officielles",
        "Croiser les périmètres ISOS et leurs objectifs de sauvegarde",
        "Confirmer les plans applicables, leurs périmètres et le statut de la zone réservée",
        "Vérifier densité, hauteur et surface bâtie déterminante selon le règlement",
        "Calculer l’enveloppe disponible selon la forme, les distances aux limites et entre bâtiments",
        "Mesurer la pente depuis un modèle numérique de terrain",
        "Vérifier l’accès réel, le réseau routier et les droits de passage",
        "Vérifier la pleine terre, le sous-sol et les arbres protégés",
        "Contrôler les limites routières, le bruit, les eaux et les dangers naturels",
        "Faire qualifier l’intérêt commercial et le type de bâti par Conti",
    ]
    return {
        "egrid": row["egrid"], "numero_parcelle": row["numero_parcelle"], "statut": status,
        "motifs_json": reasons, "preuves_patrimoine_json": evidence,
        "anomalies_json": list(dict.fromkeys(issues)), "verifications_restantes_json": remaining,
        "surface_geometrique_m2": surface, "emprise_batie_m2": footprint,
        "taux_emprise_calcule": ratio, "batiments_nombre": buildings,
        "logements_rattachement_declare": logements, "logements_objets_renseignes": known,
        "logements_objets_total": matched, "zone_dominante_source": zone,
        "zone_reservee_detectee": None if numeric(row.get("sigip_zone_reservee_nombre")) is None else numeric(row["sigip_zone_reservee_nombre"]) > 0,
        "aucune_note_interpretable_detectee": not evidence,
        "url_rdppf": row.get("url_rdppf", ""), "url_extrait_rdppf": row.get("url_extrait_rdppf", ""),
        "decision_conti": row.get("decision_conti", ""), "motif_conti": row.get("motif_conti", ""),
    }


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        required = {"egrid", "numero_parcelle", "surface_geometrique_m2", "emprise_batie_m2",
                    "batiments_nombre", "sigip_rcb_bat_json", "zone_dominante", "zone_dominante_part_surface"}
        missing = required - fields
        for _, summary, details, _ in HERITAGE_SOURCES[:4]:
            if summary not in fields and details not in fields:
                missing.add(f"{summary} ou {details}")
        if missing:
            raise ValueError("Colonnes requises absentes : " + ", ".join(sorted(missing)))
        rows = list(reader)
    if not rows:
        raise ValueError("Le CSV ne contient aucune parcelle.")
    identifiers = [row["egrid"].strip() for row in rows]
    if not all(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Les EGRID doivent être renseignés et uniques.")
    if any(not row["numero_parcelle"].strip() for row in rows):
        raise ValueError("Numéro de parcelle manquant.")
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                             for key, value in row.items()})


def run(input_path: Path, output_dir: Path, criteria: Criteria) -> dict:
    criteria.validate()
    rows = load_rows(input_path)
    results = [analyse(row, criteria) for row in rows]
    candidates = sorted((row for row in results if row["statut"] == "candidate_a_approfondir"),
                        key=lambda row: (row["taux_emprise_calcule"], -row["surface_geometrique_m2"], row["egrid"]))
    counts = Counter(row["statut"] for row in results)
    summary = {
        "date_execution_utc": datetime.now(timezone.utc).isoformat(),
        "fichier_source": str(input_path.resolve()),
        "sha256_source": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "date_modification_fichier_source_utc": datetime.fromtimestamp(input_path.stat().st_mtime, timezone.utc).isoformat(),
        "criteres_exploratoires": asdict(criteria), "parcelles_total": len(results),
        "effectifs": {status: counts[status] for status in FILES},
        "ordre_candidates": "Emprise croissante, puis superficie décroissante et EGRID. Ordre exploratoire.",
        "statut_criteres_complementaires": "ISOS, pente, accès, enveloppe réglementaire et faisabilité à vérifier",
        "validation_humaine": "Les statuts générés doivent rester distincts des annotations de Conti.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if input_path.resolve().parent == output_dir.resolve() and input_path.name in (*FILES.values(), "audit_parcelles.csv"):
        raise ValueError("Le dossier de sortie écraserait le fichier source.")
    # Préparer tous les fichiers avant leur publication. Le résumé est publié en dernier.
    with tempfile.TemporaryDirectory(prefix="pully_", dir=output_dir) as temporary:
        staging = Path(temporary)
        write_csv(staging / "audit_parcelles.csv", results)
        for status, filename in FILES.items():
            subset = candidates if status == "candidate_a_approfondir" else [r for r in results if r["statut"] == status]
            write_csv(staging / filename, subset)
        (staging / "resume.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        for filename in ("audit_parcelles.csv", *FILES.values(), "resume.json"):
            os.replace(staging / filename, output_dir / filename)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV principal pully_parcelles.csv")
    parser.add_argument("--output", type=Path, default=Path("resultats"))
    parser.add_argument("--config", type=Path, help="Fichier JSON des seuils exploratoires")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config else {}
        summary = run(args.input, args.output, Criteria(**config))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Erreur : {error}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


// test, Marco