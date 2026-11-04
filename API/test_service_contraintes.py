"""Scénarios du bouton et de la fiche canonique, sur sources synthétiques."""
import csv
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from service_contraintes import ROOT, UpdateService
from serveur_contraintes import make_server


def feature(oid,coords,**attributes):
    return {'attributes':dict(OBJECTID=oid,**attributes),'geometry':{'rings':[coords]}}


def square(x=0,width=10):
    return [[x,0],[x+width,0],[x+width,10],[x,10],[x,0]]


def fake_collect(layer,bbox):
    site=layer==404
    field='NOM_SITE' if site else 'DEG_DN_PREP'
    features=[feature(1,square(width=5),NOM_SITE='Site A')] if site else [feature(1,square(),DEG_DN_PREP='W')]
    metadata={'name':'vd.perimetre_fonde_sur_isos' if site else 'vd.carte_synthetique_danger_naturel',
              'fields':[{'name':field}],
              'drawingInfo':{'renderer':{'field1':field,'uniqueValueInfos':[{'value':'W','label':'Danger nul'}]}}}
    digest=hashlib.sha256(json.dumps(features,sort_keys=True).encode()).hexdigest()
    return dict(metadata=metadata,features=features,provenance={
        'url':f'https://www.ogc.vd.ch/test/{layer}','verifie_utc':'2026-11-04T12:00:00Z',
        'date_donnee':None,'completude':'ids_et_comptage_controles',
        'empreinte_contenu_sha256':digest,'empreinte_metadonnees_sha256':str(layer)})


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.reference=self.root/'base.csv';self.contours=self.root/'contours.json'
        self.rows=[dict(egrid='E1',numero_parcelle='1',surface_geometrique_m2='1000',emprise_batie_m2='100',
                       zone_dominante='Zone de villas',notes_batiment_existante_json='[]'),
                   dict(egrid='E2',numero_parcelle='2',surface_geometrique_m2='1000',emprise_batie_m2='100',
                       zone_dominante='Zone de villas',notes_batiment_existante_json='[]')]
        self.save_rows(self.rows)
        objects=[feature(1,square(),egris_egrid='E1'),feature(2,square(20),egris_egrid='E2')]
        self.contours.write_text(json.dumps({'sr':2056,'results':objects}))
        self.service=UpdateService(self.root/'store',self.reference,self.contours,collector=fake_collect,
                                   slopes=self.root/'pentes_absentes.csv')

    def tearDown(self):
        if self.service.thread:self.service.thread.join(timeout=10)
        self.temp.cleanup()

    def save_rows(self,rows):
        with self.reference.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

    def test_partial_isos_zero_danger_and_outside_coverage(self):
        before=self.service.fiche('E1')['classement']
        operation=self.service.start(background=False)
        self.assertEqual(self.service.status(operation['operation_id'])['statut'],'termine')
        a=self.service.fiche('E1');b=self.service.fiche('E2')
        self.assertEqual(a['contraintes']['isos_part_parcelle_pct']['valeur'],50)
        self.assertIs(a['contraintes']['isos_presence']['valeur'],True)
        self.assertEqual(a['contraintes']['danger_nul_etudie']['valeur'],0)
        self.assertIs(a['contraintes']['dangers_presence']['valeur'],False)
        self.assertIsNone(a['contraintes']['danger_naturel_bloquant']['valeur'])
        self.assertIsNone(b['contraintes']['dangers_presence']['valeur'])
        self.assertIsNone(b['contraintes']['danger_part_risque_pct']['valeur'])
        self.assertEqual(b['contraintes']['dangers_couverture_pct']['valeur'],0)
        self.assertEqual(a['classement'],before)
        for field in a['contraintes'].values():
            self.assertTrue({'valeur','unite','etat','source','date_donnee','date_verification','motif'}<=set(field))
            if field['valeur'] is None:self.assertTrue(field['motif'])

    def test_incomplete_download_keeps_active_and_annotations(self):
        old=self.service.active()
        annotations=self.service.storage/'annotations_expert.json'
        annotations.write_text(json.dumps({'E1':{'decision':'visite','contact':'à conserver'}}))
        def fail(layer,bbox):raise ValueError('Réponse paginée incomplète')
        self.service.collector=fail
        operation=self.service.start(background=False)
        self.assertEqual(self.service.status(operation['operation_id'])['statut'],'erreur')
        self.assertEqual(self.service.active(),old)
        self.assertEqual(self.service.fiche('E1')['annotations_expert']['decision'],'visite')
        self.assertFalse(list(self.service.storage.glob('application-*')))

    def test_no_change_keeps_version_and_operation_history(self):
        first=self.service.start(background=False);version=self.service.active()
        second=self.service.start(background=False)
        self.assertEqual(self.service.status(second['operation_id'])['statut'],'aucun_changement')
        self.assertEqual(self.service.active(),version)
        self.assertEqual(self.service.status(first['operation_id'])['statut'],'termine')

    def test_activation_failure_keeps_previous_pointer(self):
        import service_contraintes as module
        original=module.write_json;version=self.service.active()
        def write(path,value):
            if path==self.service.pointer:raise OSError('Activation impossible')
            return original(path,value)
        with patch('service_contraintes.write_json',side_effect=write):
            operation=self.service.start(background=False)
        self.assertEqual(self.service.active(),version)
        self.assertEqual(self.service.status(operation['operation_id'])['statut'],'erreur')

    def test_missing_parcel_is_conserved_until_archival_decision(self):
        self.service.start(background=False)
        self.save_rows(self.rows[:1])
        self.service.start(background=False)
        row=self.service.fiche('E2')
        self.assertFalse(row['presente_derniere_collecte'])
        self.assertIsNone(row['contraintes']['isos_presence']['valeur'])
        self.assertIn('absente_derniere_collecte_a_examiner',row['alertes'])
        self.assertEqual(self.service.liste()['total'],2)

    def test_same_running_operation_returned_and_old_version_readable(self):
        entered=threading.Event();release=threading.Event();old=self.service.active()
        def slow(layer,bbox):
            entered.set();release.wait(timeout=5);return fake_collect(layer,bbox)
        self.service.collector=slow
        first=self.service.start();self.assertTrue(entered.wait(timeout=2))
        try:
            second=self.service.start()
            self.assertEqual(first['operation_id'],second['operation_id'])
            self.assertTrue(second['reutilisee'])
            self.assertEqual(self.service.active(),old)
            self.assertEqual(self.service.fiche('E1')['version'],old)
        finally:
            release.set();self.service.thread.join(timeout=5)
        self.assertEqual(self.service.status(first['operation_id'])['statut'],'termine')
        self.assertEqual(self.service.fiche('E1',old)['version'],old)

    def test_http_button_status_and_canonical_egird(self):
        server=make_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        base='http://127.0.0.1:'+str(server.server_address[1])
        try:
            request=Request(base+'/actualisations',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
            with urlopen(request) as response:
                self.assertEqual(response.status,202);operation=json.load(response)['operation_id']
            self.service.thread.join(timeout=5)
            with urlopen(base+'/actualisations/'+operation) as response:self.assertEqual(json.load(response)['statut'],'termine')
            with urlopen(base+'/parcelles?limit=1') as response:listing=json.load(response)
            egrid=listing['parcelles'][0]['egrid']
            with urlopen(base+'/parcelles/'+egrid+'?version='+listing['version']) as response:fiche=json.load(response)
            self.assertEqual(fiche,self.service.fiche(egrid,listing['version']))
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    unittest.main()
