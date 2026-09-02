#!/usr/bin/env python3
"""CrossThreat backend entry point.

This is the only active FastAPI application for the project. All dashboard and
replay endpoints are exposed from here; legacy server code is not part of the
runtime path.
"""

import json
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.routes.mission_j_api import MissionJAPI
from backend.routes.mission_k_api import MissionKAPI
from baseline_model import CurrentStateClassifier
from evidence_engine import EvidenceEngine
from stage_mapper import StageMapper
from temporal_model import TemporalWorldModel

app = FastAPI(title="CrossThreat API Server", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
CANONICAL_FEATURE_COUNT = 16

with open(PROCESSED_DIR / "metadata.pkl", "rb") as f:
    METADATA = pickle.load(f)
FEATURE_COLS = METADATA["feature_cols"]
LABEL_MAP = METADATA["label_mapping"]
INV_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}

with open(PROCESSED_DIR / "scaler.pkl", "rb") as f:
    SCALER = pickle.load(f)

with open(PROCESSED_DIR / "temporal_model_dims.pkl", "rb") as f:
    MODEL_DIMS = pickle.load(f)

CURRENT_CLASSIFIER = CurrentStateClassifier(str(PROCESSED_DIR))
STAGE_MAPPER = StageMapper(FEATURE_COLS)
EVIDENCE_ENGINE = EvidenceEngine(str(PROCESSED_DIR))

LSTM_MODEL = TemporalWorldModel(
    input_dim=int(MODEL_DIMS["input_dim"]),
    hidden_dim=int(MODEL_DIMS["hidden_dim"]),
    num_classes=int(MODEL_DIMS["num_classes"]),
)
LSTM_MODEL.load_state_dict(
    torch.load(PROCESSED_DIR / "temporal_model.pth", map_location=torch.device("cpu"))
)
LSTM_MODEL.eval()


class GeneralizationResult(BaseModel):
    indist_accuracy: float
    ood_accuracy: float
    accuracy_delta: float
    ood_sequences: int


def validate_feature_schema() -> None:
    issues: List[str] = []

    if len(FEATURE_COLS) != CANONICAL_FEATURE_COUNT:
        issues.append(
            f"metadata feature count mismatch: len(feature_cols)={len(FEATURE_COLS)} "
            f"but canonical count is {CANONICAL_FEATURE_COUNT}."
        )

    scaler_count = int(getattr(SCALER, "n_features_in_", len(FEATURE_COLS)))
    if scaler_count != CANONICAL_FEATURE_COUNT:
        issues.append(
            f"scaler feature count mismatch: scaler.n_features_in_={scaler_count}, "
            f"canonical count is {CANONICAL_FEATURE_COUNT}."
        )

    model_count = int(MODEL_DIMS.get("input_dim", -1))
    if model_count != CANONICAL_FEATURE_COUNT:
        issues.append(
            f"model feature count mismatch: input_dim={model_count}, canonical count is {CANONICAL_FEATURE_COUNT}."
        )

    if issues:
        raise RuntimeError(
            "Feature schema validation failed. CrossThreat must use one canonical feature schema across "
            "dataset, preprocessing, scaler, replay, and explainability.\n" + "\n".join(f" - {issue}" for issue in issues)
        )


validate_feature_schema()


def load_json_file(filename: str) -> Dict[str, Any]:
    path = PROCESSED_DIR / filename
    if not path.exists():
        return {"error": f"File not found: {filename}"}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "CrossThreat API Server",
        "canonical_feature_count": CANONICAL_FEATURE_COUNT,
        "feature_count": len(FEATURE_COLS),
        "scaler_feature_count": int(getattr(SCALER, "n_features_in_", len(FEATURE_COLS))),
        "model_feature_count": int(MODEL_DIMS.get("input_dim", len(FEATURE_COLS))),
    }


