import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('criteres_category', ROOT / 'code' / 'criteres_category.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
cfg = mod.load_criteria(ROOT / 'code' / 'criteres.json')


class TestPotential(unittest.TestCase):
    def test_slope_completely_removed(self):
        self.assertNotIn('pente_max_autorisee_pourcentage', cfg['zonage_et_dangers'])
        row = self.example_row(pente_mediane_pct='90')
        result = mod.evaluate_parcel(row, cfg)
        self.assertNotIn('pente_max', result['filtres'])
        self.assertNotIn('pente_mediane_pct', result)
        self.assertEqual(result['statut_filtrage_criteres'], 'vert')

    def test_area_capacity_with_and_without_building(self):
        row = self.example_row()
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['emprise_max_theorique_cos_m2'], 200)
        self.assertEqual(ind['surface_exploitable_avec_batiment_m2'], 120)
        self.assertEqual(ind['surface_exploitable_sans_batiment_m2'], 200)
        self.assertEqual(ind['surface_libre_hors_batiment_m2'], 920)

    def test_inevaluable_when_cos_missing(self):
        row = self.example_row(cos_source_zone_dominante='')
        ind = mod.csv_indicators(row)
        self.assertIsNone(ind['surface_exploitable_avec_batiment_m2'])
        self.assertIsNone(ind['surface_exploitable_sans_batiment_m2'])

    def test_small_parcel_has_height_study_note_but_remains_red(self):
        row = self.example_row(surface_geometrique_m2='500')
        evaluation = mod.evaluate_parcel(row, cfg)
        self.assertEqual(evaluation['statut_filtrage_criteres'], 'rouge')
        self.assertIn('piste_surelevation', evaluation['filtres'])
        self.assertEqual(evaluation['surelevation_etude_applicable'], 'Oui')
        self.assertIn('À examiner', evaluation['piste_surelevation'])

    def test_height_not_inferred_from_floors(self):
        ind = mod.csv_indicators(self.example_row(rcb_nombre_niveaux_max='4'))
        self.assertEqual(ind['rcb_nombre_niveaux_max'], 4)
        self.assertIsNone(ind['marge_hauteur_m'])
        self.assertEqual(ind['surélévation_verifiee'], 'Non : examen réglementaire requis')

    def test_explicit_height_data_is_only_indicative(self):
        row = self.example_row(hauteur_max_reglementaire_m='12', hauteur_batiment_existant_m='9')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['marge_hauteur_m'], 3.0)
        self.assertEqual(ind['surelevation_etude_applicable'], 'Non')
        self.assertEqual(ind['surélévation_verifiee'], 'Non : examen réglementaire requis')

    def test_forest_alert_still_applies(self):
        row = self.example_row(sigip_forets_surface_intersection_m2='15')
        self.assertEqual(mod.evaluate_parcel(row, cfg)['statut_filtrage_criteres'], 'jaune')

    def test_neighbor_only_does_not_force_yellow(self):
        row = self.example_row()
        nearby = {'voisine_parcelle_avec_foret': 'Oui', 'distance_parcelle_forestiere_m': 0.0}
        result = mod.evaluate_parcel(row, cfg, nearby)
        self.assertEqual(result['statut_filtrage_criteres'], 'vert')
        self.assertEqual(result['filtres']['voisin_parcelle_forestiere']['etat'], 'note')

    def test_small_but_unbuilt_not_studied(self):
        row = self.example_row(surface_geometrique_m2='500',
                               batiments_nombre='0', emprise_batie_m2='0')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['surelevation_etude_applicable'], 'Non')
        self.assertIsNone(ind['niveaux_supplementaires_scenario_max'])

    def test_existing_building_ground_full_one_level(self):
        row = self.example_row(emprise_batie_m2='200', rcb_nombre_niveaux_max='1')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['surelevation_etude_applicable'], 'Oui')
        self.assertEqual(ind['niveaux_supplementaires_scenario_min'], 1)
        self.assertEqual(ind['niveaux_supplementaires_scenario_max'], 2)
        self.assertEqual(ind['surface_plancher_supplementaire_scenario_max_m2'], 400.0)
        self.assertEqual(ind['hauteur_reference_scenario_m'], 10.0)
        self.assertIsNone(ind['marge_hauteur_m'])

    def test_existing_building_ground_full_three_levels(self):
        row = self.example_row(emprise_batie_m2='200', rcb_nombre_niveaux_max='3')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['niveaux_supplementaires_scenario_max'], 0)
        self.assertEqual(ind['surface_plancher_supplementaire_scenario_max_m2'], None)

    def test_no_height_on_parcel_with_ground_room(self):
        row = self.example_row(rcb_nombre_niveaux_max='1')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['surelevation_etude_applicable'], 'Non')
        self.assertIsNone(ind['hauteur_reference_scenario_m'])

    def test_no_height_if_zoning_ineligible(self):
        row = self.example_row(zone_dominante='Aire forestière',
                               surface_geometrique_m2='500', rcb_nombre_niveaux_max='1')
        ind = mod.csv_indicators(row)
        self.assertEqual(ind['surelevation_etude_applicable'], 'Non')

    @staticmethod
    def example_row(**update):
        row = dict(egrid='CHTEST',numero_parcelle='123',genre_parcelle='parcelle privée',
                   surface_geometrique_m2='1000',emprise_batie_m2='80',batiments_nombre='1',
                   cos_source_zone_dominante='0.2',zone_dominante='zone de villas',
                   sigip_forets_surface_intersection_m2='0',sigip_eaux_surface_intersection_m2='0',
                   presence_note_1_3_batiment_existante='false',presence_note_1_3_batiment_provisoire='false',
                   presence_note_1_3_site_existante='false',presence_note_1_3_site_provisoire='false')
        row.update(update)
        return row


if __name__ == '__main__':
    unittest.main()
