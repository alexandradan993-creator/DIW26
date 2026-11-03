"""Contrôles analytiques de l'érosion géométrique et des formes."""
import math
import unittest

try:
    from shapely.geometry import Point, Polygon, box, MultiPolygon
    from geometrie import calculer_forme
except ImportError:
    calculer_forme=None


@unittest.skipIf(calculer_forme is None,'Installer scripts/requirements-parcelles.txt pour les tests géométriques')
class GeometryTests(unittest.TestCase):
    def test_equal_area_square_and_long_rectangle(self):
        square,_=calculer_forme(box(0,0,40,40),6)
        rectangle,_=calculer_forme(box(0,0,20,80),6)
        self.assertAlmostEqual(square['surface_apres_retrait_m2'],784)
        self.assertAlmostEqual(rectangle['surface_apres_retrait_m2'],544)
        self.assertAlmostEqual(square['part_terrain_apres_retrait_pct'],49)
        self.assertAlmostEqual(rectangle['part_terrain_apres_retrait_pct'],34)
        self.assertAlmostEqual(square['allongement_rectangle_englobant'],1)
        self.assertAlmostEqual(rectangle['allongement_rectangle_englobant'],4)

    def test_narrow_parcel_empty_and_invalid_contour_not_repaired(self):
        result,envelope=calculer_forme(box(0,0,10,160),6)
        self.assertTrue(envelope.is_empty)
        self.assertEqual(result['part_terrain_apres_retrait_pct'],0)
        with self.assertRaises(ValueError):
            calculer_forme(Polygon([(0,0),(10,10),(0,10),(10,0)]),6)
        with self.assertRaises(ValueError):calculer_forme(box(0,0,40,40),-1)

    def test_circle_and_zero_distance(self):
        circle=Point(0,0).buffer(20,quad_segs=256)
        result,_=calculer_forme(circle,6)
        self.assertAlmostEqual(result['surface_apres_retrait_m2'],math.pi*14**2,delta=.02)
        self.assertGreater(result['compacite'],.999)
        zero,_=calculer_forme(circle,0)
        self.assertAlmostEqual(zero['part_terrain_apres_retrait_pct'],100)

    def test_holes_and_separate_parts_preserved(self):
        polygon=Polygon([(0,0),(40,0),(40,40),(0,40)],holes=[[(15,15),(25,15),(25,25),(15,25)]])
        _,envelope=calculer_forme(polygon,2)
        self.assertFalse(envelope.contains(Point(20,20)))
        result,_=calculer_forme(MultiPolygon([box(0,0,40,40),box(100,0,140,40)]),6)
        self.assertEqual(result['nombre_enveloppes'],2)
        self.assertAlmostEqual(result['surface_apres_retrait_m2'],1568)
