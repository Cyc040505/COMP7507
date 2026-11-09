"""Simplify shared TopoJSON arcs while preserving every geographic feature.

Do not use the 110m world file: it omits small partner economies. Shared arc
indices and endpoints stay fixed, so adjacent countries retain matching borders.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path


def _simplify(points, scale, tolerance):
    if len(points) <= 4:
        return points
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = points[first][0] * scale[0], points[first][1] * scale[1]
        bx, by = points[last][0] * scale[0], points[last][1] * scale[1]
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        farthest, index = tolerance * tolerance, None
        for i in range(first + 1, last):
            x, y = points[i][0] * scale[0], points[i][1] * scale[1]
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length)) if length else 0
            distance = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            if distance > farthest:
                farthest, index = distance, i
        if index is not None:
            keep.add(index)
            stack.extend(((first, index), (index, last)))
    reduced = [points[i] for i in sorted(keep)]
    # Preserve small islands/rings intact rather than collapsing them to lines.
    if points[0] == points[-1] and len(reduced) < 4:
        return points
    return reduced


def simplify_topology(source, tolerance=.12):
    output = deepcopy(source)
    scale = source["transform"]["scale"]
    source_points, reduced_points = [], []
    for i, arc in enumerate(source["arcs"]):
        absolute, x, y = [], 0, 0
        for dx, dy in arc:
            x, y = x + dx, y + dy
            absolute.append((x, y))
        points = _simplify(absolute, scale, tolerance)
        source_points.append(absolute)
        reduced_points.append(points)
        encoded, x, y = [], 0, 0
        for nx, ny in points:
            encoded.append([nx - x, ny - y])
            x, y = nx, ny
        output["arcs"][i] = encoded
    # Spherical renderers fill the complement of an inverted polygon. Checking
    # whole rings (including rings assembled from several shared arcs) is vital
    # for narrow islands. Restore suspect rings using the source's shared arcs.
    rings = []
    for collection in source["objects"].values():
        for geometry in collection.get("geometries", []):
            polygons = ([geometry["arcs"]] if geometry["type"] == "Polygon" else
                        geometry["arcs"] if geometry["type"] == "MultiPolygon" else [])
            rings.extend(ring for polygon in polygons for ring in polygon)
    original_areas = [_ring_area(ring, source_points) for ring in rings]
    restored = set()
    while True:
        changed = False
        for ring, area in zip(rings, original_areas):
            reduced_area = _ring_area(ring, reduced_points)
            if area and (area * reduced_area <= 0 or abs(reduced_area / area) < .3):
                for index in ring:
                    index = index if index >= 0 else ~index
                    if index not in restored:
                        restored.add(index)
                        reduced_points[index] = source_points[index]
                        output["arcs"][index] = source["arcs"][index]
                        changed = True
        if not changed:
            break
    return output


def _ring_area(ring, arcs):
    points = []
    for index in ring:
        arc = arcs[index] if index >= 0 else arcs[~index][::-1]
        points.extend(arc if not points else arc[1:])
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1]))


@lru_cache(maxsize=1)
def optimized_world():
    path = Path(__file__).resolve().parents[1] / "assets/world_50m.json"
    source = json.loads(path.read_text())
    return json.dumps(simplify_topology(source), separators=(",", ":")).encode()