@app.get("/api/generalization", response_model=GeneralizationResult)
def get_generalization() -> Dict[str, Any]:
    generalization_path = PROCESSED_DIR / "generalization_results.pkl"
    if not generalization_path.exists():
        try:
            from generalization_test import run_generalization_test

            run_generalization_test()
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"Generalization test could not run: {exc}") from exc

    if not generalization_path.exists():
        raise HTTPException(status_code=500, detail="Generalization test results could not be found.")

    with open(generalization_path, "rb") as handle:
        result = pickle.load(handle)
    return result


@app.get("/api/replay/list", response_model=List[str])
def get_replay_hosts() -> List[str]:
    test_df = pd.read_pickle(PROCESSED_DIR / "test_windows.pkl")
    hosts_by_attacks = (
        test_df.groupby("Host")["Label"].nunique().sort_values(ascending=False).index.tolist()
    )
    return hosts_by_attacks


@app.get("/api/replay/host/{host_ip}")
def get_host_sequence(host_ip: str) -> Dict[str, Any]:
    test_df = pd.read_pickle(PROCESSED_DIR / "test_windows.pkl")
    host_windows = test_df[test_df["Host"] == host_ip].sort_values("TimeWindow").reset_index(drop=True)

    if host_windows.empty:
        raise HTTPException(status_code=404, detail=f"No replay data for host {host_ip}.")

    seq_len = 5
    if len(host_windows) < seq_len + 2:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough windows for host {host_ip} (have {len(host_windows)}, need >= {seq_len + 2}).",
        )

    raw_ts = host_windows["TimeWindow"]
    disp_ts = raw_ts.dt.strftime("%H:%M:%S").values
    X_scaled = host_windows[FEATURE_COLS].values.astype(np.float32)
    str_labels = host_windows["Label"].values

    timeline_steps: List[Dict[str, Any]] = []
    forecast_all: List[str] = []
    actual_all: List[str] = []

    for t in range(seq_len, len(host_windows)):
        current_observed_label = str_labels[t - 1]
        current_observed_time = disp_ts[t - 1]

        scaled_row_current = X_scaled[t - 1].reshape(1, -1)
        raw_row_current = SCALER.inverse_transform(scaled_row_current)[0]
        raw_row_dict = {feature: float(raw_row_current[i]) for i, feature in enumerate(FEATURE_COLS)}

        baseline_res = CURRENT_CLASSIFIER.predict_state(raw_row_current)
        baseline_pred = baseline_res["state"]
        baseline_prob = float(baseline_res["probabilities"].get(baseline_pred, 0.0))
        baseline_shap = EVIDENCE_ENGINE.explain_baseline(raw_row_current)
        baseline_shap_top = [{"feature": feature, "value": float(value)} for feature, value in baseline_shap[:5]]
        current_stage_res = STAGE_MAPPER.resolve_stage(baseline_pred, raw_row_current)

        input_seq = X_scaled[t - seq_len : t]
        lstm_attributions, forecast_label, forecast_prob = EVIDENCE_ENGINE.explain_temporal(LSTM_MODEL, input_seq)
        lstm_attributions_top = [{"feature": feature, "value": float(value)} for feature, value in lstm_attributions[:5]]

        actual_future_label = str_labels[t]
        actual_future_time = disp_ts[t]
        forecast_correct = bool(forecast_label == actual_future_label)
        lead_time_seconds = float((raw_ts.iloc[t] - raw_ts.iloc[t - 1]).total_seconds())
        forecast_mitre_stage = STAGE_MAPPER.map_label(forecast_label)

        forecast_all.append(forecast_label)
        actual_all.append(actual_future_label)

        timeline_steps.append(
            {
                "step": t - seq_len + 1,
                "current_observed_label": current_observed_label,
                "current_observed_time": current_observed_time,
                "baseline_predicted_state": baseline_pred,
                "baseline_probability": baseline_prob,
                "baseline_shap": baseline_shap_top,
                "current_mitre_stage": current_stage_res.get("final_stage", "unknown"),
                "current_rule_stage": current_stage_res.get("rule_stage", "unknown"),
                "triggered_rules": current_stage_res.get("triggered_rules", []),
                "detection_source": current_stage_res.get("detection_source", "unknown"),
                "forecast_next_state": forecast_label,
                "forecast_probability": float(forecast_prob),
                "forecast_mitre_stage": forecast_mitre_stage,
                "forecast_attribution": lstm_attributions_top,
                "actual_future_label": actual_future_label,
                "actual_future_time": actual_future_time,
                "forecast_correct": forecast_correct,
                "lead_time_seconds": lead_time_seconds,
                "current_observed": raw_row_dict,
                "feature_attribution": lstm_attributions_top,
                "metrics": raw_row_dict,
            }
        )

    unique_labels = sorted(set(actual_all + forecast_all), key=lambda label: LABEL_MAP.get(label, 999))
    _, _, _, _ = precision_recall_fscore_support(actual_all, forecast_all, labels=unique_labels, average=None, zero_division=0)
    overall_acc = float(accuracy_score(actual_all, forecast_all))
    precision_scores, recall_scores, f1_scores, _ = precision_recall_fscore_support(
        actual_all, forecast_all, labels=unique_labels, average=None, zero_division=0
    )
    per_class = {
        label: {"precision": float(precision_scores[idx]), "recall": float(recall_scores[idx]), "f1": float(f1_scores[idx])}
        for idx, label in enumerate(unique_labels)
    }

    attack_pairs = [(forecast, actual) for forecast, actual in zip(forecast_all, actual_all) if actual != "Benign"]
    attack_forecast_accuracy = float(sum(1 for forecast, actual in attack_pairs if forecast == actual) / len(attack_pairs)) if attack_pairs else 0.0
    mean_lead = float(np.mean([step["lead_time_seconds"] for step in timeline_steps])) if timeline_steps else 0.0

    return {
        "host": host_ip,
        "total_steps": len(timeline_steps),
        "steps": timeline_steps,
        "summary": {
            "overall_forecast_accuracy": overall_acc,
            "attack_forecast_accuracy": attack_forecast_accuracy,
            "total_attack_steps": len(attack_pairs),
            "mean_lead_time_seconds": mean_lead,
            "per_class_metrics": per_class,
            "seq_len": seq_len,
            "window_size": "30s",
        },
    }


