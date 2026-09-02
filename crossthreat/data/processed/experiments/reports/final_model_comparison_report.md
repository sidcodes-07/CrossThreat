# Real-data model inventory and comparison report

This inventory was compiled from the project’s existing implementations and saved real-data artifacts; no duplicate model files were created.

## 1) Existing model inventory

| Model | Existing implementation | Genuine architecture? | Training pipeline connected? | Status |
|---|---|---|---|---|
| Random Forest | Yes | Yes | Yes | TRAINED + TESTED |
| CNN | Yes | Yes | Yes | TRAINED + TESTED |
| LSTM | Yes | Yes | Yes | TRAINED + TESTED |
| Transformer | Yes | Yes | Yes | TRAINED + TESTED |
| Mamba | Yes (state-space block) | Yes, genuine Mamba-style state-space block | Partial but real-data run exists | TRAINED + TESTED (NF-only run) |
| ViT | Yes (transformer encoder adaptation) | Partial: supports sequential flow windows, but it is not a true vision transformer | Partial but real-data run exists | TRAINED + TESTED (NF-only run) |
| Swin | No | N/A | No | NOT IMPLEMENTED / NOT SCIENTIFICALLY VALID FOR THIS DATA |

## 2) What was reused

- [engines/baseline_model.py](../../../../engines/baseline_model.py) for the Random Forest baseline.
- [engines/temporal_model.py](../../../../engines/temporal_model.py) for the temporal LSTM forecasting setup.
- [engines/model_trainer.py](../../../../engines/model_trainer.py) for the CNN / LSTM / Transformer training loop.
- [engines/model_ablation.py](../../../../engines/model_ablation.py) for the existing Mamba and Transformer-style ablation models.
- [scripts/real_multidataset_training.py](../../../../scripts/real_multidataset_training.py) for the real-data chronology + benchmark pipeline.
- [scripts/train_mamba_vit_real.py](../../../../scripts/train_mamba_vit_real.py) for the NF-UNSW Mamba/ViT real-data run.
- [engines/data_pipeline.py](../../../../engines/data_pipeline.py) for the real data loading and chronological split logic.

No new model files were created to avoid duplicate implementations.

## 3) What was fixed

- Reused the existing canonical feature mapping instead of inventing a new one: `protocol`, `duration_ms`, `in_bytes`, `out_bytes`, `in_packets`, `out_packets`, `tcp_flags`.
- Kept the real chronological 80/20 split and avoided random shuffling.
- Kept train-only scaling and windowing inside the train/test partition to prevent leakage.
- Documented that the Swin model is not implemented and is not scientifically defensible for 1D flow-sequence tabular data.

## 4) What was newly implemented

None. This report documents the existing project implementations and their real-data status. The project already contained the required model families; no duplicate Mamba, ViT, or Swin implementations were introduced.

## 5) Dataset and split details

Datasets used:
- CIC-IDS2017
- CIC-IDS2018
- NF-UNSW-NB15-v3

Split policy:
- Chronological 80/20 train/test split by timestamp.
- No random shuffle before split.
- Feature scaling fit on train only.
- Sliding windows created strictly within each partition, so no train/test boundary leakage.

Canonical feature schema used for the valid cross-dataset benchmark:
- `protocol`
- `duration_ms`
- `in_bytes`
- `out_bytes`
- `in_packets`
- `out_packets`
- `tcp_flags`

The following were excluded from the benchmark to avoid leakage and schema mismatch: IPs, flow IDs, ports, timestamps for direct value usage, and any dataset-specific identifiers.

## 6) Training results

The ranking below emphasizes attack recall, attack F1, balanced accuracy, and weighted F1 rather than raw accuracy because the benign class dominates most flow datasets.

### Best same-dataset results from the real-data artifacts

| Dataset | Model | Accuracy | Balanced Acc. | Macro F1 | Weighted F1 | Attack Precision | Attack Recall | Attack F1 | Benign Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NF-UNSW-NB15-v3 | Random Forest | 0.9975 | 0.9938 | 0.9911 | 0.9975 | 0.9777 | 0.9894 | 0.9835 | 0.9982 |
| NF-UNSW-NB15-v3 | Transformer | 0.9640 | 0.7841 | 0.8431 | 0.9601 | 0.9190 | 0.5724 | 0.7054 | 0.9959 |
| NF-UNSW-NB15-v3 | CNN | 0.9574 | 0.7458 | 0.8073 | 0.9517 | 0.8884 | 0.4967 | 0.6371 | 0.9949 |
| NF-UNSW-NB15-v3 | LSTM | 0.9527 | 0.7524 | 0.7983 | 0.9482 | 0.7811 | 0.5166 | 0.6219 | 0.9882 |
| NF-UNSW-NB15-v3 | Mamba | 0.9625 | 0.8224 | 0.8526 | 0.9607 | 0.8088 | 0.6574 | 0.7253 | 0.9873 |
| NF-UNSW-NB15-v3 | ViT | 0.9601 | 0.8308 | 0.8489 | 0.9590 | 0.7650 | 0.6786 | 0.7192 | 0.9830 |
| CIC-IDS2018 | Transformer | 0.9439 | 0.8282 | 0.8766 | 0.9394 | 0.9691 | 0.6602 | 0.7854 | 0.9961 |
| CIC-IDS2018 | Random Forest | 0.9270 | 0.7654 | 0.8260 | 0.9174 | 1.0000 | 0.5307 | 0.6934 | 1.0000 |
| CIC-IDS2018 | LSTM | 0.9064 | 0.6990 | 0.7585 | 0.8887 | 1.0000 | 0.3981 | 0.5694 | 1.0000 |
| CIC-IDS2018 | CNN | 0.8996 | 0.6772 | 0.7336 | 0.8785 | 1.0000 | 0.3544 | 0.5233 | 1.0000 |
| CIC-IDS2017 | Random Forest | 0.9312 | 0.8479 | 0.8819 | 0.9275 | 0.9341 | 0.7083 | 0.8057 | 0.9874 |

