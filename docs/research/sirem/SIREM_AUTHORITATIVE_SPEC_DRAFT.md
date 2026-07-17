# S.I.R.E.M. Authoritative Formulation Evidence Pack - DRAFT — REQUIRES SALERNO TEAM CONFIRMATION

This draft is not an authoritative S.I.R.E.M. specification. It is an evidence pack grounded only in local files found in the project root. It must be confirmed by the Salerno team before any equation is implemented or presented as definitive.

## Confirmed Local Sources

- `ENED-55.pdf`: 2014 S.I.R.E.M.(c) paper, pp.1, 5-9.
- `phd thesis_Simona Mancini.pdf`: thesis/archive PDF, pp.61-69, 76, 91, 94.
- `ijerph-19-06056-v2.pdf`: Mancini et al. 2022 IJERPH article, pp.2-7.

Missing sources:

- Di Leva thesis, 2016.
- Standalone Mancini et al. 2018 source.
- Original STELLA model file.

## Confirmed Formulation Elements

### Common Model Purpose

The available sources describe S.I.R.E.M. as a simplified, semi-experimental approach for estimating indoor radon concentration and source contributions using onsite measurements and room/material geometry. ENED 2014 describes it as a model for building-material contribution and indoor radon accumulation (pp.1, 5-9). The thesis describes SIREM as a predictive model intended as a software algorithm for real-time radon sensor management (pp.61-65). IJERPH 2022 describes a simplified procedure using onsite measurements to test a predictive indoor radon model (pp.2-7).

### Confirmed Assumptions

- Single well-mixed room/zone: thesis p.63; IJERPH 2022 p.5.
- Steady-state analysis: thesis p.63; ENED p.5; IJERPH 2022 p.5.
- Semi-experimental model relying on onsite measurements: ENED pp.1,5-8; thesis pp.64-68; IJERPH pp.2-7.
- Sources considered include soil, building materials, outdoor air and potentially water/gas depending site: thesis pp.61-65; ENED pp.5-8; IJERPH pp.5-7.
- RAD7 is the principal instrument in available S.I.R.E.M. sources: ENED pp.5-8; thesis pp.65-68; IJERPH pp.2-6.

## Confirmed Equations

See `SIREM_EQUATION_INVENTORY.md`, `sirem_equation_inventory.csv`, and `sirem_equation_inventory.json`.

The strongest equation evidence is:

1. Thesis Eq.(1), p.63:
   - `Cus = (Nus/Vus) lambda_Rn`
   - `Cds = (Nds/Vds) lambda_Rn`
   - `Cbm = (Nbm/Vbm) lambda_Rn`
   - `qi,j = Vi lambda_i,j`
2. Thesis Eq.(2), p.64 and IJERPH Eq.(2), p.5:
   - `Ci = (Ni/Vi) lambda_Rn = f(Cus, Cds, Cbm, Ce, qi,j)`
3. IJERPH Eq.(1), pp.4-5:
   - `CeqD = ED / lambda`

Thesis Eq.(3), p.65, is marked `SOURCE_REVIEW_REQUIRED` because the PDF text extraction damages the fraction layout. It appears to be the single simplified expression for indoor concentration using building-material and soil terms, but it should not be implemented until manually confirmed.

## Confirmed Parameters

The thesis Table 1 on p.65 lists 18 S.I.R.E.M. parameters:

`Vi`, `Sbm`, `ws`, `lambda_rn`, `Dbm`, `gbm`, `Sis`, `sigma`, `wf`, `Cds`, `Cus`, `epsilon`, `De`, `m`, `Cbm`, `DeltaP`, `lambda`, `Ce`.

IJERPH 2022 Table 5 on p.7 lists the reduced 2022 case parameters:

`Vi`, `Sbm`, `Ci`, `Ceq`, `ED`, `Cbm`, `lambda_rn`, `lambda`.

## Reconstructed Workflow from Available Sources

1. Onsite measurements: RAD7 is used for indoor air, soil gas, outdoor air, building material and water where relevant (thesis pp.65-68; ENED pp.5-8; IJERPH pp.2-6).
2. Laboratory/chamber measurements: ENED and IJERPH describe RAD7/HSEC surface emission measurements; IJERPH uses closed-loop wall measurement with short cycle times (ENED pp.5-6; IJERPH pp.4-5).
3. Room geometry inputs: room volume and surface/material geometry are required (thesis p.65; ENED p.8; IJERPH p.7).
4. Source-contribution calculation: source terms include disturbed/undisturbed soil, building materials, outdoor air and possibly water/gas (thesis pp.63-65; ENED pp.7-8).
5. Ventilation/air-exchange treatment: `lambda` or `qi,j` represents ventilation/air exchange; IJERPH 2022 indirectly estimates leakage/air exchange from equilibrium concentration (IJERPH pp.5-7).
6. Steady-state calculation: available sources explicitly use steady-state and well-mixed assumptions (thesis p.63; ENED p.5; IJERPH p.5).
7. Calibration: RAD7 certified calibration is mentioned in IJERPH p.2; detailed calibration factors are not specified in available sources.
8. Comparison with measured room concentration: ENED p.8 compares calculated 111 Bq/m3 with measured 119 Bq/m3; thesis pp.68-69 compares S.I.R.E.M. calculations with three test-site measured values; IJERPH pp.6-7 compares model and measured concentrations.
9. RAD7 comparison: RAD7 provides measurement input, not a separate model comparator, in available sources.
10. STELLA implementation: ENED p.5 states S.I.R.E.M.(c) was developed in STELLA; no STELLA file is available.