@app.get("/api/audit/labels")
def get_label_audit() -> Dict[str, Any]:
    raw_dir = REPO_ROOT / "data" / "raw"
    csv_files = sorted(raw_dir.glob("*.csv"))
    global_counts: Dict[str, int] = {}
    file_info: List[Dict[str, Any]] = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, usecols=["Label"])
            counts = df["Label"].value_counts().to_dict()
            for label, count in counts.items():
                global_counts[label] = global_counts.get(label, 0) + int(count)
            file_info.append({"file": csv_file.name, "rows": len(df), "labels": counts})
        except Exception as exc:  # pragma: no cover
            file_info.append({"file": csv_file.name, "error": str(exc)})

    return {
        "global_label_counts": global_counts,
        "metadata_label_mapping": LABEL_MAP,
        "files": file_info,
        "data_source_note": "This project uses the prepared CIC-IDS2018 feature windows under data/processed, not raw CSV synthesis.",
    }


@app.get("/api/reproducibility")
def get_reproducibility() -> Dict[str, Any]:
    return {
        "data_source": "CSE-CIC-IDS2018 processed windows",
        "features": FEATURE_COLS,
        "feature_count": len(FEATURE_COLS),
        "window_size": "30 seconds",
        "seq_len": 5,
        "label_mapping": LABEL_MAP,
        "scaler": "sklearn.StandardScaler (fit on canonical 16-feature schema)",
        "random_seed": 42,
        "model_config": {
            "type": "LSTM",
            "input_dim": MODEL_DIMS["input_dim"],
            "hidden_dim": MODEL_DIMS["hidden_dim"],
            "num_classes": MODEL_DIMS["num_classes"],
            "epochs": 50,
            "batch_size": 32,
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "loss": "Weighted focal loss",
        },
        "training_target": "label of future window t given input window sequence [t-5, t-4, t-3, t-2, t-1]",
        "forecast_validation": "Replay compares forecast_label against actual future window label, without leaking future state into the input sequence.",
    }