## 7) Test results and confusion matrices

Representative confusion matrices from the saved results:
- NF-UNSW-NB15-v3 Random Forest: `[[9226, 17], [8, 745]]`
- NF-UNSW-NB15-v3 Transformer: `[[9205, 38], [322, 431]]`
- CIC-IDS2018 Transformer: `[[3344, 13], [210, 408]]`
- CIC-IDS2018 Random Forest: `[[3357, 0], [290, 328]]`

These matrices support the same conclusion as the summary metrics: well-calibrated/strong attack detection is not a generic property of every model, and the majority benign class still inflates raw accuracy.

## 8) Per-class metrics

Per-class metrics are saved in the JSON artifacts under the dataset experiment folders and cover the trained benchmark models. The strongest same-dataset per-class performance is from the NF-UNSW Random Forest, followed by the NF-UNSW Transformer and CIC-IDS2018 Transformer. The Mamba/ViT artifacts exist as binary summaries rather than full multi-class confusion/per-class tables; they still show strong sensitivity to the attack class relative to the baseline temporal models, but not better than the best Random Forest.

## 9) Calibration

Current project outputs do not include ECE or Brier score calculations, and there is no calibration stage in the saved training artifacts. Because of that, no trustworthy calibrated-confidence claim can be made for any model from the present results alone.

Status: calibration not yet evaluated in the project’s real-data pipeline.

## 10) Leakage findings

- No source/destination IP features were used in the canonical benchmark pipeline.
- The dataset split was chronological and not shuffled; this avoids train/test leakage from time ordering. 
- Windowing was performed within each partition to prevent future observations leaking into the current prediction window.
- The scaler was fit on training data only and applied to test data.
- No direct target leakage was found in the canonical feature set.
- The remaining risk is temporal autocorrelation within the same attack burst; this is a legitimate real-world challenge, not a preprocessing leak, and it is not fully removed by chronological split alone.

This means the reported metrics are credible for the benchmarked subset but still reflect real network burst structure rather than an artificial “random split” benchmark.

## 11) Cross-dataset results

Only the common compatible features were used for cross-dataset comparison.

| Direction | Model | Accuracy | Balanced Acc. | Macro F1 | Attack Recall | Attack F1 |
|---|---|---:|---:|---:|---:|---:|
| CIC-IDS2018 -> NF-UNSW-NB15-v3 | Random Forest | 0.8928 | 0.4943 | 0.4887 | 0.0252 | 0.0342 |
| NF-UNSW-NB15-v3 -> CIC-IDS2018 | Random Forest | 0.4818 | 0.4027 | 0.3876 | 0.2880 | 0.1474 |

Conclusion: there is no trustworthy cross-dataset winner. Both directions fail badly under domain shift, which means the real benchmark is still the same-dataset performance.

## 12) Final model ranking

Ranked by attack-detection quality, not raw accuracy alone:

1. Best attack detector: NF-UNSW-NB15-v3 Random Forest
   - Best attack recall: 0.9894
   - Best attack F1: 0.9835
   - Best overall combination of precision, recall, and balanced accuracy

2. Best forecasting model (windowed next-state prediction): NF-UNSW-NB15-v3 Random Forest
   - Uses the time-ordered window inputs and still achieves best recall/F1 in the forecasting formulation.
   - Best deep forecasting alternative: CIC-IDS2018 Transformer with attack recall 0.6602 and attack F1 0.7854.

3. Best calibrated / high-confidence model: not established
   - No ECE or Brier score was computed in the project artifacts.
   - This means the project cannot claim a calibrated-confidence winner from the current outputs.

4. Best cross-dataset model: none
   - Both directions fail badly under domain shift.

## 13) Final status summary

- Random Forest: TRAINED + TESTED
- CNN: TRAINED + TESTED
- LSTM: TRAINED + TESTED
- Transformer: TRAINED + TESTED
- Mamba: TRAINED + TESTED (NF-only real-data run)
- ViT: TRAINED + TESTED (NF-only real-data run, but not a true vision transformer)
- Swin: NOT IMPLEMENTED / NOT SCIENTIFICALLY VALID FOR THIS DATA

The project contains genuine model implementations for the required comparison, but it does not contain a defensible Swin implementation for 1D flow-sequence attack detection, and it does not provide calibration metrics for a high-confidence ranking.
