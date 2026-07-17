# S.I.R.E.M. Source Inventory

This inventory is source-grounded only in locally available files. The expected directory `docs/research/sirem_sources/` was not present at audit time. The available source PDFs were found in the project root under different names.

## Source Availability

| Expected source | Local status | Local file used | Notes |
|---|---|---|---|
| Di Leva thesis, 2016 | MISSING | N/A | No local readable file matching Di Leva 2016 was found. S.I.R.E.M.-specific claims from this source are not used. |
| Relevant thesis pages approx. 57-98 | PARTIALLY AVAILABLE | `phd thesis_Simona Mancini.pdf` | This file is titled "MEASUREMENT REGISTER, PROTOCOLS AND PROCEDURES" in PDF metadata and contains S.I.R.E.M. material on pages 61-69 plus annex/reference material. It is not labelled Di Leva 2016. |
| Mancini et al. 2018 | MISSING | N/A | A reference appears on thesis page 91, but no standalone 2018 PDF was found. |
| Mancini et al. 2022 | AVAILABLE | `ijerph-19-06056-v2.pdf` | Readable IJERPH paper: Mancini et al., 2022. |
| Earlier S.I.R.E.M. paper | AVAILABLE | `ENED-55.pdf` | WSEAS/ENED paper on S.I.R.E.M.(c) model, local root file. |

## Local Document Inventory

| File | Author(s) | Year | Source type | Language | Relevant pages | Equations | Parameter table | Experimental protocol | Calibration | STELLA implementation | RAD7 comparison/use | Primary/secondary |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|
| `ENED-55.pdf` | Simona Mancini, Michele Guida, Domenico Guida, Albina Cuomo, Pierfrancesco Fiore, Enrico Sicignano | 2014 | Conference/proceedings paper | English | 1, 4-9 | Describes S.I.R.E.M. as coupled ODE/STELLA model but PDF text extraction did not expose full equations | Yes, Table 2 on p.8 | Yes, pp.5-8 | RAD7 annual/lab calibration not detailed; RAD7 setup/protocol described | Yes, p.5, Fig.2 | Yes, RAD7/HSEC p.5-6; comparison p.8 | Primary |
| `phd thesis_Simona Mancini.pdf` | Simona Mancini | PDF metadata date 2018; thesis/archive content references 2016-2018 work | Thesis/archive/protocol document | English | 61-69, 76, 91, 94 | Yes, Eq.(1), Eq.(2), Eq.(3), pp.63-65 | Yes, Table 1 p.65 | Yes, pp.65-68 and annex p.94 | RAD7 characteristics and protocol; explicit calibration procedure not fully specified | Refers to software designed for solving ODEs; SIREM software context pp.61, 65, 76 | Yes, RAD7 on pp.65-68 | Primary/working thesis-like source, exact thesis identity requires confirmation |
| `ijerph-19-06056-v2.pdf` | Simona Mancini, Martins Vilnitis, Natasa Todorovic, Jovana Nikolov, Michele Guida | 2022 | Peer-reviewed journal article | English | 2-7 | Yes, Eq.(1), Eq.(2), pp.4-5 | Yes, Table 5 p.7 | Yes, pp.2-6 | RAD7 calibration in certified laboratory mentioned p.2; full calibration protocol not provided | Software is future-oriented; no STELLA implementation exposed | Yes, RAD7/CRM and measurements pp.2-6 | Primary |

## Missing or Not Fully Readable Sources

- `docs/research/sirem_sources/` is absent.
- Di Leva thesis, 2016 is absent.
- Mancini et al. 2018 standalone source is absent. Thesis page 91 cites: Mancini S., Guida M., Guida D., Cuomo A., Ismail A., "Modelling of indoor Radon activity concentration dynamics and its validation through in-situ measurements on regional scale", 2018, but the local PDF is not available.
- Equation layout in PDF extraction is partially degraded on thesis page 65. Eq.(3) needs manual visual/source confirmation before use in code.

