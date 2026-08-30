import os
import glob
import pickle
import pandas as pd
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from baseline_model import CurrentStateClassifier
from temporal_model import TemporalWorldModel
from stage_mapper import StageMapper
from evidence_engine import EvidenceEngine

app = FastAPI(title="CrossThreat API Server", version="2.0.0")

# Enable CORS for Next.js app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_DIR = "c:/CyberShield/crossthreat/data/processed"
RAW_DIR       = "c:/CyberShield/crossthreat/data/raw"

# ── Load global resources ──────────────────────────────────────────────────
with open(os.path.join(PROCESSED_DIR, "metadata.pkl"), "rb") as f:
    metadata = pickle.load(f)
feature_cols = metadata['feature_cols']
label_map    = metadata['label_mapping']
inv_label_map = {v: k for k, v in label_map.items()}

# ── Initialize engines ─────────────────────────────────────────────────────
current_classifier = CurrentStateClassifier()
stage_mapper       = StageMapper(feature_cols)
evidence_engine    = EvidenceEngine()

# ── Initialize LSTM ────────────────────────────────────────────────────────
with open(os.path.join(PROCESSED_DIR, "temporal_model_dims.pkl"), "rb") as f:
    dims = pickle.load(f)

lstm_model = TemporalWorldModel(
    input_dim=dims['input_dim'],
    hidden_dim=dims['hidden_dim'],
    num_classes=dims['num_classes']
)
lstm_model.load_state_dict(
    torch.load(os.path.join(PROCESSED_DIR, "temporal_model.pth"),
               map_location=torch.device('cpu'))
)
lstm_model.eval()


# ── Pydantic models ────────────────────────────────────────────────────────
class GeneralizationResult(BaseModel):
    indist_accuracy: float
    ood_accuracy: float
    accuracy_delta: float
    ood_sequences: int


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/generalization", response_model=GeneralizationResult)
def get_generalization():
    path = os.path.join(PROCESSED_DIR, "generalization_results.pkl")
    if not os.path.exists(path):
        from generalization_test import run_generalization_test
        run_generalization_test()

    if not os.path.exists(path):
        raise HTTPException(status_code=500,
                            detail="Generalization test results could not be found.")

    with open(path, "rb") as f:
        res = pickle.load(f)
    return res


@app.get("/api/replay/list", response_model=List[str])
def get_replay_hosts():
    test_df = pd.read_pickle(os.path.join(PROCESSED_DIR, "test_windows.pkl"))
    # Prioritise hosts that have the most attack-type diversity
    hosts_by_attacks = (
        test_df.groupby('Host')['Label']
        .nunique()
        .sort_values(ascending=False)
        .index.tolist()
    )
    return hosts_by_attacks


