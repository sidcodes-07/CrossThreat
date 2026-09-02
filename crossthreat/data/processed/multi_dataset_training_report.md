# Multi-Dataset Training Report

## Dataset overview
- Real datasets used: cic_ids2017, cic_ids2018, nf_unsw_nb15_v3
- Controlled training configuration: 50000 rows per dataset, window size 5
- All preprocessing fitted on train only.
- Temporal splits are chronological and no train/test overlap is allowed.

## 80/20 split methodology
- Each dataset was sorted by flow start timestamp.
- The first 80% of rows were used for training and the final 20% for testing.
- No random shuffling was applied before splitting.

## Feature schema
- Canonical features: protocol, duration_ms, in_bytes, out_bytes, in_packets, out_packets, tcp_flags
- These were mapped from the real NF-UNSW and CIC schemas before the train/test split.

## Label taxonomy
- Labels were preserved as original values and reduced to a binary canonical detection label: Benign = 0, Attack = 1.
- This preserves the dataset-specific identities while allowing cross-dataset evaluation under a consistent attack-vs-benign detection target.

## Model comparison
| Experiment | Model | Accuracy | Attack Recall | Macro F1 | Latency (s/sample) |
|---|---|---:|---:|---:|---:|
| cic_ids2017 | random_forest | 0.9312 | 0.7083 | 0.8819 | 0.000133 |
| cic_ids2017 | cnn | 0.7987 | 0.0000 | 0.4440 | 0.000012 |
| cic_ids2017 | lstm | 0.7987 | 0.0000 | 0.4440 | 0.000010 |
| cic_ids2017 | transformer | 0.9060 | 0.6417 | 0.8382 | 0.000010 |
| cic_ids2018 | random_forest | 0.9270 | 0.5307 | 0.8260 | 0.000019 |
| cic_ids2018 | cnn | 0.8996 | 0.3544 | 0.7336 | 0.000009 |
| cic_ids2018 | lstm | 0.9064 | 0.3981 | 0.7585 | 0.000009 |
| cic_ids2018 | transformer | 0.9439 | 0.6602 | 0.8766 | 0.000010 |
| nf_unsw_nb15_v3 | random_forest | 0.9975 | 0.9894 | 0.9911 | 0.000010 |
| nf_unsw_nb15_v3 | cnn | 0.9574 | 0.4967 | 0.8073 | 0.000009 |
| nf_unsw_nb15_v3 | lstm | 0.9527 | 0.5166 | 0.7983 | 0.000008 |
| nf_unsw_nb15_v3 | transformer | 0.9640 | 0.5724 | 0.8431 | 0.000009 |
| cic_to_nf | random_forest | 0.8928 | 0.0252 | 0.4887 | 0.000000 |
| nf_to_cic | random_forest | 0.4818 | 0.2880 | 0.3876 | 0.000000 |

## Data leakage checks
- A chronological split was used for each dataset.
- The scaler was fit on train only and applied to test, preserving a valid evaluation protocol.
- Window creation was done inside each train/test partition to avoid cross-boundary leakage.

## Limitations
- This is a controlled, resource-aware run on a bounded subset of the actual datasets.
- Cross-dataset experiments are domain-shift studies rather than same-distribution benchmarks.
- Mamba was not trained in this environment because the mamba implementation is not installed in the runtime.

## Final conclusion
- This phase validates the real-data pipeline with chronological splits, explicit feature mapping, and train-only preprocessing.
- Results are valid for the configured subset and must be interpreted with the dataset and resource constraints explicitly recorded.
