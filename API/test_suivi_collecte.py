"""Délais effectifs, état observable et conservation de la version valide."""
import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from actualiser_pully import Etat
from suivi_collecte import CollectionTimeout, SuiviCollecte, download


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def do_GET(self):
                if self.path == '/forbidden':
                    self.send_error(403)
                    return
                self.send_response(200)
                self.end_headers()
                try:
                    for _ in range(40 if self.path == '/slow' else 1):
                        self.wfile.write(b'{"ok":true}')
                        self.wfile.flush()
                        if self.path == '/slow':time.sleep(.1)
                except (BrokenPipeError, ConnectionResetError):pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_complete_response(self):
        self.assertEqual(json.loads(download(self.base+'/ok',timeout=3)), {'ok':True})

    def test_trickling_response_is_actually_stopped(self):
        started = time.monotonic()
        with self.assertRaises(CollectionTimeout):
            download(self.base+'/slow',timeout=.5)
        self.assertLess(time.monotonic()-started, 2)

    def test_http_failure_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
            download(self.base+'/forbidden',timeout=3)


class TrackingTests(unittest.TestCase):
    def test_live_step_has_layer_counts_and_no_url_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Etat(Path(folder))
            state.data['operation_id'] = 'operation-test'
            def transport(url, params, post):
                current = json.loads(state.chemin.read_text())
                self.assertEqual(current['telechargement']['etat'], 'envoi')
                self.assertEqual(current['telechargement']['couche'], 'patrimoine')
                return b'[]'
            tracker = SuiviCollecte(state,transport)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                tracker('https://www.sigip.ch/mapserv_proxy?token=SECRET',
                        {'TYPENAME':'patrimoine', 'REQUEST':'GetFeature'})
            current = json.loads(state.chemin.read_text())
            self.assertEqual(current['progression_reseau']['octets_recus'], 2)
            self.assertEqual(current['telechargement']['etat'], 'réponse reçue')
            self.assertNotIn('SECRET',output.getvalue()+state.chemin.read_text())

    def test_timeout_retries_are_bounded_and_operation_keeps_version(self):
        from test_service_contraintes import ServiceTests
        fixture = ServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        previous = fixture.service.active()
        def collector(stage,state,old):
            tracker = SuiviCollecte(state)
            tracker('https://www.sigip.ch/mapserv_proxy',{'TYPENAME':'patrimoine'})
        fixture.service.base_collector = collector
        with contextlib.redirect_stdout(io.StringIO()), patch('suivi_collecte.download',
                side_effect=CollectionTimeout('Délai maximal dépassé')) as transport:
            operation = fixture.service.start(background=False)
        self.assertEqual(transport.call_count, 2)
        result = fixture.service.status(operation['operation_id'])
        self.assertEqual(result['statut'], 'erreur')
        self.assertIn('SIGIP / couche patrimoine',result['erreur'])
        self.assertEqual(fixture.service.active(),previous)
        self.assertFalse(fixture.service.lock.exists())

    def test_global_deadline_prevents_another_request(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Etat(Path(folder))
            transport = unittest.mock.Mock()
            tracker = SuiviCollecte(state,transport)
            tracker.deadline = time.monotonic()-1
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'20 minutes'):
                tracker('https://www.sigip.ch/mapserv_proxy',{'TYPENAME':'test'})
            transport.assert_not_called()


if __name__ == '__main__':unittest.main()
