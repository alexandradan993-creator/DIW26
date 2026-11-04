"""Contrats de publication : données privées, même API et stockage persistant."""
import base64
import io
import json
import unittest
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

from application_web import create_app
from service_contraintes import UpdateService


class WebTests(unittest.TestCase):
    def setUp(self):
        from test_service_contraintes import ServiceTests
        self.fixture=ServiceTests();self.fixture.setUp()
        self.service=self.fixture.service
        self.app=create_app(self.service,username='expert',password='secret-uniquement-test')

    def tearDown(self):
        self.fixture.tearDown()

    def call(self,path='/',method='GET',auth=True,body=b'',**extra):
        env={};setup_testing_defaults(env)
        route,_,query=path.partition('?')
        env.update(PATH_INFO=route,QUERY_STRING=query,REQUEST_METHOD=method,
                   CONTENT_LENGTH=str(len(body)),CONTENT_TYPE='application/json',HTTP_HOST='localhost',
                   **{'wsgi.input':io.BytesIO(body)})
        if auth:
            env['HTTP_AUTHORIZATION']='Basic '+base64.b64encode(b'expert:secret-uniquement-test').decode()
        env.update(extra);response={}
        def start(status,headers):response.update(status=int(status.split()[0]),headers=dict(headers))
        response['body']=b''.join(self.app(env,start))
        return response

    def test_anonymous_cannot_read_or_refresh(self):
        for path,method in [('/','GET'),('/actualisation.js','GET'),('/application/donnees','GET'),
                            ('/parcelles/E1','GET'),('/actualisations','POST')]:
            with self.subTest(path=path):
                r=self.call(path,method,auth=False,body=b'{}')
                self.assertEqual(r['status'],401)
                self.assertIn('WWW-Authenticate',r['headers'])
        self.assertEqual(self.service.status()['statut'],'aucune_operation')

    def test_invalid_credentials_and_malformed_header_rejected(self):
        for value in ['Basic invalid!', 'Bearer token', 'Basic '+base64.b64encode(b'expert:mauvais').decode()]:
            self.assertEqual(self.call(HTTP_AUTHORIZATION=value)['status'],401)

    def test_health_exposes_no_parcel_or_version(self):
        r=self.call('/healthz',auth=False)
        self.assertEqual(r['status'],200)
        self.assertEqual(json.loads(r['body']),{'statut':'pret'})
        with patch.object(self.service,'active',side_effect=OSError('disque')):
            self.assertEqual(self.call('/healthz',auth=False)['status'],503)

    def test_same_interface_and_canonical_fiche(self):
        self.assertEqual(self.call()['status'],200)
        self.assertEqual(self.call('/actualisation.js')['status'],200)
        data=json.loads(self.call('/application/donnees')['body'])
        fiche=json.loads(self.call('/parcelles/E1?version='+data['version'])['body'])
        self.assertEqual(data['version'],fiche['version'])
        self.assertEqual(data['total'],2)
        self.assertEqual(fiche,self.service.fiche('E1'))

    def test_authenticated_button_updates_and_reboot_preserves_version(self):
        r=self.call('/actualisations','POST',body=b'{}')
        self.assertEqual(r['status'],202)
        operation=json.loads(r['body'])['operation_id']
        self.service.thread.join(timeout=10)
        state=json.loads(self.call('/actualisations/'+operation)['body'])
        self.assertEqual(state['statut'],'termine')
        restored=UpdateService(storage=self.service.storage,reference=self.fixture.reference,
                               contours=self.fixture.contours,slopes=self.service.slopes)
        self.assertEqual(restored.active(),self.service.active())
        self.assertEqual(restored.fiche('E1'),self.service.fiche('E1'))

    def test_cross_origin_refresh_rejected(self):
        self.assertEqual(self.call('/actualisations','POST',body=b'{}',HTTP_ORIGIN='https://ailleurs.invalid')['status'],403)
        self.assertEqual(self.service.status()['statut'],'aucune_operation')

    def test_request_controls_and_no_arbitrary_file_route(self):
        self.assertEqual(self.call('/actualisations','POST',body=b'{}',CONTENT_TYPE='text/plain')['status'],415)
        self.assertEqual(self.call('/actualisations','POST',body=b'{"reference":"ailleurs"}')['status'],400)
        self.assertEqual(self.call('/../../pully_parcelles.csv')['status'],404)
        self.assertEqual(self.call('/parcelles?limit=10000')['status'],400)


if __name__=='__main__':unittest.main()
