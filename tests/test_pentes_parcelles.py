"""Contrôles des unités, masques et couvertures sur un raster synthétique."""
import unittest

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

from scripts.calculer_pentes_parcelles import statistics


class ParcelSlopeTests(unittest.TestCase):
    def run_stats(self, values, polygon):
        values=np.asarray(values,dtype='float32')
        with MemoryFile() as memory:
            with memory.open(driver='GTiff',height=values.shape[0],width=values.shape[1],
                             count=1,dtype='float32',crs='EPSG:2056',
                             transform=from_origin(0,values.shape[0]*2,2,2),
                             nodata=-9999) as dataset:
                dataset.write(values,1)
                return statistics(dataset,polygon)

    def test_percent_conversion_and_nodata_do_not_create_flat_ground(self):
        values=[[0,np.degrees(np.arctan(.15))],
                [np.degrees(np.arctan(.5)),-9999]]
        r=self.run_stats(values,box(0,0,4,4))
        self.assertEqual(r['pixels_valides'],3)
        self.assertEqual(r['pixels_nodata'],1)
        self.assertEqual(r['part_pixels_valides_pct'],75)
        self.assertAlmostEqual(r['pente_mediane_pct'],15,places=4)
        self.assertAlmostEqual(r['pente_max_pct'],50,places=4)
        for name in ['part_pixels_pente_inf_10pct','part_pixels_pente_10_a_25pct',
                     'part_pixels_pente_sup_25pct']:
            self.assertAlmostEqual(r[name],100/3)

    def test_hole_excludes_steep_pixel(self):
        values=np.zeros((3,3));values[1,1]=70
        polygon=Polygon([(0,0),(6,0),(6,6),(0,6)],
                        holes=[[(2,2),(4,2),(4,4),(2,4)]])
        r=self.run_stats(values,polygon)
        self.assertEqual(r['pixels_valides'],8)
        self.assertEqual(r['pente_max_degres'],0)

    def test_partial_coverage_is_separate_from_nodata(self):
        r=self.run_stats(np.zeros((2,2)),box(0,0,8,4))
        self.assertEqual(r['couverture_emprise_raster_pct'],50)
        self.assertEqual(r['part_pixels_valides_pct'],100)

    def test_no_sample_returns_unknown_not_zero_slope(self):
        for polygon in [box(10,10,12,12),box(.1,.1,.2,.2)]:
            with self.subTest(bounds=polygon.bounds):
                r=self.run_stats(np.zeros((2,2)),polygon)
                self.assertEqual(r['pixels_valides'],0)
                self.assertIsNone(r['pente_mediane_pct'])


if __name__=='__main__':
    unittest.main()
