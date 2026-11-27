"""Check C9: grid conversion against squares computed by hand from the OS lettering.

Run from the Pipeline folder:  python3 -m pytest tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from register import base_reference, gridref_to_bng, reference_date  # noqa: E402


@pytest.mark.parametrize("gridref, expected", [
    # 100 km square origins (no digits -> centre of the 100 km square)
    ("SV", (50_000, 50_000, 0)),          # Scilly: south-west corner of the grid
    ("SU", (450_000, 150_000, 0)),
    ("TQ", (550_000, 150_000, 0)),
    ("NZ", (450_000, 550_000, 0)),
    ("HU", (450_000, 1_150_000, 0)),      # Shetland
    # 1 km reference in central London: TQ 30 80 -> 530 km E, 180 km N, centre +500 m
    ("TQ3080", (530_500, 180_500, 4)),
    # 100 m, 10 m and 1 m references (centre adds half the square)
    ("SU378910", (437_850, 191_050, 6)),
    ("NZ89250938", (489_255, 509_385, 8)),
    ("NZ3963110201", (439_631.5, 510_201.5, 10)),
    ("su 378 910", (437_850, 191_050, 6)),  # spaces and lower case
])
def test_gridref(gridref, expected):
    assert gridref_to_bng(gridref) == expected


def test_empty_gridref():
    assert gridref_to_bng(None) == (None, None, 0)
    assert gridref_to_bng("") == (None, None, 0)


@pytest.mark.parametrize("bad", ["XX1234", "SI1234", "SU123", "SU12a4"])
def test_bad_gridref(bad):
    with pytest.raises(ValueError):
        gridref_to_bng(bad)


def test_reference_parsing():
    ref = "BGS-140125001 - 05/11/2026 14:33 "
    assert base_reference(ref) == "BGS-140125001"
    assert reference_date(ref).date().isoformat() == "2025-01-14"
