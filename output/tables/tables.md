### Table S1. Intensity DiD, baseline (205 councils, 2015 Q1-2026 Q2 excl. 2023 Q4-2024 Q2)

| Outcome                                  | beta per SD (SE, pyfixest)   |   SE, pilot convention |     p |   LPAs |   Obs |
|:-----------------------------------------|:-----------------------------|-----------------------:|------:|-------:|------:|
| log(1 + dwelling decisions)              | +0.0361 (0.0175)             |                 0.0177 | 0.043 |    205 |  8815 |
| dwelling grant rate                      | +0.0075 (0.0059)             |                 0.0059 | 0.204 |    205 |  8794 |
| log(1 + householder decisions) [placebo] | +0.0104 (0.0074)             |                 0.0075 | 0.166 |    205 |  8815 |

### Table S2. Robustness: beta per SD of intensity x Post (SE clustered by LPA)

| Check                                    | Dwelling decisions (log)   | Dwelling grant rate   | Householder (placebo)   |
|:-----------------------------------------|:---------------------------|:----------------------|:------------------------|
| 1 baseline (main sample)                 | +0.036 (0.017) p=0.04      | +0.008 (0.006) p=0.20 | +0.010 (0.007) p=0.16   |
| 2 all councils                           | +0.003 (0.018) p=0.85      | +0.011 (0.005) p=0.03 | +0.024 (0.007) p<0.01   |
| 3 main + London                          | +0.010 (0.022) p=0.65      | +0.012 (0.006) p=0.04 | +0.026 (0.008) p<0.01   |
| 4 region x quarter FE                    | +0.042 (0.023) p=0.07      | +0.017 (0.007) p=0.01 | +0.005 (0.008) p=0.59   |
| 5 LPA trends (pre-fitted) removed        | +0.029 (0.019) p=0.13      | +0.015 (0.007) p=0.03 | +0.006 (0.010) p=0.59   |
| 6 window 2021Q1+                         | +0.027 (0.017) p=0.11      | +0.012 (0.006) p=0.03 | +0.008 (0.007) p=0.24   |
| 7 intensity: 0-250 m                     | +0.035 (0.017) p=0.04      | +0.008 (0.006) p=0.19 | +0.009 (0.007) p=0.20   |
| 7 intensity: 0-1 km                      | +0.037 (0.018) p=0.04      | +0.007 (0.006) p=0.27 | +0.011 (0.007) p=0.14   |
| 7 intensity: settlements >= 50 ha        | +0.035 (0.017) p=0.04      | +0.006 (0.006) p=0.29 | +0.008 (0.007) p=0.24   |
| 7 intensity: alt crosswalk               | +0.036 (0.016) p=0.02      | +0.003 (0.006) p=0.60 | +0.008 (0.007) p=0.25   |
| 7 intensity: mean distinctiveness        | +0.029 (0.017) p=0.09      | +0.006 (0.006) p=0.30 | +0.011 (0.008) p=0.16   |
| 8 top vs bottom tercile                  | +0.054 (0.038) p=0.16      | +0.017 (0.014) p=0.22 | +0.009 (0.016) p=0.59   |
| 9 PPML counts                            | +0.044 (0.016) p<0.01      | -                     | -0.000 (0.006) p=0.98   |
| 10 drop anomalies, merged, DC hosts      | +0.033 (0.018) p=0.07      | +0.007 (0.006) p=0.27 | +0.009 (0.008) p=0.26   |
| 13 drop nutrient-neutrality LPAs         | +0.041 (0.021) p=0.05      | +0.002 (0.007) p=0.75 | +0.018 (0.009) p=0.05   |
| 14 NN x quarter FE                       | +0.035 (0.017) p=0.05      | +0.007 (0.006) p=0.23 | +0.010 (0.007) p=0.17   |
| 15 region x quarter + NN x quarter FE    | +0.039 (0.023) p=0.09      | +0.017 (0.007) p=0.02 | +0.005 (0.009) p=0.57   |
| 16 NN catchment share x quarter          | +0.038 (0.017) p=0.03      | +0.007 (0.006) p=0.23 | +0.011 (0.007) p=0.13   |
| 17 drop LPAs >=10% in NN catchment       | +0.040 (0.019) p=0.04      | +0.006 (0.007) p=0.34 | +0.014 (0.008) p=0.10   |
| 18 region x quarter + NN share x quarter | +0.045 (0.023) p=0.06      | +0.017 (0.007) p=0.01 | +0.005 (0.009) p=0.56   |
| 12 placebo: fake Post 2021Q1-2023Q3      | +0.014 (0.013) p=0.31      | -0.007 (0.004) p=0.12 | +0.003 (0.007) p=0.67   |
| 11 leave one region out (range)          | +0.027 to +0.041           | +0.002 to +0.013      | -0.005 to +0.018        |

