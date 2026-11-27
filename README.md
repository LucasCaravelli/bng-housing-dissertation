# Biodiversity Net Gain and the English housing market

BSc Economics dissertation (University of Exeter). How did England's mandatory Biodiversity
Net Gain (BNG, from February 2024) affect housing **supply** (planning decisions), **demand**
(house prices near registered gain sites) and, as a check, **biodiversity** around gain sites?
A toy model, in which BNG is a cost on development and possibly a local amenity, frames every
test.

Results, models and tables: **[docs/REPORT.md](docs/REPORT.md)**. Background and open questions:
[docs/FINDINGS.md](docs/FINDINGS.md).

## Repository layout

| Folder | Contents |
|---|---|
| `src/` | the pipeline, one script per stage (inputs, designs, figures, tables) |
| `tests/` | unit tests: estimators on simulated data, grid and quarter conversions |
| `notes/` | one file per design: **Part A** pre-specification (written before running) and **Part B** results, including every deviation |
| `docs/` | the report and the background findings |
| `inputs/` | small hand-made tables the code depends on (habitat distinctiveness crosswalk) |
| `output/` | figures (PNG and PDF) and generated results tables |
| `config.py` | all paths and the random seed |

## Data (not included)

No data are in this repository: the files are large, and several licences forbid
redistribution (eBird, HM Land Registry CCOD). The scripts expect:

- raw data under `RAW_ROOT` (set in `config.py`): `RawData-BNG/`, `RawData-Planning/`,
  `RawData-Housing/`, the eBird Basic Dataset zip;
- large working files under `WORK_ROOT` (`~/Diss Data/`): the unzipped Living England
  GeoPackage and the 50 m rasters;
- processed outputs are written to `data/` (ignored by git).

Sources: Natural England Biodiversity Gain Site Register; MHCLG planning statistics (PS1/PS2);
Welsh Government DMQS; HM Land Registry Price Paid; ONS Postcode Directory; EPC open data;
Natural England Living England 2022-23; ONS LAD boundaries; nutrient-neutrality catchments;
English Indices of Deprivation 2025; eBird Basic Dataset (Cornell Lab of Ornithology).

## Environment

```
mamba env create -f environment.yml      # creates the 'bng-diss' environment
conda activate bng-diss
python -m pytest tests -p no:cacheprovider
```

Exact versions used are in `environment.lock.yml`.

## Running

From this folder, in the order listed in [docs/REPORT.md, section 9](docs/REPORT.md#9-reproducing-everything).
Each script prints its checks; a failed check stops the script.

## Conventions

- Every design is pre-specified in `notes/<design>.md` before it is run; changes after seeing
  results are recorded as deviations.
- Every estimator is checked against an independent route (a second package, a hand-coded
  version or simulated data).
- Raw data are never modified; random seeds are fixed in `config.py`.