@app.get("/api/replay/host/{host_ip}")
def get_host_sequence(host_ip: str):
    """
    Returns a chronological replay for a single host.

    Temporal model audit note
    ─────────────────────────
    HostSequenceDataset trains the LSTM to predict labels[i+seq_len]
    from features[i : i+seq_len].  That is:
        input  = windows [t-5, t-4, t-3, t-2, t-1]   (the past)
        target = label  of window t                    (the next, unseen window)

    So at each replay step t we:
        • Show window t-1 as CURRENT OBSERVED
        • Run the LSTM on [t-5 : t-1] → FORECAST of window t
        • Reveal labels[t]            as ACTUAL FUTURE
        • lead_time = timestamp[t] − timestamp[t-1]   (real, not hardcoded)
    """
    test_df = pd.read_pickle(os.path.join(PROCESSED_DIR, "test_windows.pkl"))

    host_windows = (
        test_df[test_df['Host'] == host_ip]
        .sort_values('TimeWindow')
        .reset_index(drop=True)
    )

    # Need at least seq_len + 2 rows:
    #   seq_len windows as input, 1 "current observed", 1 "actual future"
    seq_len = 5
    if len(host_windows) < seq_len + 2:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough windows for host {host_ip} "
                   f"(have {len(host_windows)}, need ≥ {seq_len + 2})."
        )

    # Raw datetime timestamps (for real lead-time calculation)
    raw_ts    = host_windows['TimeWindow']
    disp_ts   = raw_ts.dt.strftime("%H:%M:%S").values

    X_scaled  = host_windows[feature_cols].values.astype(np.float32)
    str_labels = host_windows['Label'].values   # string labels

    timeline_steps   = []
    forecast_all     = []
    actual_all       = []

    # t is the index of the ACTUAL FUTURE window.
    # input sequence  = X_scaled[t-seq_len : t]  → windows [t-5 .. t-1]
    # current observed = window t-1
    # actual future    = window t
    for t in range(seq_len, len(host_windows)):

        # ── Current observed (window t-1) ─────────────────────────────────
        current_observed_label = str_labels[t - 1]
        current_observed_time  = disp_ts[t - 1]

        scaled_row_current = X_scaled[t - 1].reshape(1, -1)
        raw_row_current    = evidence_engine.scaler.inverse_transform(scaled_row_current)[0]
        raw_row_dict       = {col: float(raw_row_current[i])
                              for i, col in enumerate(feature_cols)}

        # ── Baseline classifier (classifies current observed window t-1) ──
        baseline_res  = current_classifier.predict_state(raw_row_current)
        baseline_pred = baseline_res["state"]
        baseline_prob = baseline_res["probabilities"][baseline_pred]

        baseline_shap     = evidence_engine.explain_baseline(raw_row_current)
        baseline_shap_top = [{"feature": f, "value": v}
                              for f, v in baseline_shap[:5]]

        # ── MITRE stage of the CURRENT window (label-gated rule engine) ───
        current_stage_res = stage_mapper.resolve_stage(baseline_pred, raw_row_current)

        # ── LSTM Temporal Forecast ─────────────────────────────────────────
        # Input: windows [t-seq_len .. t-1] (the past 5 windows)
        # Output: predicted label for window t (the next, unseen window)
        input_seq = X_scaled[t - seq_len : t]  # shape: (5, 16)

        lstm_attributions, forecast_label, forecast_prob = (
            evidence_engine.explain_temporal(lstm_model, input_seq)
        )
        lstm_attributions_top = [{"feature": f, "value": v}
                                  for f, v in lstm_attributions[:5]]

        # ── Actual future (window t) ───────────────────────────────────────
        actual_future_label = str_labels[t]
        actual_future_time  = disp_ts[t]

        # ── Forecast validation ────────────────────────────────────────────
        forecast_correct = bool(forecast_label == actual_future_label)

        # ── Real lead time (seconds between window t-1 and t) ─────────────
        lead_time_seconds = float(
            (raw_ts.iloc[t] - raw_ts.iloc[t - 1]).total_seconds()
        )

        # ── MITRE stage of the FORECAST (label-only, no future features) ──
        forecast_mitre_stage = stage_mapper.map_label(forecast_label)

        # Accumulate for summary
        forecast_all.append(forecast_label)
        actual_all.append(actual_future_label)

        timeline_steps.append({
            "step": t - seq_len + 1,

            # Current observed (window t-1 — last window in the input)
            "current_observed_label": current_observed_label,
            "current_observed_time":  current_observed_time,

            # Baseline classifier output
            "baseline_predicted_state": baseline_pred,
            "baseline_probability":     baseline_prob,
            "baseline_shap":            baseline_shap_top,

            # Current MITRE stage (from baseline prediction + rule engine)
            "current_mitre_stage": current_stage_res["final_stage"],
            "current_rule_stage":  current_stage_res["rule_stage"],
            "triggered_rules":     current_stage_res["triggered_rules"],
            "detection_source":    current_stage_res["detection_source"],

            # LSTM forecast (predicting window t)
            "forecast_next_state":   forecast_label,
            "forecast_probability":  forecast_prob,
            "forecast_mitre_stage":  forecast_mitre_stage,
            "forecast_attribution":  lstm_attributions_top,

            # Actual future (window t — revealed after forecast)
            "actual_future_label": actual_future_label,
            "actual_future_time":  actual_future_time,

            # Validation
            "forecast_correct":    forecast_correct,
            "lead_time_seconds":   lead_time_seconds,

            # Raw feature values for frontend rendering
            "metrics": raw_row_dict,
        })

    # ── Summary metrics ────────────────────────────────────────────────────
    unique_labels = sorted(
        set(actual_all + forecast_all),
        key=lambda x: label_map.get(x, 999)
    )

    overall_acc = float(accuracy_score(actual_all, forecast_all))

    prec_arr, rec_arr, f1_arr, _ = precision_recall_fscore_support(
        actual_all, forecast_all,
        labels=unique_labels, average=None, zero_division=0
    )
    per_class = {
        lbl: {
            "precision": float(prec_arr[i]),
            "recall":    float(rec_arr[i]),
            "f1":        float(f1_arr[i]),
        }
        for i, lbl in enumerate(unique_labels)
    }

    attack_pairs       = [(f, a) for f, a in zip(forecast_all, actual_all) if a != "Benign"]
    attack_fc_acc      = (
        sum(1 for f, a in attack_pairs if f == a) / len(attack_pairs)
        if attack_pairs else 0.0
    )
    mean_lead          = float(np.mean([s["lead_time_seconds"] for s in timeline_steps]))

    return {
        "host":        host_ip,
        "total_steps": len(timeline_steps),
        "steps":       timeline_steps,
        "summary": {
            "overall_forecast_accuracy":  overall_acc,
            "attack_forecast_accuracy":   float(attack_fc_acc),
            "total_attack_steps":         len(attack_pairs),
            "mean_lead_time_seconds":     mean_lead,
            "per_class_metrics":          per_class,
            "seq_len":                    seq_len,
            "window_size":                "30s",
        },
    }


