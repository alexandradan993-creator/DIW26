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
