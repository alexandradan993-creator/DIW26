"""Contrôles supplémentaires autour du script de collecte inchangé de l'équipe."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from actualiser_pully import Etat, ecrire_csv, maintenant
from collecte_application import collecter


class CollecteTests(unittest.TestCase):
    def fake(self, incomplete=False, hits=1):
        m=types.SimpleNamespace(SIGIP_WFS='https://test/wfs',GEOVD='https://test/rest',
            maintenant=maintenant,ecrire_csv=ecrire_csv,trouver_egrid=lambda a:a.get('EGRID'))
        feature={'attributes':{'OBJECTID':1,'EGRID':'E1'},'geometry':{'rings':[[[0,0],[0,10],[10,10],[10,0],[0,0]]]}}
        def transport(url,params=None,post=False):
            if params.get('RESULTTYPE')=='hits':return f'<FeatureCollection numberOfFeatures="{hits}"/>'.encode()
            if params.get('returnIdsOnly')=='true':return b'{"objectIds":[1]}'
            return json.dumps({'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}],
                'features':[] if incomplete else [feature],'spatialReference':{'wkid':2056}}).encode()
        def wfs(couche,bbox,max_par_requete=5000,profondeur=0):return [{'gml_id':'x1'}]
        def construire(etat):
            url='https://test/rest/272/query'
            m.telecharger(url,{'returnIdsOnly':'true'},True)
            m.telecharger(url,{'objectIds':'1'},True)
            m.wfs_requete('test',(0,0,10,10))
            etat.data['sources']={'test':{'objets':1}}
            return [{'egrid':'E1','numero_parcelle':'1','decision_conti':'perdu'}]
        m.telecharger=transport;m.wfs_requete=wfs;m.construire=construire
        return m

    def test_complete_keeps_expert_fields_and_raw_contours(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            collecter(stage,Etat(stage),{'E1':{'decision_conti':'visite'}},self.fake())
            self.assertIn('visite',(stage/'parcelles.csv').read_text(encoding='utf-8-sig'))
            contour=json.loads((stage/'contours.json').read_text())
            self.assertEqual(contour['sr'],2056)
            self.assertEqual(contour['results'][0]['attributes']['egris_egrid'],'E1')

    def test_incomplete_arcgis_page_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            with self.assertRaisesRegex(ValueError,'incomplète'):
                collecter(stage,Etat(stage),{},self.fake(incomplete=True))
            self.assertFalse((stage/'parcelles.csv').exists())

    def test_wfs_count_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            with self.assertRaisesRegex(ValueError,'Effectif SIGIP'):
                collecter(stage,Etat(stage),{},self.fake(hits=2))
            self.assertFalse((stage/'parcelles.csv').exists())

if __name__=='__main__':unittest.main()
