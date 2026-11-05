"""Écriture atomique et reprise après interruption de l'initialisation."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service_contraintes import UpdateService, write_json


class StorageTests(unittest.TestCase):
    def test_failed_serialization_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            original = {'texte': 'à conserver', 'inconnue': None, 'zero': 0}
            write_json(path, original)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                write_json(path, {'partiel': [1, 2], 'invalide': float('nan')})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(json.loads(path.read_text()), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_streaming_validation_rejects_truncated_duplicate_and_wrong_identity(self):
        from service_contraintes import verifier_fiches, immutable_json
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fiches.json'
            payload={'E1':{'egrid':'E1','version':'V','valeur':1.25,'vide':None}}
            write_json(path,payload)
            with patch.object(Path,'read_text',side_effect=AssertionError('Lecture entière interdite')):
                verifier_fiches(path,{'E1'},'V')
                self.assertEqual(immutable_json(str(path)),payload)
            for raw in ('{"E1":',
                        '{"E1":{"egrid":"E1","version":"V"},"E1":{"egrid":"E1","version":"V"}}',
                        '{"E1":{"egrid":"E2","version":"V"}}',
                        '{"E1":{"egrid":"E1","version":"ancienne"}}'):
                path.write_text(raw)
                with self.assertRaises(Exception):verifier_fiches(path,{'E1'},'V')
            immutable_json.cache_clear()

    def test_parallel_fiche_reads_and_pagination_keep_large_payloads_separate(self):
        from concurrent.futures import ThreadPoolExecutor
        from service_contraintes import selected_fiche, summaries, _selected_fiche, _summaries
        _selected_fiche.cache_clear();_summaries.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fiches.json'
            values={str(i):{'egrid':str(i),'numero_parcelle':str(i),
                           'classement':{'statut_filtrage_criteres':'jaune'},
                           'detail':'x'*50000} for i in range(100)}
            write_json(path,values)
            del values
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda i:selected_fiche(str(path),str(i%4)),range(12)))
            self.assertEqual([r['egrid'] for r in results],[str(i%4) for i in range(12)])
            self.assertEqual(len(summaries(str(path))),100)
            self.assertNotIn('detail',summaries(str(path))[0])
            self.assertEqual(_selected_fiche.cache_info().currsize,4)
            with self.assertRaises(KeyError):selected_fiche(str(path),'absent')
            _selected_fiche.cache_clear();_summaries.cache_clear()

    def fixture(self):
        from test_service_contraintes import ServiceTests
        fixture = ServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture

    def test_dead_initialization_owner_can_be_restarted_without_deleting_data(self):
        fixture = self.fixture()
        storage = fixture.root / 'interrupted'
        storage.mkdir()
        lock = storage / 'actualisation.lock'
        lock.write_text(json.dumps({'pid': 1234567, 'operation_id': 'initialisation'}))
        retained = storage / 'candidate-interrompue.json'
        retained.write_text('{"a_examiner": true}')
        with patch('service_contraintes.os.kill', side_effect=ProcessLookupError):
            service = UpdateService(storage, fixture.reference, fixture.contours,
                                    slopes=fixture.service.slopes)
        self.assertEqual(service.interface()['total'], 2)
        self.assertTrue(retained.exists())
        self.assertFalse(lock.exists())

    def test_live_initialization_owner_keeps_lock(self):
        fixture = self.fixture()
        storage = fixture.root / 'busy'
        storage.mkdir()
        lock = storage / 'actualisation.lock'
        content = json.dumps({'pid': os.getpid(), 'operation_id': 'initialisation'})
        lock.write_text(content)
        with self.assertRaises(FileExistsError):
            UpdateService(storage, fixture.reference, fixture.contours)
        self.assertEqual(lock.read_text(), content)


if __name__ == '__main__':
    unittest.main()