@app.get("/api/audit/labels")
def get_label_audit():
    """
    Reads every raw CSV and reports unique labels + frequencies.
    Allows verification that data/raw CSVs are synthetic (mock) or real.
    """
    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))
    global_counts: Dict[str, int] = {}
    file_info = []

    for fpath in csv_files:
        try:
            df = pd.read_csv(fpath, usecols=["Label"])
            counts = df["Label"].value_counts().to_dict()
            for lbl, cnt in counts.items():
                global_counts[lbl] = global_counts.get(lbl, 0) + cnt
            file_info.append({
                "file":   os.path.basename(fpath),
                "rows":   len(df),
                "labels": counts,
            })
        except Exception as exc:
            file_info.append({
                "file":  os.path.basename(fpath),
                "error": str(exc),
            })

    return {
        "global_label_counts":     global_counts,
        "metadata_label_mapping":  label_map,
        "files":                   file_info,
        "data_source_note": (
            "CSVs in data/raw/ are synthetic mock data generated by "
            "mock_data_generator.py (~2000 rows each). "
            "Real CSE-CIC-IDS2018 files would be ~500 MB each."
        ),
    }


@app.get("/api/reproducibility")
def get_reproducibility():
    """
    Full experiment log for reproducibility.
    """
    train_files = [
        "Wednesday-14-02-2018.csv", "Thursday-15-02-2018.csv",
        "Friday-16-02-2018.csv",    "Tuesday-20-02-2018.csv",
        "Wednesday-21-02-2018.csv", "Thursday-22-02-2018.csv",
        "Friday-23-02-2018.csv",
    ]
    test_files = [
        "Wednesday-28-02-2018.csv",
        "Thursday-01-03-2018.csv",
        "Friday-02-03-2018.csv",
    ]
    return {
        "data_source": (
            "Synthetic mock data (mock_data_generator.py) — "
            "NOT real CSE-CIC-IDS2018 downloads"
        ),
        "dataset_files": {"train": train_files, "test": test_files},
        "features":      feature_cols,
        "feature_count": len(feature_cols),
        "window_size":   "30 seconds",
        "seq_len":       5,
        "label_mapping": label_map,
        "scaler":        "sklearn.StandardScaler (fit on train only)",
        "random_seed":   42,
        "model_config": {
            "type":          "LSTM",
            "input_dim":     dims['input_dim'],
            "hidden_dim":    dims['hidden_dim'],
            "num_classes":   dims['num_classes'],
            "num_layers":    1,
            "epochs":        8,
            "batch_size":    32,
            "optimizer":     "Adam",
            "learning_rate": 0.001,
            "loss":          "CrossEntropyLoss",
        },
        "training_target": (
            "label of window t+1 given input sequence [t-4, t-3, t-2, t-1, t]"
        ),
        "forecast_validation": (
            "At each replay step, forecast is generated from past 5 windows "
            "BEFORE the future window is revealed. "
            "forecast_correct compares forecast_label vs actual_future_label."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
