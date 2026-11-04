"""Tests du fichier code/criteres_category.py (indépendants du réseau)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "code" / "criteres_category.py"
spec = importlib.util.spec_from_file_location("criteres_category", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CFG = {
    "surface_min_m2": 600,
    "emprise_max": .2,
    "surface_parcelle": {"seuil_fort_potentiel_m2":1200,"seuil_moyen_potentiel_m2":600},
    "patrimoine_recensement":{"notes_exclues":[1,2,3]},
    "zone_reservee_pleine_terre":{"seuil_exclusion_pourcentage":50,"seuil_malus_pourcentage":64},
    "ratio_sous_exploitation_rd":{"seuil_fort_potentiel":.35,"seuil_moyen_potentiel":.7},
    "reculs_rdppf_metres":{"lisiere_foret":10,"cours_d_eau":15,"route":3},
    "zonage_et_dangers":{"pente_max_autorisee_pourcentage":25,"penalite_isos":True,"exclure_dangers_naturels":True,"exclure_acces_complique":True},
}

def full_row(**updates):
    row = dict(egrid="TEST-001", numero_parcelle="1", surface_geometrique_m2="1200",
        emprise_batie_m2="200", notes_batiment_existante_json="[]",
        notes_batiment_provisoire_json="[]", notes_site_existante_json="[]",
        notes_site_provisoire_json="[]", pleine_terre_pct="65",
        ratio_sous_exploitation_rd="0.3", distance_lisiere_foret_m="12",
        distance_cours_d_eau_m="20", recul_route_m="5", pente_mediane_pct="10",
        isos_present="false", danger_naturel_bloquant="false", acces_complique="false")
    row.update(updates)
    return row

class TestCriteriaCategory(unittest.TestCase):
    def test_valid_config(self):
        mod.validate_config(CFG)

    def test_complete_pass(self):
        a=mod.evaluate_parcel(full_row(),CFG)
        self.assertEqual(a['statut_filtrage_criteres'],'retenue')
        self.assertEqual(a['filtres']['surface_fort_potentiel_m2']['etat'],'ok')

    def test_area_bound_inclusive(self):
        a=mod.evaluate_parcel(full_row(surface_geometrique_m2='600',emprise_batie_m2='60'),CFG)
        self.assertEqual(a['filtres']['surface_min_m2']['etat'],'ok')

    def test_area_exclusion(self):
        a=mod.evaluate_parcel(full_row(surface_geometrique_m2='599'),CFG)
        self.assertEqual(a['statut_filtrage_criteres'],'exclue')

    def test_coverage_exclusion(self):
        a=mod.evaluate_parcel(full_row(emprise_batie_m2='300'),CFG)
        self.assertIn('emprise_max',a['filtres_echoues'])

    def test_heritage_exclusion(self):
        a=mod.evaluate_parcel(full_row(notes_batiment_provisoire_json='[2]'),CFG)
        self.assertIn('patrimoine',a['filtres_echoues'])

    def test_full_earth_missing(self):
        a=mod.evaluate_parcel(full_row(pleine_terre_pct=''),CFG)
        self.assertEqual(a['statut_filtrage_criteres'],'a_verifier')
        self.assertIn('pleine_terre_exclusion',a['filtres_inconnus'])

    def test_full_earth_exclusion(self):
        a=mod.evaluate_parcel(full_row(pleine_terre_pct='49'),CFG)
        self.assertIn('pleine_terre_exclusion',a['filtres_echoues'])

    def test_full_earth_malus(self):
        a=mod.evaluate_parcel(full_row(pleine_terre_pct='60'),CFG)
        self.assertIn('pleine_terre_malus',a['alertes'])

    def test_distances_missing_not_assumed(self):
        a=mod.evaluate_parcel(full_row(distance_lisiere_foret_m=''),CFG)
        self.assertIn('recul_lisiere_foret',a['filtres_inconnus'])

    def test_slopes_in_percent(self):
        a=mod.evaluate_parcel(full_row(pente_mediane_pct=''),CFG,
            {'statut_calcul':'calcule','pente_mediane_pct':'26'})
        self.assertIn('pente_max',a['filtres_echoues'])

    def test_slope_unknown_bad_quality(self):
        a=mod.evaluate_parcel(full_row(pente_mediane_pct=''),CFG,
            {'statut_calcul':'non_calculable','pente_mediane_pct':'10'})
        self.assertIn('pente_max',a['filtres_inconnus'])

    def test_danger_exclusion(self):
        a=mod.evaluate_parcel(full_row(danger_naturel_bloquant='true'),CFG)
        self.assertIn('dangers_naturels',a['filtres_echoues'])

    def test_isos_alert(self):
        a=mod.evaluate_parcel(full_row(isos_present='true'),CFG)
        self.assertIn('isos',a['alertes'])

    def test_known_failure_overrides_missing(self):
        a=mod.evaluate_parcel(full_row(surface_geometrique_m2='400',pleine_terre_pct=''),CFG)
        self.assertEqual(a['statut_filtrage_criteres'],'exclue')

    def test_ratio_is_signal_only(self):
        a=mod.evaluate_parcel(full_row(ratio_sous_exploitation_rd='0.8'),CFG)
        self.assertEqual(a['statut_filtrage_criteres'],'retenue')
        self.assertEqual(a['filtres']['ratio_rd_fort']['etat'],'echec')

    def test_inactive_constraints(self):
        cfg=json.loads(json.dumps(CFG));cfg['zonage_et_dangers']['exclure_acces_complique']=False
        a=mod.evaluate_parcel(full_row(acces_complique='true'),cfg)
        self.assertEqual(a['filtres']['acces_complique']['etat'],'sans_objet')

    def test_validator_rejects_bad_coverage(self):
        cfg=json.loads(json.dumps(CFG));cfg['emprise_max']=20
        with self.assertRaises(ValueError):mod.validate_config(cfg)

if __name__ == '__main__': unittest.main()
