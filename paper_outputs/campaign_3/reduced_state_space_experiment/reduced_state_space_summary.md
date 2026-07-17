# Reduced State-Space Experiment Summary

Campaign: 3 - RadonEye Salerno 2024 — pilot regime analysis
Algorithm version: reduced_state_space_experiment_v1

This is exploratory research software, not a certified radon risk assessment or ventilation-control tool.

## Model
`C_(k+1)=a_r*C_k+b_r+w_k`, `y_k=C_k+v_k`; state vector `x_k=[C_k]`.
The model estimates reduced apparent dynamics only and does not estimate ACH or material exhalation.

## Key rows
- Experiment A F1_no_future_event_knowledge R_high 1h: N=167, MAE=12.548, coverage=0.958
- Experiment A F1_no_future_event_knowledge R_high 3h: N=165, MAE=16.575, coverage=0.982
- Experiment A F1_no_future_event_knowledge R_high 6h: N=162, MAE=25.034, coverage=0.969
- Experiment A F1_no_future_event_knowledge R_low 1h: N=167, MAE=13.76, coverage=0.91
- Experiment A F1_no_future_event_knowledge R_low 3h: N=165, MAE=16.719, coverage=0.964
- Experiment A F1_no_future_event_knowledge R_low 6h: N=162, MAE=24.778, coverage=0.963
- Experiment A F1_no_future_event_knowledge R_nominal 1h: N=167, MAE=13.088, coverage=0.946
- Experiment A F1_no_future_event_knowledge R_nominal 3h: N=165, MAE=16.401, coverage=0.97
- Experiment A F1_no_future_event_knowledge R_nominal 6h: N=162, MAE=24.704, coverage=0.969
- Experiment A F2_known_intervention_scenario R_high 1h: N=167, MAE=12.83, coverage=0.958
- Experiment A F2_known_intervention_scenario R_high 3h: N=165, MAE=15.913, coverage=0.988
- Experiment A F2_known_intervention_scenario R_high 6h: N=162, MAE=21.24, coverage=0.988

Duplicate forecast keys: 0