### Table S3. Pre-BNG linear differential trend (2015 Q1-2023 Q3, per year per SD)

| sample       | outcome                                |   slope_per_year |     se |      p |
|:-------------|:---------------------------------------|-----------------:|-------:|-------:|
| main         | log(1+dwelling decisions)              |           0.0012 | 0.0029 | 0.6846 |
| main         | dwelling grant rate                    |          -0.0013 | 0.0009 | 0.1695 |
| main         | log(1+householder decisions) [placebo] |           0.0008 | 0.0017 | 0.6539 |
| all_councils | log(1+dwelling decisions)              |          -0.0028 | 0.0027 | 0.3063 |
| all_councils | dwelling grant rate                    |           0.0004 | 0.001  | 0.7243 |
| all_councils | log(1+householder decisions) [placebo] |          -0.0025 | 0.0016 | 0.1126 |

### Table S4. National grant rates (%), pre 2022 Q1-2023 Q2 vs post 2025 Q1-2026 Q2 (descriptive)

| type            |   pre |   post |   change (pp) |
|:----------------|------:|-------:|--------------:|
| Householder     | 89.67 |  90.27 |          0.6  |
| Major dwellings | 79.96 |  84.45 |          4.49 |
| Minor dwellings | 71.55 |  74.55 |          3    |

### Table S5. SDID, English councils vs Welsh donors (jackknife SE; see the two-cluster caveat)

| check                                         | outcome                                |     tau |     se |   tau_did |   eff_donors |   n_wales |   n_england |
|:----------------------------------------------|:---------------------------------------|--------:|-------:|----------:|-------------:|----------:|------------:|
| 1 main                                        | dwelling grant rate [primary]          |  0.0173 | 0.0132 |    0.062  |      20.9874 |        21 |         259 |
| 2 placebo in time (fake post 2021 Q1-2023 Q3) | dwelling grant rate [primary]          |  0.0392 | 0.012  |    0.043  |      20.9969 |        21 |         259 |
| 3 drop interpolated councils                  | dwelling grant rate [primary]          |  0.0128 | 0.0114 |    0.0384 |      16.9955 |        17 |         259 |
| 1 main                                        | minor dwelling grant rate              |  0.0139 | 0.0149 |    0.0627 |      20.986  |        21 |         252 |
| 2 placebo in time (fake post 2021 Q1-2023 Q3) | minor dwelling grant rate              |  0.0368 | 0.0135 |    0.042  |      20.9949 |        21 |         254 |
| 3 drop interpolated councils                  | minor dwelling grant rate              |  0.0105 | 0.0131 |    0.0381 |      16.9958 |        17 |         252 |
| 1 main                                        | log(1+dwelling decisions)              | -0.0485 | 0.0348 |    0.0084 |      20.9904 |        21 |         263 |
| 2 placebo in time (fake post 2021 Q1-2023 Q3) | log(1+dwelling decisions)              |  0.0001 | 0.0357 |    0.0674 |      20.9833 |        21 |         263 |
| 3 drop interpolated councils                  | log(1+dwelling decisions)              | -0.0249 | 0.0414 |    0.0065 |      16.9933 |        17 |         263 |
| 1 main                                        | householder grant rate [placebo]       |  0.0111 | 0.0089 |    0.0157 |      20.9588 |        21 |         263 |
| 2 placebo in time (fake post 2021 Q1-2023 Q3) | householder grant rate [placebo]       |  0.0086 | 0.0053 |    0.0183 |      20.9931 |        21 |         263 |
| 3 drop interpolated councils                  | householder grant rate [placebo]       |  0.0105 | 0.0109 |    0.0174 |      16.9609 |        17 |         263 |
| 1 main                                        | log(1+householder decisions) [placebo] | -0.0335 | 0.0158 |   -0.0224 |      20.9896 |        21 |         263 |
| 2 placebo in time (fake post 2021 Q1-2023 Q3) | log(1+householder decisions) [placebo] | -0.0445 | 0.0119 |   -0.0629 |      20.9909 |        21 |         263 |
| 3 drop interpolated councils                  | log(1+householder decisions) [placebo] | -0.039  | 0.0172 |   -0.0303 |      16.9946 |        17 |         263 |
| 1 main                                        | major dwelling grant rate (annual)     |  0.0391 | 0.0361 |    0.0156 |      15.987  |        16 |         260 |

