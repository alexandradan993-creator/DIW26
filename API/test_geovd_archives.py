"""Périmètre GEO.vd, notes sourcées et archives authentifiées."""
import contextlib
import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from actualiser_pully import SCHEMA, deriver
from collecte_application import collecter
from patrimoine_geovd import collecter as patrimoine


class GeoTests(unittest.TestCase):
    def fixture(self):
        from test_service_contraintes import ServiceTests
        fixture=ServiceTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        return fixture

    def bundles(self,note=2):
        from test_service_contraintes import feature,square
        def collect(layer,bbox):
            return dict(metadata={'name':'vd.batiment_recense' if layer==316 else 'vd.site',
                                  'fields':[{'name':'NOTE_CARTO'},{'name':'NOTE_DETAIL'}]},
                        features=[feature(1,square(width=5),ID_OBJET_RECENSE=10,
                                          NOTE_CARTO=note if layer==316 else 6,NOTE_DETAIL=None)],
                        provenance={'empreinte_contenu_sha256':str(layer)+str(note),
                                    'verifie_utc':'2026-11-05T14:00:00Z'})
        return collect

    def test_real_notes_join_and_first_observation_then_evolution(self):
        f=self.fixture()
        first=patrimoine(f.contours,None,collect=self.bundles(2))
        self.assertEqual(first['parcelles']['E1']['notes_batiments'],[2])
        self.assertEqual(first['parcelles']['E2']['notes_batiments'],[])
        self.assertIsNone(first['parcelles']['E1']['evolution_notes'])
        second=patrimoine(f.contours,None,first,collect=self.bundles(4))
        self.assertEqual(second['evolutions'],1)
        self.assertEqual(second['parcelles']['E1']['precedentes']['notes_batiments'],[2])
        self.assertEqual(second['parcelles']['E1']['notes_batiments'],[4])

    def test_new_blocking_note_and_old_blocking_note_are_preserved(self):
        f=self.fixture();cfg=f.service.criteria.load_criteria(f.service.config)
        observations=patrimoine(f.contours,None,collect=self.bundles(2))
        fiches=f.service._fiches(f.rows,{}, {},cfg,f.service.active(),contours_path=f.contours,
                                 patrimoine=observations['parcelles'])
        self.assertEqual(fiches['E1']['classement']['statut_filtrage_criteres'],'rouge')
        f.rows[0]['notes_batiment_existante_json']='[1]'
        observations=patrimoine(f.contours,None,collect=self.bundles(4))
        fiches=f.service._fiches(f.rows,{}, {},cfg,f.service.active(),contours_path=f.contours,
                                 patrimoine=observations['parcelles'])
        self.assertEqual(fiches['E1']['classement']['statut_filtrage_criteres'],'rouge')

    def test_geo_candidate_activates_and_archives_sourced_notes(self):
        from unittest.mock import patch
        f=self.fixture();service=f.service;service.mode_actualisation='geovd'
        def base(stage,state,old):
            with (stage/'parcelles.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(f.rows[0]));writer.writeheader();writer.writerows(f.rows)
        service.base_collector=base
        real=patrimoine
        with contextlib.redirect_stdout(io.StringIO()),patch('donnees_interface.derivations'),patch(
                'patrimoine_geovd.collecter',side_effect=lambda contours,state,before:real(contours,state,before,collect=self.bundles(2))):
            operation=service.start(background=False)
        state=service.status(operation['operation_id'])
        self.assertEqual(state['statut'],'termine')
        self.assertEqual(state['mode'],'geovd')
        fiche=service.fiche('E1')
        self.assertEqual(fiche['patrimoine_geovd']['notes_batiments'],[2])
        self.assertEqual(fiche['classement']['statut_filtrage_criteres'],'rouge')
        with service.archive(service.active()) as stream,zipfile.ZipFile(stream) as archive:
            self.assertIn('patrimoine_geovd.json',archive.namelist())
            self.assertEqual(json.loads(archive.read('manifest.json'))['mode_actualisation'],'geovd')

    def test_unknown_note_refuses_candidate(self):
        f=self.fixture()
        with self.assertRaisesRegex(ValueError,'Note patrimoniale inconnue'):
            patrimoine(f.contours,None,collect=self.bundles(9))

    def test_geo_mode_does_not_fetch_sigip_and_preserves_provisional_note(self):
        from test_collecte_application import CollecteTests
        from actualiser_pully import Etat
        module=CollecteTests().fake();module.SCHEMA=SCHEMA;module.deriver=deriver
        def construire(state):
            self.assertEqual(module.COUCHES_SIGIP,{})
            module.telecharger('https://test/rest/272/query',{'returnIdsOnly':'true'},True)
            module.telecharger('https://test/rest/272/query',{'objectIds':'1'},True)
            return [dict(egrid='E1',surface_geometrique_m2=1000,
                         batiments_surface_intersection_m2=100,zones_affectation_json=[])]
        module.construire=construire
        module.wfs_requete=lambda *args: self.fail('SIGIP ne doit pas être appelé')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            stage=Path(tmp)
            collecter(stage,Etat(stage),{'E1':{'sigip_pully_recensement_provisoire_batiments_json':
                                              '[{"note_provisoire":2}]','decision_conti':'visite'}},module,geovd=True)
            with (stage/'parcelles.csv').open(encoding='utf-8-sig') as stream:row=next(csv.DictReader(stream))
            self.assertEqual(json.loads(row['notes_batiment_provisoire_json']),[2])
            self.assertEqual(row['decision_conti'],'visite')


class ArchiveTests(unittest.TestCase):
    def test_history_and_zip_are_authenticated_and_preserve_old_versions(self):
        from test_application_web import WebTests
        web=WebTests();web.setUp();self.addCleanup(web.tearDown)
        service=web.service;old=service.active()
        original=(service.version_path(old)/'parcelles.json').read_bytes()
        self.assertEqual(web.call('/versions',auth=False)['status'],401)
        self.assertEqual(web.call('/versions/'+old+'/archive.zip',auth=False)['status'],401)
        with contextlib.redirect_stdout(io.StringIO()):service.start(background=False)
        history=json.loads(web.call('/versions')['body'])
        self.assertEqual(len(history['versions']),2)
        self.assertEqual(sum(v['active'] for v in history['versions']),1)
        self.assertTrue(all(v['date'] for v in history['versions']))
        response=web.call('/versions/'+old+'/archive.zip')
        self.assertEqual(response['status'],200)
        with zipfile.ZipFile(io.BytesIO(response['body'])) as archive:
            self.assertEqual(archive.read('parcelles.json'),original)
            self.assertIn('manifest.json',archive.namelist())
            self.assertNotIn('annotations_expert.json',archive.namelist())
        self.assertEqual(web.call('/versions/invalide/archive.zip')['status'],404)


if __name__=='__main__':unittest.main()
