import importlib.util
import json
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'code' / 'criteres_category.py'
spec = importlib.util.spec_from_file_location('criteres_category', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CFG = {
  'surface_min_m2': 600, 'emprise_max': .2,
  'surface_parcelle': {'seuil_fort_potentiel_m2': 1200, 'seuil_moyen_potentiel_m2': 600},
  'patrimoine_recensement': {'notes_exclues': [1,2,3]},
  'zone_reservee_pleine_terre': {'seuil_exclusion_pourcentage': 50, 'seuil_malus_pourcentage': 64},
  'ratio_sous_exploitation_rd': {'seuil_fort_potentiel': .35, 'seuil_moyen_potentiel': .70},
  'reculs_rdppf_metres': {'lisiere_foret': 10, 'cours_d_eau': 15, 'route': 3},
  'zonage_et_dangers': {'pente_max_autorisee_pourcentage': 25, 'penalite_isos': True, 'exclure_dangers_naturels': True, 'exclure_acces_complique': True},
}

class ZonageEliminatoireTests(unittest.TestCase):
    def result(self, zone):
        return mod.evaluate_parcel({'zone_dominante': zone, 'surface_geometrique_m2': '1000', 'emprise_batie_m2': '80'}, CFG)

    def test_allowed_zones(self):
        for zone in ['Zone de faible densité', 'ZONE DE MOYENNE DENSITÉ', 'Zone de villas', 'Zone de moyenne densite']:
            with self.subTest(zone=zone):
                r = self.result(zone)
                self.assertEqual(r['filtres']['zonage_residentiel']['etat'], 'ok')
                self.assertNotIn('zonage_residentiel', r['filtres_echoues'])

    def test_other_zones_are_red(self):
        for zone in ['Aire forestière', 'Zone de forte densité', 'Zone viticole', 'Zone de verdure', 'Domaine public', "Zone d'habitation", 'Zone de construction de moyenne densité']:
            with self.subTest(zone=zone):
                r = self.result(zone)
                self.assertEqual(r['statut_filtrage_criteres'], 'exclue')
                self.assertIn('zonage_residentiel', r['filtres_echoues'])

    def test_missing_zoning_is_not_invented(self):
        r = self.result('')
        self.assertEqual(r['filtres']['zonage_residentiel']['etat'], 'inconnu')
        self.assertIn('zonage_residentiel', r['filtres_inconnus'])

    def test_forest_excluded_even_if_other_data_missing(self):
        r = mod.evaluate_parcel({'zone_dominante':'Aire forestière'}, CFG)
        self.assertEqual(r['statut_filtrage_criteres'], 'exclue')

if __name__ == '__main__':
    unittest.main()
