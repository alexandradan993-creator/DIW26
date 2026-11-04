"""Tests sur sources synthétiques : aucun croisement réel n'est simulé comme acquis."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import box

import actualiser_pully as A
from croisements_contraintes import SpatialLayer, collect_layer, export_crossings


def feature(oid, coords=None, classe='rouge'):
    return {'attributes':{'OBJECTID':oid,'CLASSE':classe,'SITE':'Site test'},
            'geometry':{'rings':[coords or [[0,0],[10,0],[10,10],[0,10],[0,0]]]}}


def metadata():
    return {'geometryType':'esriGeometryPolygon','objectIdField':'OBJECTID','maxRecordCount':2,
            'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'},
                      {'name':'CLASSE','type':'esriFieldTypeString'},
                      {'name':'SITE','type':'esriFieldTypeString'}]}


def bundle(features):
    return {'metadata':metadata(),'features':features,'provenance':{'source':'synthétique'}}


class CrossingsTests(unittest.TestCase):
    def test_complete_download_even_when_server_truncates_batches(self):
        def request(url,params=None):
            if params is None:return metadata()
            if params.get('returnIdsOnly'):return {'objectIds':[1,2,3]}
            if params.get('returnCountOnly'):return {'count':3}
            wanted=list(map(int,params['objectIds'].split(',')))
            return {'spatialReference':{'wkid':2056},
                    'features':[feature(wanted[0])],
                    'exceededTransferLimit':len(wanted)>1}
        result=collect_layer(404,(0,0,10,10),request)
        self.assertEqual(len(result['features']),3)
        self.assertEqual(result['provenance']['objets'],3)
        self.assertIsNone(result['provenance']['date_donnee'])

    def test_missing_single_object_and_incomplete_inventory_fail(self):
        def request(url,params=None):
            if params is None:return metadata()
            if params.get('returnIdsOnly'):return {'objectIds':[1]}
            if params.get('returnCountOnly'):return {'count':1}
            return {'spatialReference':{'wkid':2056},'features':[]}
        with self.assertRaises(ValueError):collect_layer(404,(0,0,10,10),request)
        def truncated(url,params=None):
            return metadata() if params is None else {'objectIds':[1],'exceededTransferLimit':True}
        with self.assertRaises(ValueError):collect_layer(404,(0,0,10,10),truncated)

    def test_overlap_uses_union_including_per_class(self):
        features=[feature(1,[[0,0],[7,0],[7,10],[0,10],[0,0]]),
                  feature(2,[[3,0],[10,0],[10,10],[3,10],[3,0]])]
        r=SpatialLayer(bundle(features),'CLASSE').intersect(box(0,0,10,10))
        self.assertEqual(r['surface_union_m2'],100)
        self.assertEqual(r['classes'][0]['surface_union_m2'],100)
        self.assertEqual(len(r['objets']),2)

    def test_no_intersection_is_unknown_without_study_coverage(self):
        r=SpatialLayer(bundle([])).intersect(box(0,0,10,10))
        self.assertFalse(r['intersection_detectee'])
        self.assertEqual(r['statut_couverture'],'inconnue')
        self.assertIsNone(r['couverture_etude_pct'])
        full=SpatialLayer(bundle([]),coverage=box(-1,-1,11,11)).intersect(box(0,0,10,10))
        self.assertEqual(full['statut_couverture'],'complete')
        partial=SpatialLayer(bundle([]),coverage=box(0,0,5,10)).intersect(box(0,0,10,10))
        self.assertEqual(partial['statut_couverture'],'partielle')
        self.assertEqual(partial['couverture_etude_pct'],50)

    def test_boundary_contact_does_not_create_positive_area(self):
        r=SpatialLayer(bundle([feature(1)])).intersect(box(10,0,20,10))
        self.assertFalse(r['intersection_detectee'])
        self.assertEqual(r['surface_union_m2'],0)

    def test_unknown_business_field_rejected(self):
        with self.assertRaises(ValueError):SpatialLayer(bundle([feature(1)]),'CHAMP_INVENTE')

    def test_class_labels_only_come_from_official_coded_domain(self):
        source=bundle([feature(1,classe=2)])
        source['metadata']['fields'][1]['domain']={'codedValues':[{'code':2,'name':'Libellé fourni'}]}
        result=SpatialLayer(source,'CLASSE').intersect(box(0,0,10,10))
        self.assertEqual(result['classes'][0]['code'],'2')
        self.assertEqual(result['classes'][0]['libelle'],'Libellé fourni')

    def test_export_negative_result_depends_on_verified_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);reference,contours=self.inputs(root)
            coverage=root/'couverture.json'
            coverage.write_text(json.dumps({'sr':2056,'source':'Étude synthétique',
                'date_donnee':'2026-01-01','features':[feature(1)]}))
            out=root/'versions';out.mkdir()
            collect=lambda layer,bbox:bundle([])
            dest,_=export_crossings(reference,contours,out,A.Etat(out),
                                    coverage_isos=coverage,coverage_dangers=coverage,collect=collect)
            with (dest/'croisements.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(rows[0]['isos_etat'],'hors_perimetres_consultes')
            self.assertEqual(rows[0]['dangers_etat'],'aucun_danger_identifie_dans_donnees_consultees')
            self.assertEqual(rows[1]['dangers_etat'],'a_verifier')

    def inputs(self,root):
        reference=root/'base.csv'
        reference.write_text('egrid,numero_parcelle,surface_geometrique_m2,decision_conti\nE1,1,100,examiner\nE2,2,100,conserver\nE3,3,100,visite\n')
        good=feature(1);good['attributes']['egris_egrid']='E1'
        invalid=feature(2,[[0,0],[10,10],[0,10],[10,0],[0,0]])
        invalid['attributes']['egris_egrid']='E2'
        contours=root/'contours.json'
        contours.write_text(json.dumps({'sr':2056,'results':[good,invalid]}))
        return reference,contours

    def test_export_preserves_missing_and_invalid_parcels_and_original_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);reference,contours=self.inputs(root)
            before=reference.read_bytes();out=root/'versions';out.mkdir()
            state=A.Etat(out)
            collect=lambda layer,bbox:bundle([feature(1)])
            dest,report=export_crossings(reference,contours,out,state,'SITE','CLASSE',collect=collect)
            with (dest/'croisements.csv').open(encoding='utf-8-sig') as stream:r=list(csv.DictReader(stream))
            self.assertEqual([row['egrid'] for row in r],['E1','E2','E3'])
            self.assertEqual(r[0]['dangers_etat'],'danger_identifie')
            self.assertEqual(r[0]['danger_bloquant'],'')
            self.assertEqual(r[1]['isos_etat'],'a_verifier')
            self.assertEqual(r[2]['dangers_etat'],'a_verifier')
            self.assertEqual(reference.read_bytes(),before)
            self.assertFalse(report['activation_automatique'])
            self.assertFalse(report['classement_recalcule'])
            self.assertTrue((dest/'provenance.json').exists())

    def test_failure_keeps_previous_version_without_incomplete_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);reference,contours=self.inputs(root)
            out=root/'versions';out.mkdir();previous=out/'ancienne.csv';previous.write_text('ne pas remplacer')
            def fail(layer,bbox):raise OSError('source inaccessible')
            with self.assertRaises(OSError):
                export_crossings(reference,contours,out,A.Etat(out),collect=fail)
            self.assertEqual(previous.read_text(),'ne pas remplacer')
            self.assertFalse(list(out.glob('croisements-*')))

    def test_shared_lock_blocks_second_update_without_network_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'actualisation.lock').write_text('autre processus')
            with patch('sys.argv',['actualiser_pully.py','--croisements','--sortie',str(root)]),patch('croisements_contraintes.collect_layer') as collect:
                with self.assertRaises(SystemExit) as stopped:A.main()
                self.assertEqual(stopped.exception.code,2)
                collect.assert_not_called()
            self.assertTrue((root/'actualisation.lock').exists())


if __name__=='__main__':
    unittest.main()
