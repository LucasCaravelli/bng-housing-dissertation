"""Check W3: financial-year to calendar quarter conversion, and release ordering.

Run from the Pipeline folder:  python -m pytest tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from planning_panel import fy_to_calendar, release_order  # noqa: E402


@pytest.mark.parametrize("year, quarter, expected", [
    ("2016-17", "Q1", "2016 Q2"),   # Apr-Jun 2016
    ("2016-17", "Q2", "2016 Q3"),   # Jul-Sep 2016
    ("2016-17", "Q3", "2016 Q4"),   # Oct-Dec 2016
    ("2016-17", "Q4", "2017 Q1"),   # Jan-Mar 2017
    ("2015-16", "Q4", "2016 Q1"),   # first quarter in the panel
    ("2025-26", "Q4", "2026 Q1"),   # last quarter in the panel
])
def test_fy_to_calendar(year, quarter, expected):
    assert fy_to_calendar(year, quarter) == expected


def test_release_order():
    names = ["dmqs_2023_october-december.ods", "dmqs_2023_january-march.ods",
             "dmqs_2023_july-september.ods", "dmqs_2023_april-june.ods"]
    ordered = sorted(names, key=lambda n: release_order(Path(n)))
    assert ordered == ["dmqs_2023_january-march.ods", "dmqs_2023_april-june.ods",
                       "dmqs_2023_july-september.ods", "dmqs_2023_october-december.ods"]
