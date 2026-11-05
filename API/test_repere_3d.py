"""Altitude réelle du repère Uzuverse et conservation de l'export versionné."""
import unittest
from unittest.mock import patch
from donnees_interface import altitudes_repere
from service_contraintes import immutable_json


class MarkerTests(unittest.TestCase):
    def test_reference_point_uses_local_terrain_and_missing_stays_unknown(self):
        height,missing,outside=altitudes_repere(((2540003.59,1151259.87),None,(0,0)))
        self.assertTrue(370<height<500)
        self.assertIsNone(missing)
        self.assertIsNone(outside)

    def test_active_and_archived_exports_get_marker_without_mutating_storage(self):
        from test_service_contraintes import ServiceTests
        fixture=ServiceTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        service=fixture.service;version=service.active()
        path=service.version_path(version)/'interface.json';before=path.read_bytes()
        with patch('donnees_interface.altitudes_repere',return_value=(412.79,415.25)):
            active=service.interface();archived=service.interface(version)
        self.assertEqual(active['parcels'][0][9],412.79)
        self.assertEqual(active,archived)
        self.assertEqual(active['version'],version)
        self.assertTrue(all(len(row)==10 for row in active['parcels']))
        self.assertEqual(path.read_bytes(),before)
        self.assertIsNone(immutable_json(str(path))['parcels'][0][9])

if __name__=='__main__':unittest.main()
