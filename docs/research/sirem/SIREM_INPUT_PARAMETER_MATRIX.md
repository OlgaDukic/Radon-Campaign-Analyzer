# S.I.R.E.M. Input Parameter Matrix

Status uses the current RadonEye apartment context only where known from project data and local sources. Do not convert the yellow-tuff value into an exhalation rate unless the source-specific formula, geometry and exposed surface are confirmed.

| Original symbol / item | English description | Serbian working description | Unit | Measurement method in sources | Source page | Required equipment | Directly measured | Inferred/calculated | Site-specific | Current RadonEye apartment status |
|---|---|---|---|---|---:|---|---|---|---|---|
| `Ci` | Indoor radon concentration | unutrasnja koncentracija radona | Bq/m3 or kBq/m3 | RAD7 CRM indoor air; current project has RadonEye time series | IJERPH 2022 pp.3,5-7; thesis p.64 | RAD7/RadonEye depending campaign | Yes | No | Yes | AVAILABLE as RadonEye time series, but not the same instrument/protocol as S.I.R.E.M. source |
| `Ceq`, `CeqD` | Equilibrium indoor radon concentration | ravnotezna koncentracija u sobi | kBq/m3 in IJERPH tables | Closed room measurement after defined closure period | IJERPH 2022 pp.4-7 | RAD7 CRM | Yes | Used to infer leakage/air exchange | Yes | PARTIALLY_AVAILABLE if documented closure intervals are accepted; exact local-time event log still provisional |
| `ED` | Total rate of diffusion radon entry | ukupni difuzioni ulaz radona | SOURCE_REVIEW_REQUIRED | Sum of radon fluxes through surfaces | IJERPH 2022 p.5, p.7 | RAD7 + surface emission chamber / surface flux setup | No, calculated from fluxes | Yes | Yes | MISSING |
| `Cbm` / `CBM` | Building-material radon concentration / emanation | radon iz gradjevinskog materijala | kBq/m3 in ENED/IJERPH tables | RAD7 with HSEC / wall measurement | ENED p.8; thesis p.65; IJERPH pp.4,6-7 | RAD7 + HSEC | Yes in S.I.R.E.M. protocol | Sometimes used as input | Yes | PARTIALLY_AVAILABLE: yellow-tuff value mentioned externally, but geometry/exposed surface/formula not confirmed |
| `Vi` | Volume of room | zapremina prostorije | m3 | Geometric measurement | ENED p.8; thesis p.65; IJERPH p.7 | Tape/geometry survey | Yes | No | Yes | PARTIALLY_AVAILABLE if research-context room volume is provided |
| `Sbm` | Building material surface area | povrsina gradjevinskog materijala | m2 | Geometric characterization of room/material surfaces | ENED p.8; thesis p.65; IJERPH p.7 | Geometry survey | Yes | No | Yes | MISSING |
| `ws` | Building material coverage | pokrivka/debljina/pokrivenost materijala | m in ENED table for concrete coverage | Site/building geometry/material characterization | ENED p.8; thesis p.65 | Geometry/material survey | Yes/assumed depending case | Sometimes assumed | Yes | MISSING |
| `lambda_Rn` / `lambda_rn` | Radon decay constant | konstanta raspada radona | s-1 | Physical constant | ENED p.8; thesis p.65; IJERPH p.7 | None | No | Known constant | No | AVAILABLE as physical constant, source value should be confirmed |
| `Dbm` / `De,BM` | Building-material effective diffusion coefficient | efektivni difuzioni koeficijent materijala | m2/s | Literature or material-specific value | ENED p.8; thesis p.65 | Literature/material testing | No | Yes | Material-specific | MISSING |
| `gbm` / `g` | Building-material coverage factor | faktor pokrivenosti materijala | dimensionless | Literature/assumption | ENED p.8; thesis p.65 | Literature/source confirmation | No | Yes | Material-specific | MISSING |
| `Sis` | Surface in contact with soil | povrsina u kontaktu sa tlom | m2 | Geometry survey | ENED p.8; thesis p.65 | Geometry survey | Yes | No | Yes | MISSING / likely not applicable for second-floor RadonEye room unless source confirms |
| `sigma` | Open area fraction | frakcija otvorene povrsine | dimensionless | Site/material defects/cracks assessment | ENED pp.7-8; thesis p.65 | Site inspection | Possibly | Often assumed | Yes | MISSING |
| `wf` | Foundation width | sirina temelja | m | Geometry/site data | ENED p.8; thesis p.65 | Geometry survey | Yes | No | Yes | MISSING / likely not applicable for second-floor apartment |
| `Cds` | Disturbed soil radon activity concentration | radon u poremecenom tlu pored zgrade | kBq/m3 | RAD7 soil-gas measurement near building | ENED pp.6-8; thesis pp.63-66 | RAD7 soil-gas setup | Yes | No | Yes | MISSING |
| `Cus` / `CUS` | Undisturbed soil radon activity concentration | radon u neporemecenom tlu | kBq/m3 | RAD7 soil-gas measurement beyond influence of building | ENED pp.6-8; thesis pp.63-66 | RAD7 soil-gas setup | Yes | No | Yes | MISSING |
| `epsilon` | Soil porosity | poroznost tla | dimensionless | Literature or site characterization | ENED p.8; thesis p.65 | Soil data/literature | No | Yes | Site/material-specific | MISSING |
| `De` | Soil effective diffusion coefficient | efektivni difuzioni koeficijent tla | m2/s | Literature/site characterization | ENED p.8; thesis p.65 | Soil data/literature | No | Yes | Site-specific | MISSING |
| `m` | Water saturation fraction | frakcija zasicenja vodom | dimensionless | Literature/site characterization | ENED p.8; thesis p.65 | Soil data/literature | No | Yes | Site-specific | MISSING |
| `DeltaP` | Pressure difference soil-external air | razlika pritiska tlo-spoljni vazduh | Pa | Calculated by basic equations or measured | ENED p.8; thesis p.68 | Pressure/temperature data | Maybe | Yes | Yes | MISSING |
| `lambda` | Ventilation rate factor / air exchange | faktor ventilacije / izmena vazduha | h-1 in IJERPH/ENED tables | Assumed, measured, or indirectly calculated by convergence | ENED p.8; thesis pp.68; IJERPH pp.5-7 | Event log, airflow, tracer or model inversion | Partially | Yes | Yes | PARTIALLY_AVAILABLE as documented opening intervals, but no measured air exchange |
| `Ce` | Outdoor radon concentration | spoljasnja koncentracija radona | Bq/m3 | Outdoor air measurement or assumed 0 in ENED table | ENED p.8; thesis p.65 | RAD7 outdoor air | Yes/assumed | Sometimes assumed | Yes | MISSING |
| water contribution | Radon from water | doprinos vode | Bq/m3 or source-specific | RAD7 water protocol; ignored when below detection in case studies | Thesis pp.61,67; ENED p.7 | RAD7 water setup | Yes when relevant | No | Site-specific | MISSING / likely not assessed |
| RAD7 measurements | Real-time radon measurements | RAD7 merenja | Bq/m3/kBq/m3 | RAD7 protocols | ENED pp.5-8; thesis pp.65-68; IJERPH pp.2-6 | RAD7, HSEC, drying unit | Yes | No | Yes | MISSING for RadonEye campaign; RadonEye is different instrument |
| STELLA model inputs | ODE software inputs | ulazi za STELLA model | mixed | Source states model implemented in STELLA | ENED p.5 | STELLA software | No | Yes | Model-specific | MISSING |
| calibration factors | Calibration details | kalibracija | SOURCE_REVIEW_REQUIRED | RAD7 calibrated in certified lab mentioned | IJERPH p.2 | Calibration lab/certificate | No | No | Instrument-specific | MISSING |

## Summary for RadonEye Apartment

- AVAILABLE: radon time series.
- PARTIALLY_AVAILABLE: room volume if research-context metadata is entered; closure/opening event windows are provisional; yellow-tuff concentration exists as a value but lacks confirmed S.I.R.E.M. geometry/formula context.
- MISSING: RAD7/HSEC wall emission protocol data, exposed surface areas, outdoor radon, measured ventilation/air exchange, soil/water contribution assessment, STELLA file, authoritative static S.I.R.E.M. calculation for the apartment, timestamp/timezone confirmation.

