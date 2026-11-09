"""Guard against small-island loss and inverted country fills during simplification."""
import json
from pathlib import Path
import unittest

from src.geo_topology import optimized_world


def decode(topology):
    output = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            points.append((x, y))
        output.append(points)
    return output


def ring_area(ring, arcs):
    points = []
    for index in ring:
        arc = arcs[index] if index >= 0 else list(reversed(arcs[~index]))
        points.extend(arc if not points else arc[1:])
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, points[1:] + points[:1]))


class MapTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((Path(__file__).resolve().parents[1] / "assets/world_50m.json").read_text())
        cls.fast = json.loads(optimized_world())
        cls.original_arcs, cls.fast_arcs = decode(cls.source), decode(cls.fast)

    def test_features_and_shared_boundaries_survive_with_lower_vertex_count(self):
        self.assertEqual(self.source["objects"], self.fast["objects"])
        self.assertEqual(self.source["transform"], self.fast["transform"])
        self.assertEqual(len(self.original_arcs), len(self.fast_arcs))
        for source, fast in zip(self.original_arcs, self.fast_arcs):
            self.assertEqual(source[0], fast[0])
            self.assertEqual(source[-1], fast[-1])
        self.assertLess(sum(map(len, self.fast_arcs)), .4 * sum(map(len, self.original_arcs)))

    def test_no_polygon_winding_inverts_or_collapses(self):
        for collection in self.source["objects"].values():
            for geometry in collection["geometries"]:
                polygons = ([geometry["arcs"]] if geometry["type"] == "Polygon" else
                            geometry["arcs"] if geometry["type"] == "MultiPolygon" else [])
                for polygon in polygons:
                    for ring in polygon:
                        source = ring_area(ring, self.original_arcs)
                        fast = ring_area(ring, self.fast_arcs)
                        if source:
                            self.assertGreater(source * fast, 0)
                            self.assertGreaterEqual(abs(fast / source), .3)
