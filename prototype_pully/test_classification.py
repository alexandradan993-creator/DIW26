"""Contrats métier de la classification configurable à 600 m²."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from classification import analyse, run, validate_config
from test_prospection import parcel


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads(Path(__file__).with_name('filtres.json').read_text())
        self.row=parcel()
        self.row.update(zone_dominante='Zone de moyenne densité',surface_geometrique_m2='600',
                        emprise_batie_m2='100',taux_emprise_geometrique=str(100/600))

    def test_inclusive_600_and_below_threshold(self):
        self.assertEqual(analyse(self.row,self.config)['statut_filtrage'],'retenue_filtres_connus')
        self.row['surface_geometrique_m2']='599.99'
        self.assertEqual(analyse(self.row,self.config)['statut_filtrage'],'exclue_cible')

    def test_provisional_three_still_excludes_despite_four(self):
        self.row.update(notes_batiment_provisoire_json='[3,4]')
        r=analyse(self.row,self.config)
        self.assertEqual(r['statut_filtrage'],'exclue_cible')
        self.assertTrue(r['preuves_patrimoine_json'])

    def test_unknown_heritage_is_not_clearance(self):
        self.row['notes_site_existante_json']='[0]'
        self.assertEqual(analyse(self.row,self.config)['statut_filtrage'],'a_verifier_filtres')
        del self.row['notes_site_existante_json']
        self.assertEqual(analyse(self.row,self.config)['statut_filtrage'],'a_verifier_filtres')

    def test_tree_unknown_or_present_never_becomes_automatic_exclusion(self):
        for observation, state in [(None,'inconnu'),
                                   ({'arbre_central':'oui','source':'Relevé terrain'},'presence_signalee'),
                                   ({'arbre_central':'non','source':''},'inconnu')]:
            with self.subTest(state=state):
                r=analyse(self.row,self.config,observation)
                self.assertEqual(r['statut_filtrage'],'retenue_filtres_connus')
                self.assertEqual(r['arbre_central_statut'],state)
                self.assertEqual(r['statut_potentiel'],'non_etabli')

    def test_cos_simulation_and_no_invented_coefficients(self):
        r=analyse(self.row,self.config)
        self.assertEqual(r['emprise_theorique_simulee_m2'],120)
        self.assertEqual(r['ecart_apparent_simule_m2'],20)
        self.row.update(zone_dominante='Zone de villas',cos_source_zone_dominante='0.2')
        self.assertIsNone(analyse(self.row,self.config)['cos_simulation'])

    def test_mixed_zone_prevents_cos_simulation(self):
        self.row['zone_dominante_part_surface']='0.8'
        r=analyse(self.row,self.config)
        self.assertIsNone(r['cos_simulation'])
        self.assertTrue(r['anomalies_json'])

    def test_negative_gap_not_hidden_and_legacy_limits_inactive(self):
        self.row['emprise_batie_m2']='300'
        self.row['sigip_rcb_bat_json']='[]'
        r=analyse(self.row,self.config)
        self.assertEqual(r['ecart_apparent_simule_m2'],-180)
        self.assertEqual(r['statut_filtrage'],'retenue_filtres_connus')

    def test_slope_and_construction_year_have_no_classification_effect(self):
        before=analyse(self.row,self.config)
        self.row['rcb_annee_construction_max']='1800'
        after=analyse(self.row,self.config,slope={'pente_mediane_pct':'100','alertes_json':'[]'})
        self.assertEqual(before['statut_filtrage'],after['statut_filtrage'])
        self.assertEqual(before['motifs_exclusion_json'],after['motifs_exclusion_json'])
        self.assertEqual(after['pente_information_json']['pente_mediane_pct'],'100')

    def test_filters_can_be_disabled_and_bad_config_rejected(self):
        self.config['surface']['actif']=False
        self.config['patrimoine']['actif']=False
        self.row.update(surface_geometrique_m2='200',notes_site_existante_json='[2]')
        self.assertEqual(analyse(self.row,self.config)['statut_filtrage'],'retenue_filtres_connus')
        for mutation in [('energy',{}),('surface',{'actif':'false','minimum_m2':600})]:
            bad=copy.deepcopy(self.config);bad[mutation[0]]=mutation[1]
            with self.assertRaises(ValueError):validate_config(bad)

    def test_pipeline_outputs_and_duplicate_tree_observations_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);input_path=root/'source.csv';cfg=root/'filtres.json'
            cfg.write_text(json.dumps(self.config))
            with input_path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(self.row));writer.writeheader();writer.writerow(self.row)
            report=run(input_path,cfg,root/'out')
            self.assertEqual(report['effectifs'],{'retenue_filtres_connus':1})
            with (root/'out'/'classification.csv').open(encoding='utf-8-sig') as stream:
                r=next(csv.DictReader(stream))
            self.assertEqual(r['egrid'],'CH_TEST')
            self.assertEqual(json.loads(r['filtres_json'])[0]['critere'],'surface')
            observations=root/'arbres.csv'
            observations.write_text('egrid,arbre_central,source\nCH_TEST,oui,Visite\nCH_TEST,non,Visite\n')
            with self.assertRaises(ValueError):run(input_path,cfg,root/'out',observations)


if __name__=='__main__':
    unittest.main()
