import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'code' / 'criteres_category.py'
SPEC = importlib.util.spec_from_file_location('criteres_category', SRC)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
CFG = json.loads((Path(__file__).with_name('criteres_three_color_fixture.json')).read_text(encoding='utf-8-sig'))
CFG['zonage_et_dangers'].update(
    penalite_isos=False, exclure_dangers_naturels=False, exclure_acces_complique=False
)


def parcel(**updates):
    row = {
        'egrid': 'TEST', 'numero_parcelle': '1',
        'zone_dominante': 'Zone de villas',
        'surface_geometrique_m2': '600',
        'emprise_batie_m2': '120',
        'notes_batiment_existante_json': '[]',
        'pente_mediane_pct': '10',
    }
    row.update(updates)
    return row


class Tests(unittest.TestCase):
    def status(self, **updates):
        return module.evaluate_parcel(parcel(**updates), CFG)['statut_filtrage_criteres']

    def test_exactly_600_area_and_20pct_green(self):
        self.assertEqual(self.status(), 'vert')

    def test_below_600_red(self):
        self.assertEqual(self.status(surface_geometrique_m2='599'), 'rouge')

    def test_coverage_over_20pct_yellow(self):
        self.assertEqual(self.status(emprise_batie_m2='121'), 'jaune')

    def test_missing_coverage_yellow(self):
        self.assertEqual(self.status(emprise_batie_m2=''), 'jaune')

    def test_forbidden_zone_red(self):
        self.assertEqual(self.status(zone_dominante='Aire forestière'), 'rouge')

    def test_unknown_zone_yellow(self):
        self.assertEqual(self.status(zone_dominante=''), 'jaune')

    def test_heritage_note_2_red(self):
        self.assertEqual(self.status(notes_batiment_existante_json='[2]'), 'rouge')

    def test_slope_over_25_red(self):
        self.assertEqual(self.status(pente_mediane_pct='26'), 'rouge')

    def test_missing_slope_yellow(self):
        self.assertEqual(self.status(pente_mediane_pct=''), 'jaune')

    def test_missing_full_earth_does_not_block_green(self):
        self.assertEqual(self.status(pleine_terre_reglementaire_m2=''), 'vert')

    def test_notes_not_eliminatory(self):
        self.assertEqual(self.status(distance_lisiere_foret_m='1', distance_cours_d_eau_m='1', recul_route_m='1'), 'vert')

    def test_bad_coverage_and_forbidden_zone_red_priority(self):
        self.assertEqual(self.status(emprise_batie_m2='180', zone_dominante='Aire forestière'), 'rouge')

if __name__ == '__main__':
    unittest.main()