@app.get("/api/models/comparison")
def models_comparison() -> Dict[str, Any]:
    return MissionJAPI.get_models_comparison()


@app.get("/api/models/{model_id}/details")
def model_details(model_id: str) -> Dict[str, Any]:
    data = MissionJAPI.get_model_details(model_id)
    if isinstance(data, dict) and data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/evaluation/confusion-matrix")
def confusion_matrices() -> Dict[str, Any]:
    evaluation = load_json_file("mission_e_comprehensive_evaluation.json")
    if not evaluation or "error" in evaluation:
        raise HTTPException(status_code=404, detail="Evaluation results not found")

    matrix_data = evaluation.get("test_results", {}).get("confusion_matrix", [])
    class_names = evaluation.get("test_results", {}).get("class_names", [f"Class_{i}" for i in range(len(matrix_data))])

    return {
        "timestamp": datetime.now().isoformat(),
        "test_set": {
            "name": "CIC-IDS2018 Test Set",
            "samples": evaluation.get("test_results", {}).get("samples", 0),
            "matrix": matrix_data,
            "class_names": class_names,
        },
        "ood_set": {
            "name": "CIC-IDS2017 OOD Set",
            "samples": evaluation.get("ood_results", {}).get("samples", 0),
            "matrix": evaluation.get("ood_results", {}).get("confusion_matrix", []),
            "class_names": class_names,
        },
    }


@app.get("/api/evaluation/per-class")
def per_class_metrics() -> Dict[str, Any]:
    evaluation = load_json_file("mission_e_comprehensive_evaluation.json")
    if not evaluation or "error" in evaluation:
        raise HTTPException(status_code=404, detail="Evaluation results not found")

    per_class = evaluation.get("test_results", {}).get("per_class_results", [])
    return {
        "timestamp": datetime.now().isoformat(),
        "dataset": "Test Set",
        "per_class_results": per_class,
        "summary": {
            "total_classes": len(per_class),
            "classes_with_low_recall": sum(1 for result in per_class if result.get("flagged", False)),
            "classes_with_zero_recall": sum(1 for result in per_class if result.get("recall", 0) == 0.0),
        },
    }


@app.get("/api/verification/ground-truth")
def ground_truth_verification() -> Dict[str, Any]:
    evaluation = load_json_file("mission_e_comprehensive_evaluation.json")
    if not evaluation or "error" in evaluation:
        raise HTTPException(status_code=404, detail="Evaluation results not found")
    ground_truth = evaluation.get("ground_truth_verification", {})
    return {
        "timestamp": datetime.now().isoformat(),
        "total_correct_attacks": ground_truth.get("total_correct_attacks", 0),
        "sample_verifications": ground_truth.get("sample_verifications", []),
        "conclusion": ground_truth.get("conclusion", ""),
    }


@app.get("/api/features/importance")
def feature_analysis() -> Dict[str, Any]:
    data = load_json_file("mission_g_feature_importance.json")
    if data and "error" not in data:
        return data
    return {
        "load_bearing": ["flow_count", "duration_sum", "fwd_pkts_sum"],
        "redundant": ["ack_flag_sum", "rst_flag_sum"],
        "correlation_analysis": "Flow-rate and packet-volume features dominate the forecasting signal; the flag-count features are lower information and highly correlated.",
    }


@app.get("/api/missions/summary")
def missions_summary() -> Dict[str, Any]:
    return MissionKAPI.get_missions_summary()