### Table D1. Gain-site price effects, sales-weighted designs (423-site register)

| Design / spec                                                               |   Sites (treated) |    beta |     SE | % effect [95% CI]   |
|:----------------------------------------------------------------------------|------------------:|--------:|-------:|:--------------------|
| Ring DiD, urban fringe 2024-25                                              |                71 |  0.0003 | 0.0078 | +0.0% [-1.5, +1.6]  |
| Stacked: 1a All sites, inner ring only                                      |               155 |  0.006  | 0.0098 | +0.6% [-1.3, +2.6]  |
| Stacked: 1b All sites, ring DDD (inner vs 2-4 km)                           |               155 |  0.0022 | 0.0122 | +0.2% [-2.1, +2.6]  |
| Stacked: 1c Urban fringe only, inner ring                                   |                56 |  0.0045 | 0.0107 | +0.5% [-1.6, +2.6]  |
| Stacked: 1d Urban fringe only, ring DDD                                     |                56 | -0.0004 | 0.0135 | -0.0% [-2.7, +2.7]  |
| Stacked: 1e Anticipation buffer: controls registered >= 1 year after window |                40 |  0.0282 | 0.0221 | +2.9% [-1.5, +7.4]  |
| Stacked: 1f Treatment = works start if earlier than reference date          |               201 |  0.0026 | 0.0086 | +0.3% [-1.4, +2.0]  |
| Stacked: 1g Existing homes only (no new builds)                             |               155 |  0.0056 | 0.0094 | +0.6% [-1.3, +2.4]  |
| EPC: 2a-i Matched sample, pilot controls only (type, tenure, new)           |                71 |  0.0005 | 0.0081 | +0.1% [-1.5, +1.7]  |
| EPC: 2a-ii + log floor area, rooms, age band, energy rating                 |                71 |  0.004  | 0.007  | +0.4% [-1.0, +1.8]  |
| EPC: 2b Outcome: log price per m2 (+ same controls except area)             |                71 |  0.0039 | 0.0075 | +0.4% [-1.1, +1.9]  |
| EPC: 2c-i Composition: log floor area of homes sold                         |                71 | -0.0085 | 0.0084 | -0.8% [-2.5, +0.8]  |
| EPC: 2c-ii Composition: share built 2012 or later                           |                71 | -0.0076 | 0.0099 | -0.8% [-2.7, +1.2]  |
| SDID, pseudo-site donors, seed 7                                            |                63 |  0.0032 | 0.0088 | +0.3% [-1.4, +2.1]  |
| SDID, mean of 40 donor draws (SE: placebo and draw SD combined)             |                63 | -0.0047 | 0.0095 | -0.5% [-2.3, +1.4]  |

