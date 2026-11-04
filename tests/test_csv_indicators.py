"""Run from repo root: python -m unittest discover -s tests -p 'test_csv_indicators.py'"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from criteres_category import csv_indicators, load_criteria, evaluate_parcel


class CsvOnlyIndicatorsTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "egrid": "TEST", "genre_parcelle": "DP communal",
            "surface_geometrique_m2": "1000",
            "emprise_batie_m2": "200",
            "surface_hors_emprise_batiments_m2": "800",
            "batiments_nombre": "2",
            "sigip_surfaces_vertes_surface_intersection_m2": "510",
            "sigip_surfaces_dures_surface_intersection_m2": "150",
            "sigip_forets_surface_intersection_m2": "10",
            "sigip_eaux_surface_intersection_m2": "0",
            "zone_dominante": "Zone de villas",
            "presence_note_1_3_batiment_existante": "false",
            "presence_note_1_3_batiment_provisoire": "false",
            "presence_note_1_3_site_existante": "false",
            "presence_note_1_3_site_provisoire": "false",
        }
        self.cfg = load_criteria(Path(__file__).resolve().parents[1] / "code" / "criteres.json")

    def test_csv_fields(self):
        v = csv_indicators(self.row)
        self.assertEqual(v["domaine_cadastral"], "Communal (domaine public)")
        self.assertEqual(v["domaine_public_communal"], "Oui")
        self.assertEqual(v["proprietaire_communal_confirme"], "Non établi")
        self.assertEqual(v["emprise_batie_m2"], 200)
        self.assertEqual(v["emprise_batie_pct"], 20)
        self.assertEqual(v["intersection_foret"], "Oui")
        self.assertEqual(v["distance_lisiere_foret_m"], 0)
        self.assertEqual(v["intersection_eaux"], "Non")
        self.assertIsNone(v["distance_cours_d_eau_m"])

    def test_no_forest_distance_guess(self):
        self.row["sigip_forets_surface_intersection_m2"] = "0"
        self.assertIsNone(csv_indicators(self.row)["distance_lisiere_foret_m"])

    def test_missing_overlap_is_unknown(self):
        self.row["sigip_forets_surface_intersection_m2"] = ""
        self.assertEqual(csv_indicators(self.row)["intersection_foret"], "Inconnu")

    def test_forest_intersection_moves_green_to_yellow(self):
        slope = {"pente_mediane_pct": "10", "statut_calcul": "calcule"}
        a = evaluate_parcel(self.row, self.cfg, slope)
        self.assertEqual(a["statut_filtrage_criteres"], "jaune")
        self.assertIn("intersection_foret", a["alertes"])
        self.row["sigip_forets_surface_intersection_m2"] = "0"
        b = evaluate_parcel(self.row, self.cfg, slope)
        self.assertEqual(b["statut_filtrage_criteres"], "vert")

    def test_forest_does_not_override_red(self):
        self.row["surface_geometrique_m2"] = "500"
        slope = {"pente_mediane_pct": "10", "statut_calcul": "calcule"}
        v = evaluate_parcel(self.row, self.cfg, slope)
        self.assertEqual(v["statut_filtrage_criteres"], "rouge")


if __name__ == "__main__":
    unittest.main()
