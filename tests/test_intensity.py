"""Check I1: settlement patches, distance rings and cell counts on small synthetic grids.

Run from the Pipeline folder:  python -m pytest tests
"""

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from intensity_score import count_cells, rings, settlements  # noqa: E402

RES = 50  # metres per cell, as in the real grid


def disk(radius_cells):
    y, x = np.ogrid[-radius_cells:radius_cells + 1, -radius_cells:radius_cells + 1]
    return x * x + y * y <= radius_cells * radius_cells


def rings_by_dilation(settle):
    """Brute-force route: dilate the settlement mask with disks of 5, 10 and 20 cells."""
    ring = np.full(settle.shape, 4, dtype=np.uint8)
    for code, metres in [(3, 1000), (2, 500), (1, 250)]:
        ring[ndimage.binary_dilation(settle, structure=disk(metres // RES))] = code
    ring[settle] = 0
    return ring


def town_grid():
    built = np.zeros((80, 80), dtype=bool)
    built[30:50, 30:50] = True     # 400 cells = 100 ha town
    built[5, 5] = True             # 1-cell farmstead
    return built


def test_small_patches_are_not_settlements():
    settle, n = settlements(town_grid(), min_cells=40)   # 10 ha = 40 cells
    assert n == 1
    assert settle[40, 40] and not settle[5, 5]


def test_diagonal_cells_join_one_patch():
    built = np.zeros((10, 10), dtype=bool)
    built[2, 2] = built[3, 3] = True                     # touch only at a corner
    _, n = settlements(built, min_cells=2)
    assert n == 1                                        # 8-connectivity


def test_ring_codes_at_known_distances():
    settle, _ = settlements(town_grid(), min_cells=40)
    ring = rings(settle)
    # town's east edge is column 49; distance to column 49 + k is k cells = 50k metres
    assert ring[40, 40] == 0
    assert ring[40, 54] == 1      # 250 m: edge inclusive
    assert ring[40, 55] == 2      # 300 m
    assert ring[40, 59] == 2      # 500 m
    assert ring[40, 60] == 3      # 550 m
    assert ring[40, 69] == 3      # 1000 m
    assert ring[40, 70] == 4      # 1050 m
    assert ring[5, 6] == 4        # the farmstead creates no zone


def test_distance_transform_matches_brute_force_dilation():
    rng = np.random.default_rng(20261126)
    built = ndimage.binary_closing(rng.random((150, 150)) > 0.93, iterations=2)
    settle, n = settlements(built, min_cells=40)
    assert n > 0
    assert np.array_equal(rings(settle), rings_by_dilation(settle))


def test_count_cells_adds_up():
    settle, _ = settlements(town_grid(), min_cells=40)
    ring = rings(settle)
    units = np.ones(ring.shape, dtype=np.int16)
    units[:, 60:] = 2
    cls = np.ones(ring.shape, dtype=np.uint8)
    c = count_cells(units, cls, ring, n_units=2, n_cls=1)
    assert c.sum() == ring.size
    assert c[2].sum() == (units == 2).sum()
    assert c[1, 1, 0] == settle.sum()