Steps not fully specified in available sources:

- Full derivation and exact grouping of Eq.(3): `NOT_FULLY_SPECIFIED_IN_AVAILABLE_SOURCES`.
- Exact calibration procedure and correction factors: `NOT_FULLY_SPECIFIED_IN_AVAILABLE_SOURCES`.
- Transfer from yellow-tuff onsite value to a model-ready flux/source term: `NOT_FULLY_SPECIFIED_IN_AVAILABLE_SOURCES`.

## Version Comparison

| Version/source | Model purpose | Site type | Equation structure | Source terms | Ventilation treatment | Measurements | Software implementation | Validation | Differences |
|---|---|---|---|---|---|---|---|---|---|
| ENED 2014 | Assess building-material contribution to indoor radon | Concrete slab-on-grade test house | Described as STELLA ODE sector model; parameter table given | Soil, building material, water/gas if present | Ventilation rate in Table 2; simulations vary ventilation | RAD7 indoor, soil, BM; HSEC | STELLA stated | Calculated 111 Bq/m3 vs measured 119 Bq/m3 | Earliest available local S.I.R.E.M.(c) description; explicit STELLA framing |
| Thesis/archive | Predictive model for real-time radon sensor system | Three Campania test houses | Eq.(1), Eq.(2), Eq.(3) and 18-parameter table | Soil, BM, outdoor air, water/gas if relevant | Lambda factors 0.9, 0.4, 0.2 in validation | RAD7 simultaneous indoor, wall, soil measurements | Software/ODE context; later product idea | Three-site measured vs analytical comparison | More explicit equations and parameter list |
| Mancini et al. 2022 | Test predictive model and infer ventilation factor | Second-floor urban apartment with yellow tuff | Reduced diffusion/equilibrium Eq.(1) plus general Eq.(2) | Building material mainly; no floor/soil contribution for studied second-floor room | Lambda indirectly calculated from model/measurements | RAD7 indoor, BM, tuff/brick walls | Future software, not STELLA file | Table 6 model vs measured concentrations | Reduced source structure for apartment where soil contribution is excluded |

Common across versions:

- Onsite measurements are central.
- RAD7-based protocols are central.
- Room/material geometry is required.
- Well-mixed and steady-state simplifications appear repeatedly.
- S.I.R.E.M. is not presented as a sequential forecasting model in available sources.

Differences:

- ENED 2014 emphasizes building materials in a concrete house and STELLA.
- Thesis/archive gives fuller soil+BM equations and parameter table.
- IJERPH 2022 uses a reduced diffusion-entry framing for an upper-floor yellow-tuff apartment and calculates/infer air exchange factors.

Questions requiring Salerno confirmation:

- Which source/version is the authoritative baseline?
- Which exact Eq.(3) form and symbol notation should be used?
- Whether the 2022 reduced formulation should replace or only specialize the thesis Eq.(3) for upper-floor/tuff apartment cases.

## RadonEye Feasibility

| Required S.I.R.E.M. element | RadonEye apartment status | Notes |
|---|---|---|
| Radon time series | AVAILABLE | RadonEye provides campaign time series, but source protocols use RAD7. |
| Room volume | PARTIALLY_AVAILABLE | Only if research-context metadata is entered and confirmed. |
| Wall/material surfaces | MISSING | Required for source-term calculation. |
| Yellow-tuff measurements | PARTIALLY_AVAILABLE | Do not convert `160.8 +/- 4.5 Bq/m3` without formula, geometry and exposed area. |
| Yellow-tuff onsite measurement meaning | MISSING | Need whether value is surface emission, wall-proximity air, chamber concentration, etc. |
| Outdoor radon | MISSING | `Ce` unavailable. |
| Ventilation measurement | MISSING | Event windows exist, but no measured air exchange. |
| Exact opening times | PARTIALLY_AVAILABLE | Provisional stored timestamps only. |
| Soil contribution | MISSING | May be less relevant for upper-floor apartment, but needs source-team confirmation. |
| Water contribution | MISSING | Not assessed. |
| Sensor metadata | PARTIALLY_AVAILABLE | RadonEye metadata exists in app; not a RAD7 protocol equivalent. |
| Timestamp timezone | PARTIALLY_AVAILABLE | Requires confirmation. |

## Boundary Between S.I.R.E.M. and Future Dynamic Extension

| Directly supported by S.I.R.E.M. sources | Proposed dynamic extension |
|---|---|
| Onsite RAD7 measurements from indoor air, soil, building materials and outdoor/water where relevant | RadonEye-native continuous forecast workflow |
| Room volume and material/surface geometry inputs | State-space representation |
| Well-mixed single-zone approximation | Sequential updating |
| Steady-state source-contribution calculation | Kalman/EKF filtering |
| Ventilation/air-exchange factor as parameter or inferred value | Process noise and measurement noise states |
| STELLA ODE implementation in ENED 2014 | Prediction intervals |
| RAD7/HSEC material measurement protocol | Regime-validity flags |
| Comparison of model-calculated and measured indoor concentrations | 1h, 3h, 6h forecasts |

No available source identifies Kalman filtering, state-space modelling, or short-horizon forecasts as original S.I.R.E.M.

## Unresolved Questions

See `SIREM_CONFIRMATION_QUESTIONS.md`.

## Implementation Warning

Do not implement S.I.R.E.M. code from this draft. The draft is sufficient for manuscript planning and collaborator review, but not for an authoritative computational implementation.

