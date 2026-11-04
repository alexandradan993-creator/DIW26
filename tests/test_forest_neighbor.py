"""Unit tests: python -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from criteres_category import (load_criteria, evaluate_parcel, compute_forest_neighbor_index)


def polygon(egrid, x0, x1):
    return {'type': 'Feature', 'properties': {'egrid': egrid},
            'geometry': {'type': 'Polygon', 'coordinates': [[
                [x0, 46.5], [x1, 46.5], [x1, 46.5001], [x0, 46.5001], [x0, 46.5]
            ]]}}


class ForestNeighbourTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_criteria(Path(__file__).resolve().parents[1] / 'code' / 'criteres.json')
        self.row = {'egrid':'A', 'numero_parcelle':'1', 'genre_parcelle':'parcelle privée',
                    'surface_geometrique_m2':'1000', 'emprise_batie_m2':'100',
                    'zone_dominante':'Zone de villas',
                    'sigip_forets_surface_intersection_m2':'0',
                    'presence_note_1_3_batiment_existante':'false',
                    'presence_note_1_3_batiment_provisoire':'false',
                    'presence_note_1_3_site_existante':'false',
                    'presence_note_1_3_site_provisoire':'false'}
        self.slope = {'pente_mediane_pct':'10', 'statut_calcul':'calcule'}

    def test_nearby_forest_parcel_is_yellow(self):
        forest = dict(self.row, egrid='B', sigip_forets_surface_intersection_m2='10')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'contours.geojson'
            path.write_text(json.dumps({'type':'FeatureCollection','features':[
                polygon('A', 6.65, 6.6501), polygon('B',6.6501,6.6502)]}))
            ix = compute_forest_neighbor_index([self.row, forest], path, 1)
            self.assertEqual(ix['A']['voisine_parcelle_avec_foret'], 'Oui')
            self.assertEqual(ix['A']['distance_parcelle_forestiere_m'], 0)
            tested = evaluate_parcel(self.row, self.cfg, self.slope, ix['A'])
            self.assertEqual(tested['statut_filtrage_criteres'],'jaune')
            self.assertIn('voisin_parcelle_forestiere', tested['alertes'])
            self.assertEqual(tested['bordure_foret_confirmee'], 'Inconnu (pas de géométrie forestière)')

    def test_far_from_forest_parcel_stays_green(self):
        forest = dict(self.row, egrid='B', sigip_forets_surface_intersection_m2='10')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'contours.geojson'
            path.write_text(json.dumps({'type':'FeatureCollection','features':[
                polygon('A',6.65,6.6501),polygon('B',6.66,6.6601)]}))
            ix = compute_forest_neighbor_index([self.row, forest], path, 1)
            self.assertEqual(ix['A']['voisine_parcelle_avec_foret'], 'Non détectée (dans le jeu de données)')
            result = evaluate_parcel(self.row, self.cfg, self.slope, ix['A'])
            self.assertEqual(result['statut_filtrage_criteres'],'vert')

    def test_red_always_takes_priority(self):
        low_area = dict(self.row, surface_geometrique_m2='500')
        result = evaluate_parcel(low_area, self.cfg, self.slope,
                                 {'voisine_parcelle_avec_foret':'Oui',
                                  'distance_parcelle_forestiere_m':0,
                                  'egrid_voisin_forestier':'B'})
        self.assertEqual(result['statut_filtrage_criteres'],'rouge')

    def test_without_contours_no_adjacency_is_assumed(self):
        result = evaluate_parcel(self.row, self.cfg, self.slope)
        self.assertEqual(result['statut_filtrage_criteres'],'vert')
        self.assertIsNone(result['voisine_parcelle_avec_foret'])


if __name__=='__main__':
    unittest.main()
