"""Paths and global settings for the pipeline.

Every script imports its locations from here, so moving a folder means
changing one line.
"""

from pathlib import Path

# This repository (code, notes, docs only)
REPO_ROOT = Path(__file__).resolve().parent

# Raw data: read-only, on OneDrive. Folders are RawData-BNG, RawData-Housing,
# RawData-Land, RawData-Planning and RawData-Boundaries.
RAW_ROOT = Path.home() / "Library/CloudStorage/OneDrive-UniversityofExeter/Dissertation"

# Large working files on the Mac disk (not synced): unzipped Living England
# GeoPackage, 50 m work rasters, eBird.
WORK_ROOT = Path.home() / "Diss Data"

# Outputs of this pipeline (ignored by git)
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
TEMP_DIR = DATA_DIR / "temp"

# Random seed for every bootstrap, permutation or simulation:
# rng = np.random.default_rng(SEED)
SEED = 20261126