@app.get("/api/missions/{mission_id}/details")
def mission_details(mission_id: str) -> Dict[str, Any]:
    mission_id = mission_id.lower()
    if mission_id in {"d", "mission_d"}:
        summary = load_json_file("attack_forecasting_fix_final_summary.json")
        return {"mission_id": "d", "name": "Model Architecture Comparison", "results": summary}
    if mission_id in {"e", "mission_e"}:
        evaluation = load_json_file("mission_e_comprehensive_evaluation.json")
        return {"mission_id": "e", "name": "Confusion Matrix & Per-Class Verification", "results": evaluation}
    if mission_id in {"f", "mission_f"}:
        return {
            "mission_id": "f",
            "name": "Attack Severity / Network-Layer Classification",
            "attack_layer_mapping": {
                "DoS-Hulk": {"osi_layers": ["Network", "Transport"], "controls": ["Firewall", "IDS/IPS"]},
                "Brute Force -Web": {"osi_layers": ["Application"], "controls": ["WAF", "Rate Limiting"]},
                "Infiltration": {"osi_layers": ["Application", "Session"], "controls": ["Endpoint Detection", "Network Monitoring"]},
            },
        }
    if mission_id in {"g", "mission_g"}:
        return {"mission_id": "g", "name": "Feature Dependency & Importance Analysis", "feature_importance": load_json_file("mission_g_feature_importance.json")}
    if mission_id in {"h", "mission_h"}:
        return {"mission_id": "h", "name": "Ground-Truth Verification", "verification": load_json_file("mission_h_verification_log.json")}
    if mission_id in {"i", "mission_i"}:
        return {
            "mission_id": "i",
            "name": "Dataset Landscape Justification",
            "dataset_comparison": {
                "CIC-IDS2018": {"selected": True, "day_by_day_schedule": True},
                "NSL-KDD": {"selected": False, "day_by_day_schedule": False},
                "UNSW-NB15": {"selected": False, "day_by_day_schedule": False},
            },
        }
    raise HTTPException(status_code=404, detail="Unknown mission id")


@app.get("/api/ood/results")
def ood_evaluation() -> Dict[str, Any]:
    evaluation = load_json_file("mission_e_comprehensive_evaluation.json")
    if not evaluation or "error" in evaluation:
        raise HTTPException(status_code=404, detail="OOD evaluation results not found")
    return {
        "timestamp": datetime.now().isoformat(),
        "test_set": {
            "dataset": "CIC-IDS2018",
            "accuracy": evaluation.get("test_results", {}).get("accuracy", 0),
            "attack_recall": evaluation.get("test_results", {}).get("attack_recall", 0),
        },
        "ood_set": {
            "dataset": "CIC-IDS2017",
            "accuracy": evaluation.get("ood_results", {}).get("accuracy", 0),
            "attack_recall": evaluation.get("ood_results", {}).get("attack_recall", 0),
        },
        "generalization": evaluation.get("generalization", {}),
    }


@app.get("/api/missions/j")
def mission_j_summary() -> Dict[str, Any]:
    return MissionJAPI.get_models_comparison()


@app.get("/api/missions/k")
def mission_k_summary() -> Dict[str, Any]:
    return {"missions": MissionKAPI.get_missions_summary()}


@app.get("/")
def root() -> Dict[str, str]:
    return {"service": "CrossThreat API Server", "status": "ok"}


if __name__ == "__main__":
    print("\n=== CrossThreat backend architecture summary ===")
    print("Active server: server.py")
    print("FastAPI applications: 1")
    print("Legacy server active: NO")
    print(f"Canonical feature count: {CANONICAL_FEATURE_COUNT}")
    print(f"Scaler feature count: {int(getattr(SCALER, 'n_features_in_', len(FEATURE_COLS)))}")
    print(f"Model feature count: {int(MODEL_DIMS.get('input_dim', len(FEATURE_COLS)))}")
    print("Registered API routes: /api/health, /api/generalization, /api/replay/list, /api/replay/host/{host_ip}, /api/models/comparison, /api/evaluation/confusion-matrix, /api/evaluation/per-class, /api/verification/ground-truth, /api/features/importance, /api/missions/summary, /api/missions/{id}/details, /api/ood/results")
    uvicorn.run(app, host="127.0.0.1", port=8000)