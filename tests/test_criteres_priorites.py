"""Regression checks for revised status priorities."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('criteres_category', ROOT / 'code' / 'criteres_category.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CONFIG = {
    'surface_min_m2': 600,
    'emprise_max': .20,
    'surface_parcelle': {'seuil_fort_potentiel_m2': 1200, 'seuil_moyen_potentiel_m2': 600},
    'patrimoine_recensement': {'notes_exclues': [1, 2, 3]},
    'zone_reservee_pleine_terre': {'seuil_exclusion_pourcentage': 50, 'seuil_malus_pourcentage': 64},
    'ratio_sous_exploitation_rd': {'seuil_fort_potentiel': .35, 'seuil_moyen_potentiel': .70},
    'reculs_rdppf_metres': {'lisiere_foret': 10, 'cours_d_eau': 15, 'route': 3},
    'zonage_et_dangers': {'pente_max_autorisee_pourcentage': 25, 'penalite_isos': True,
                         'exclure_dangers_naturels': False, 'exclure_acces_complique': False},
}


def base_row():
    return {'egrid': 'E1', 'zone_dominante': 'Zone de villas', 'surface_geometrique_m2': '1000',
            'emprise_batie_m2': '100', 'pleine_terre_pct': '70',
            'notes_batiment_existante_json': '[]', 'pente_mediane_pct': '5',
            'distance_lisiere_foret_m': '20', 'distance_cours_d_eau_m': '20', 'recul_route_m': '5'}

class TestRevisedCategories(unittest.TestCase):
    def evaluate(self, **overrides):
        row = base_row()
        row.update(overrides)
        return mod.evaluate_parcel(row, CONFIG)

    def test_baseline_retained(self):
        self.assertEqual(self.evaluate()['statut_filtrage_criteres'], 'retenue')

    def test_coverage_only_evaluation(self):
        r=self.evaluate(emprise_batie_m2='300')
        self.assertEqual(r['statut_filtrage_criteres'], 'retenue')
        self.assertIn('emprise_max', r['criteres_evaluation_defavorables'])
        self.assertNotIn('emprise_max', r['filtres_echoues'])

    def test_earth_only_evaluation(self):
        r=self.evaluate(pleine_terre_pct='40')
        self.assertEqual(r['statut_filtrage_criteres'], 'retenue')
        self.assertIn('pleine_terre_exclusion', r['criteres_evaluation_defavorables'])

    def test_earth_unknown_not_grey(self):
        r=self.evaluate(pleine_terre_pct='')
        self.assertEqual(r['statut_filtrage_criteres'], 'retenue')
        self.assertEqual(r['filtres']['pleine_terre_exclusion']['etat'], 'inconnu')

    def test_all_three_setbacks_only_notes(self):
        r=self.evaluate(distance_lisiere_foret_m='3', distance_cours_d_eau_m='2', recul_route_m='1')
        self.assertEqual(r['statut_filtrage_criteres'], 'retenue')
        self.assertCountEqual(r['notes_reglementaires'], ['recul_lisiere_foret','recul_cours_d_eau','recul_route'])
        self.assertEqual(r['filtres_echoues'], [])

    def test_unknown_setback_not_grey(self):
        r=self.evaluate(distance_lisiere_foret_m='')
        self.assertEqual(r['statut_filtrage_criteres'], 'retenue')

    def test_zoning_still_red(self):
        self.assertEqual(self.evaluate(zone_dominante='Aire forestière')['statut_filtrage_criteres'], 'exclue')

    def test_heritage_still_red(self):
        self.assertEqual(self.evaluate(notes_batiment_existante_json='[2]')['statut_filtrage_criteres'], 'exclue')

    def test_min_area_still_red(self):
        self.assertEqual(self.evaluate(surface_geometrique_m2='400')['statut_filtrage_criteres'], 'exclue')

    def test_slope_still_red(self):
        self.assertEqual(self.evaluate(pente_mediane_pct='35')['statut_filtrage_criteres'], 'exclue')

    def test_missing_slope_still_grey(self):
        self.assertEqual(self.evaluate(pente_mediane_pct='')['statut_filtrage_criteres'], 'a_verifier')

if __name__ == '__main__':
    unittest.main()
