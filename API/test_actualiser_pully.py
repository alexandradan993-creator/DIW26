"""Tests hors ligne : les règles de calcul et le format d'écriture doivent
reproduire exactement la base de référence pully_parcelles.csv.

Usage : python test_actualiser_pully.py ../pully_parcelles.csv
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

import actualiser_pully as A

DERIVEES = [
    "emprise_batie_m2", "taux_emprise_geometrique", "surface_hors_emprise_batiments_m2",
    "zone_dominante", "zone_dominante_statut", "zone_dominante_part_surface",
    "cos_source_zone_dominante", "ius_source_zone_dominante",
    "rcb_nbre_logements_renseignes", "rcb_nbre_logements_somme",
    "rcb_nombre_niveaux_renseignes", "rcb_nombre_niveaux_max",
    "rcb_annee_construction_renseignes", "rcb_annee_construction_max",
    "rcb_surf_plancher_renseignes", "rcb_surf_plancher_somme",
] + [c for n in ("batiment_existante", "batiment_provisoire", "site_existante", "site_provisoire")
     for c in (f"notes_{n}_json", f"presence_note_1_3_{n}")]


def valeur(c, s):
    """Reconstruit la valeur Python d'une cellule de la référence."""
    if s == "":
        return None
    if c.endswith("_json"):
        return json.loads(s)
    if s in ("True", "False"):
        return s == "True"
    for t in (int, float):
        try:
            return t(s)
        except ValueError:
            pass
    return s


def main(ref):
    rows = list(csv.DictReader(open(ref, encoding="utf-8-sig", newline="")))
    assert list(rows[0]) == A.SCHEMA["colonnes"], "Colonnes du schéma différentes"

    # 1. Règles de calcul
    erreurs = {}
    lignes = []
    for r in rows:
        L = {c: valeur(c, r[c]) for c in r}
        brut = dict(L)
        A.deriver(L)
        for c in DERIVEES:
            attendu, obtenu = A.normaliser(r[c]), A.normaliser(A.cellule(L[c]))
            if c.startswith("notes_"):  # l'ordre compte pour les notes
                attendu, obtenu = r[c], A.cellule(L[c])
            if attendu != obtenu:
                erreurs.setdefault(c, []).append((r["numero_parcelle"], r[c], A.cellule(L[c])))
        lignes.append(brut)
    for c in DERIVEES:
        n = len(erreurs.get(c, []))
        print(f"{'OK ' if not n else 'KO '} {c:<45} {len(rows) - n}/{len(rows)}", erreurs.get(c, [])[:2])

    # 2. Format d'écriture : relire et réécrire doit redonner le fichier à l'identique
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "copie.csv"
        A.ecrire_csv(out, lignes)
        identique = out.read_bytes() == Path(ref).read_bytes()
        print(f"{'OK ' if identique else 'KO '} écriture CSV identique octet par octet")
        rapport = A.comparer(out, Path(ref))
        print(f"{'OK ' if rapport['modifiees'] == 0 else 'KO '} comparaison : {rapport['modifiees']} parcelles modifiées")

    # 3. Types : les services renvoient "3" au lieu de 3, 785307 au lieu de 785307.0,
    #    "2025-06-07" au lieu de "2025-06-07 00:00:00" (constaté au premier lancement réel)
    def degrader(v):
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str) and v.endswith(" 00:00:00"):
            return v[:10]
        return v
    ko = total = 0
    for r in rows:
        for c, cles in A.SCHEMA["cles_json"].items():
            for o in json.loads(r[c]):
                brut = {k: degrader(v) for k, v in o.items()}
                n = A.objet_json(cles, brut, o.get("surface_intersection_m2"), o.get("source_layer"),
                                 A.TYPES.get(c))
                total += 1
                ko += n != o
    print(f"{'OK ' if not ko else 'KO '} types rétablis comme la référence : {total - ko}/{total}")

    # 4. La comparaison « significative » ignore les identifiants SIGIP renumérotés
    a = '[{"gml_id": "rcb_bat.1", "surface": 156.0}]'
    b = '[{"gml_id": "rcb_bat.9", "surface": 156.004}]'
    print(f"{'OK ' if A.normaliser(a, True) == A.normaliser(b, True) else 'KO '} gml_id ignoré en comparaison significative")

    # 5. Extraction des URL
    o = A.objet_json(["lien", "source_layer", "surface_intersection_m2", "lien_urls"],
                     {"lien": "<a onclick=\"javascript:window.open('https://x.ch/a.pdf')\">ici</a>"}, 1.5, "zone_reservee")
    print(f"{'OK ' if o['lien_urls'] == ['https://x.ch/a.pdf'] else 'KO '} extraction des URL", o)
    print(f"{'OK ' if A.typer_wfs('2025-06-07T00:00:00', 'datetime') == '2025-06-07 00:00:00' else 'KO '} format des dates")
    print(f"{'OK ' if A.trouver_egrid({'URL_EXTRAIT_RDPPF': 'https://www.rdppf.vd.ch/x?EGRID=CH485483457601'}) == 'CH485483457601' else 'KO '} lecture EGRID")
    return not erreurs and identique and not ko


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "../pully_parcelles.csv") else 1)