### Table D2. Callaway-Sant'Anna doubly robust (site x half-year; bootstrap B = 499)

| spec                                        |    att |   se_boot |   ci90_lo |   ci90_hi | equivalent_3pct   |   pretrend_p |   treated_sites |   n_sites |
|:--------------------------------------------|-------:|----------:|----------:|----------:|:------------------|-------------:|----------------:|----------:|
| Main: DR, full covariates, delta 1          | -0.023 |     0.031 |    -0.079 |     0.02  | False             |        0.457 |             192 |       355 |
| R1 No covariates                            | -0.029 |     0.031 |    -0.083 |     0.019 | False             |        0.515 |             192 |       355 |
| R2 delta 0 (base g-1)                       | -0.005 |     0.029 |    -0.056 |     0.04  | False             |        0.853 |             192 |       355 |
| R3 Existing homes only                      | -0.031 |     0.031 |    -0.082 |     0.019 | False             |        0.595 |             192 |       355 |
| R4 Urban-fringe sites only                  | -0.05  |     0.048 |    -0.107 |     0.021 | False             |        0.207 |              69 |       123 |
| R5 Drop two 1 km sites                      | -0.023 |     0.031 |    -0.079 |     0.02  | False             |        0.457 |             192 |       355 |
| W Main: DR, full covariates, sales-weighted | -0.008 |     0.05  |    -0.107 |     0.049 | False             |        0.296 |             192 |       355 |
| W-R1 No covariates                          | -0.03  |     0.02  |    -0.066 |    -0     | False             |        0.034 |             192 |       355 |
| W-R2 delta 0 (base g-1)                     | -0.017 |     0.037 |    -0.078 |     0.028 | False             |        0.119 |             192 |       355 |
| W-R3 Existing homes only                    |  0.001 |     0.043 |    -0.071 |     0.059 | False             |        0.406 |             192 |       355 |
| W-R4 Urban-fringe sites only                | -0.01  |     0.082 |    -0.132 |     0.076 | False             |        0.146 |              69 |       123 |

### Table D3. Equivalence (TOST) against +/-3% (+/-0.0296 log points), 90% CI

| design                                                    |   beta |     se |   ci90_lo |   ci90_hi | equivalent_3pct   |
|:----------------------------------------------------------|-------:|-------:|----------:|----------:|:------------------|
| T1 ring DiD (urban fringe 2024-25)                        | 0.0003 | 0.0078 |   -0.0125 |    0.0132 | True              |
| 1a All sites, inner ring only                             | 0.006  | 0.0098 |   -0.0101 |    0.0221 | True              |
| 1f Treatment = works start if earlier than reference date | 0.0026 | 0.0086 |   -0.0116 |    0.0168 | True              |

### Table B1. Bird species per checklist near future gain sites vs 2-4 km, 2015-23 (PPML, site FE)

| spec                                                |   beta |     se | % [95% CI]           |   sites |   rows | reading                  |
|:----------------------------------------------------|-------:|-------:|:---------------------|--------:|-------:|:-------------------------|
| 1 Main: richness, 0-1 km vs 2-4 km, effort controls | 0.0603 | 0.0486 | +6.2% [-3.4, +16.8]  |     124 |  66598 | inconclusive             |
| 2 No effort controls                                | 0.0617 | 0.0518 | +6.4% [-3.9, +17.7]  |     124 |  66598 | inconclusive             |
| 3 0-500 m vs 2-4 km                                 | 0.1123 | 0.0745 | +11.9% [-3.3, +29.5] |     124 |  59710 | inconclusive             |
| 4 All sites with checklists in both rings           | 0.0535 | 0.0472 | +5.5% [-3.8, +15.7]  |     298 | 100203 | inconclusive             |
| 5 Farmland Bird Index species                       | 0.1369 | 0.0537 | +14.7% [+3.2, +27.4] |     124 |  66598 | richer near future sites |
