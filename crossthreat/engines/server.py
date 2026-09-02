#!/usr/bin/env python3
"""CrossThreat backend entry point.

This is the only active FastAPI application for the project. All dashboard and
replay endpoints are exposed from here; legacy server code is not part of the
runtime path.
"""

import errno
import json
import os
import pickle
import socket
import sys
import time
from datetime import datetime
from functools import lru_cache
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
from sklearn.inspection import permutation_importance

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
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
PROTOCOL_NAMES = {
    "1": "ICMP",
    "2": "IGMP",
    "6": "TCP",
    "17": "UDP",
    "47": "GRE",
    "89": "OSPF",
    "132": "SCTP",
}


def format_protocol(protocol: Any) -> str:
    protocol_id = str(protocol)
    return f"{PROTOCOL_NAMES[protocol_id]} ({protocol_id})" if protocol_id in PROTOCOL_NAMES else f"Protocol {protocol_id}"


def numeric_total(value: Any) -> int | float:
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric

with open(PROCESSED_DIR / "metadata.pkl", "rb") as f:
    METADATA = pickle.load(f)
FEATURE_COLS = METADATA["feature_cols"]
LABEL_MAP = METADATA["label_mapping"]
INV_LABEL_MAP = LABEL_MAP

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


_FLOW_CACHE: pd.DataFrame | None = None
_RAW_FLOW_CACHE: pd.DataFrame | None = None


def get_live_flows() -> pd.DataFrame:
    """Load the current replay flow table once; all dashboard aggregates use this state."""
    global _FLOW_CACHE
    if _FLOW_CACHE is None:
        flow_path = PROCESSED_DIR / "test_windows.pkl"
        if not flow_path.exists():
            return pd.DataFrame()
        columns = [
            "TimeWindow", "Host", "IPV4_SRC_ADDR", "IPV4_DST_ADDR",
            "Protocol", "PROTOCOL", "L4_SRC_PORT", "L4_DST_PORT", "IN_BYTES",
            "OUT_BYTES", "IN_PKTS", "OUT_PKTS", "FLOW_DURATION_MILLISECONDS", "Label", "Attack",
        ]
        available = pd.read_pickle(flow_path)
        columns.extend(FEATURE_COLS)
        selected_columns = list(dict.fromkeys(column for column in columns if column in available.columns))
        _FLOW_CACHE = available[selected_columns].copy()
    return _FLOW_CACHE


def get_raw_network_flows() -> pd.DataFrame:
    global _RAW_FLOW_CACHE
    if _RAW_FLOW_CACHE is None:
        flows = get_live_flows()
        if flows.empty:
            return flows
        _RAW_FLOW_CACHE = flows.copy()
        scaled_features = flows[FEATURE_COLS].values.astype(np.float32)
        raw_features = SCALER.inverse_transform(scaled_features)
        for index, feature in enumerate(FEATURE_COLS):
            _RAW_FLOW_CACHE[feature] = raw_features[:, index]
    return _RAW_FLOW_CACHE


def get_replay_window(flows: pd.DataFrame) -> pd.DataFrame:
    if flows.empty:
        return flows
    cursor = int(time.time() / 2.5) % len(flows)
    return flows.iloc[: cursor + 1]


def get_replay_context(host: str | None = None, step: int | None = None) -> pd.DataFrame:
    flows = get_live_flows()
    if host and "Host" in flows.columns:
        flows = flows[flows["Host"].astype(str) == host]
    if flows.empty:
        return flows
    flows = flows.sort_values("TimeWindow").tail(64)
    if step is not None:
        flows = flows.iloc[:max(0, min(len(flows), 5 + max(step, 0)))]
    return flows


def get_dynamic_alerts(host: str | None = None, step: int | None = None) -> List[Dict[str, Any]]:
    flows = get_replay_context(host, step)
    if flows.empty or "Label" not in flows.columns:
        return []
    alerts: List[Dict[str, Any]] = []
    attack_flows = flows
    attack_flows = attack_flows[attack_flows["Label"].astype(str).str.lower() != "benign"].tail(100)
    for row_index, (_, row) in enumerate(attack_flows.iterrows()):
        label = str(row.get("Attack", row.get("Label", "Unknown")))
        timestamp = row.get("TimeWindow")
        alerts.append({
            "id": f"AL-{row_index + 1:06d}",
            "time": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
            "type": label,
            "source": str(row.get("IPV4_SRC_ADDR", row.get("Host", "Unknown"))),
            "destination": str(row.get("IPV4_DST_ADDR", "Unknown")),
            "severity": "High" if label.lower() not in {"benign", "normal"} else "Low",
            "status": "Active",
            "protocol": str(row.get("PROTOCOL", "Unknown")),
            "risk_score": 100 if label.lower() not in {"benign", "normal"} else 0,
        })
    return alerts


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


@lru_cache(maxsize=1)
def _get_replay_host_summaries() -> List[Dict[str, Any]]:
    test_df = get_live_flows()
    if test_df.empty or "Host" not in test_df.columns or "Label" not in test_df.columns:
        return []
    if "TimeWindow" not in test_df.columns:
        return []
    summaries: List[Dict[str, Any]] = []
    for host, group in test_df.groupby("Host"):
        replay_steps = max(min(int(group["TimeWindow"].nunique()), 64) - 5, 0)
        if replay_steps >= 7:
            summaries.append({
                "host": str(host),
                "flow_count": int(len(group)),
                "replay_steps": replay_steps,
            })
    return sorted(summaries, key=lambda item: item["flow_count"], reverse=True)


@app.get("/api/replay/list", response_model=List[str])
def get_replay_hosts() -> List[str]:
    return [summary["host"] for summary in _get_replay_host_summaries()]


@app.get("/api/replay/hosts")
def get_replay_host_summaries() -> Dict[str, Any]:
    return {
        "dataset": "NF-UNSW-NB15-v3",
        "mode": "replay",
        "hosts": _get_replay_host_summaries(),
    }


@app.get("/api/replay/host/{host_ip}")
@lru_cache(maxsize=64)
def get_host_sequence(host_ip: str) -> Dict[str, Any]:
    test_df = get_live_flows()
    host_windows = test_df[test_df["Host"] == host_ip].sort_values("TimeWindow").tail(64).reset_index(drop=True)

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
        baseline_shap_top = []
        current_stage_res = STAGE_MAPPER.resolve_stage(baseline_pred, raw_row_current)

        input_seq = X_scaled[t - seq_len : t]
        with torch.no_grad():
            logits = LSTM_MODEL(torch.tensor(input_seq, dtype=torch.float32).unsqueeze(0))
            probabilities = torch.softmax(logits, dim=1)[0]
        forecast_class = int(torch.argmax(probabilities).item())
        forecast_label = INV_LABEL_MAP[forecast_class]
        forecast_prob = float(probabilities[forecast_class].item())
        lstm_attributions_top = []

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




@app.get("/api/state/current")
def get_current_state(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    try:
        hosts = get_replay_hosts()
    except Exception:
        hosts = []
    host_ip = host or (hosts[0] if hosts else "")
    try:
        replay = get_host_sequence(host_ip)
    except HTTPException:
        replay = {"steps": [], "summary": {}}

    steps = replay.get("steps", [])
    if not steps:
        return {
            "current_stage": "—",
            "threat_level": "—",
            "risk_score": 0.0,
            "next_stage_forecast": "—",
            "probability": 0.0,
            "alternative_outcomes": [],
            "host": host_ip,
        }

    latest = steps[min(max(step or 0, 0), len(steps) - 1)]
    forecast_probability = float(latest.get("forecast_probability", 0.0))
    alternative = []
    for step in steps[-5:]:
        label = step.get("forecast_next_state", "Benign")
        probability = float(step.get("forecast_probability", 0.0))
        alternative.append({
            "label": label,
            "probability": round(probability * 100, 1),
            "stage": step.get("forecast_mitre_stage", "Phase A"),
        })

    return {
        "host": replay.get("host", host_ip),
        "current_stage": latest.get("current_mitre_stage", "Monitoring"),
        "threat_level": latest.get("forecast_next_state", "Benign"),
        "risk_score": round(forecast_probability * 100, 2),
        "next_stage_forecast": latest.get("forecast_mitre_stage", "Reconnaissance"),
        "probability": round(forecast_probability, 4),
        "alternative_outcomes": alternative,
    }


@app.get("/api/timeline/{host_ip}")
def get_timeline_summary(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    output = []
    for step in replay.get("steps", []):
        output.append({
            "stage": step.get("current_mitre_stage", "Monitoring"),
            "label": step.get("current_observed_label", "Benign"),
            "started": step.get("current_observed_time", "00:00:00"),
            "duration": f"{int(step.get('lead_time_seconds', 30))}s",
            "risk": round(float(step.get("forecast_probability", 0.0)) * 100, 1),
        })
    return output


@app.get("/api/timeline/{host_ip}/details")
def get_timeline_details(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    details = []
    for step in replay.get("steps", []):
        prob = float(step.get("forecast_probability", 0.0)) * 100.0
        severity = "High" if prob >= 75 else "Medium" if prob >= 45 else "Low"
        details.append({
            "stage": step.get("current_mitre_stage", "Monitoring"),
            "start_time": step.get("current_observed_time", "00:00:00"),
            "duration": f"{int(step.get('lead_time_seconds', 30))}s",
            "risk": round(prob, 1),
            "confidence": round(prob, 1),
            "description": f"Observed {step.get('current_observed_label', 'standard traffic')} and forecast transition into {step.get('forecast_next_state', 'Benign')} with {prob:.1f}% likelihood.",
            "severity": severity,
        })
    return details


@app.get("/api/timeline/{host_ip}/indicators")
def get_timeline_indicators(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    indicators = []
    for step in replay.get("steps", [])[:6]:
        risk = float(step.get("forecast_probability", 0.0)) * 100.0
        indicators.append({
            "name": step.get("forecast_next_state", "Benign"),
            "source": step.get("detection_source", "Replay pipeline"),
            "severity": "High" if risk >= 75 else "Medium" if risk >= 45 else "Low",
        })
    return indicators


@app.get("/api/timeline/{host_ip}/risk-history")
def get_risk_history(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    history = []
    for idx, step in enumerate(replay.get("steps", [])):
        prob = float(step.get("forecast_probability", 0.0)) * 100.0
        history.append({
            "step": idx + 1,
            "timestamp": step.get("current_observed_time", f"T{idx:02d}:00"),
            "risk_score": round(prob, 1),
        })
    return history


@app.get("/api/forecast/{host_ip}/transition-probs")
def get_transition_probs(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    counts: Dict[str, int] = {}
    for step in replay.get("steps", []):
        label = step.get("forecast_next_state", "Benign")
        counts[label] = counts.get(label, 0) + 1
    total = max(sum(counts.values()), 1)
    return [{"label": label, "value": round((count / total) * 100, 1)} for label, count in sorted(counts.items())]


@app.get("/api/forecast/{host_ip}/upcoming")
def get_upcoming_predictions(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    upcoming = []
    for step in replay.get("steps", [])[-5:]:
        probability = float(step.get("forecast_probability", 0.0)) * 100.0
        upcoming.append({
            "step": step.get("step"),
            "stage": step.get("forecast_next_state", "Benign"),
            "timestamp": step.get("actual_future_time", step.get("current_observed_time")),
            "probability": round(probability, 1),
            "risk": round(probability, 1),
        })
    return upcoming


@app.get("/api/forecast/{host_ip}/confidence-history")
def get_confidence_history(host_ip: str) -> List[Dict[str, Any]]:
    replay = get_host_sequence(host_ip)
    history = []
    for idx, step in enumerate(replay.get("steps", [])):
        history.append({
            "step": idx + 1,
            "timestamp": step.get("actual_future_time", step.get("current_observed_time", f"T{idx:02d}:00")),
            "probability": round(float(step.get("forecast_probability", 0.0)) * 100.0, 1),
        })
    return history


@app.get("/api/evidence/{forecast_id}")
def get_evidence(forecast_id: str, step: int | None = None) -> List[Dict[str, Any]]:
    replay = get_host_sequence(forecast_id)
    steps = replay.get("steps", [])
    if not steps:
        return []
    latest = steps[min(max(step if step is not None else len(steps) - 1, 0), len(steps) - 1)]
    host_windows = get_live_flows()
    host_windows = host_windows[host_windows["Host"] == forecast_id].sort_values("TimeWindow").tail(64).reset_index(drop=True)
    input_seq = host_windows[FEATURE_COLS].values.astype(np.float32)[-6:-1]
    forecast_class = next(
        (class_id for class_id, label in LABEL_MAP.items() if label == latest["forecast_next_state"]),
        None,
    )
    if forecast_class is None:
        raise HTTPException(status_code=422, detail="Forecast label is not present in the model label mapping.")
    attributions, label, probability = EVIDENCE_ENGINE.explain_temporal(
        LSTM_MODEL, input_seq, target_class_idx=forecast_class
    )
    evidence_items = []
    for feature, contribution in attributions[:5]:
        evidence_items.append({
            "label": feature,
            "value": contribution,
            "description": f"Input-gradient attribution for the {label} forecast at replay step {latest.get('step')}.",
            "explanation": f"{feature} contribution: {contribution:.6f}; model probability: {probability * 100:.1f}%.",
        })
    return evidence_items


@app.get("/api/network/topology")
def get_network_topology(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    flows = get_replay_context(host, step)
    flows = get_raw_network_flows().loc[flows.index] if not flows.empty else flows
    if flows.empty:
        return {"nodes": [], "edges": [], "summary": {"total_flows": 0, "active_connections": 0, "bytes": 0, "peak": 0}}
    flows = get_replay_window(flows)
    hosts = pd.unique(pd.concat([flows["IPV4_SRC_ADDR"], flows["IPV4_DST_ADDR"]], ignore_index=True))
    nodes = []
    for idx, host_ip in enumerate(hosts[:30]):
        host_flows = flows[(flows["IPV4_SRC_ADDR"] == host_ip) | (flows["IPV4_DST_ADDR"] == host_ip)]
        nodes.append({
            "id": str(host_ip),
            "label": host_ip.split(".")[-1] if "." in host_ip else f"H{idx + 1}",
            "x": f"{12 + ((idx % 5) * 19)}%",
            "y": f"{18 + ((idx // 5) * 16)}%",
            "severity": "high" if host_flows["Label"].astype(str).str.lower().ne("benign").any() else "low",
        })
    edges = []
    pair_columns = ["IPV4_SRC_ADDR", "IPV4_DST_ADDR"]
    for idx, pair in enumerate(flows.groupby(pair_columns, dropna=False).size().nlargest(100).index):
        edges.append({
            "source": str(pair[0]),
            "target": str(pair[1]),
            "value": int(flows[(flows["IPV4_SRC_ADDR"] == pair[0]) & (flows["IPV4_DST_ADDR"] == pair[1])].shape[0]),
            "severity": "medium",
        })
    byte_columns = [column for column in ["IN_BYTES", "OUT_BYTES"] if column in flows.columns]
    total_bytes = float(flows[byte_columns].fillna(0).sum().sum()) if byte_columns else 0.0
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_flows": int(len(flows)),
            "active_connections": int(flows[pair_columns].drop_duplicates().shape[0]),
            "bytes": numeric_total(total_bytes),
            "peak": int(flows.groupby("TimeWindow").size().max()) if "TimeWindow" in flows.columns else 0,
        },
    }


@app.get("/api/network/protocol-breakdown")
def get_protocol_breakdown(host: str | None = None, step: int | None = None) -> List[Dict[str, Any]]:
    flows = get_replay_context(host, step)
    if flows.empty or "Protocol" not in flows.columns:
        return []
    counts = flows["Protocol"].astype(str).value_counts()
    total = int(counts.sum())
    return [{"protocol": format_protocol(protocol), "protocol_id": protocol, "percent": round(float(count / total * 100), 2), "flows": int(count)} for protocol, count in counts.items()]


@app.get("/api/network/top-talkers")
def get_top_talkers() -> List[Dict[str, Any]]:
    flows = get_raw_network_flows()
    if flows.empty:
        return []
    flows = get_replay_window(flows)
    talkers = []
    for idx, (host_ip, group) in enumerate(flows.groupby("Host").size().nlargest(10).items()):
        talkers.append({
            "host": str(host_ip),
            "flows": int(group),
            "bytes": numeric_total(flows.loc[flows["Host"] == host_ip, ["IN_BYTES", "OUT_BYTES"]].fillna(0).sum().sum()),
            "risk": int(flows.loc[flows["Host"] == host_ip, "Label"].astype(str).str.lower().ne("benign").mean() * 100),
        })
    return talkers


@app.get("/api/network/top-pairs")
def get_top_pairs(host: str | None = None, step: int | None = None) -> List[Dict[str, Any]]:
    context = get_replay_context(host, step)
    flows = get_raw_network_flows().loc[context.index] if not context.empty else context
    if flows.empty:
        return []
    protocol_column = "Protocol" if "Protocol" in flows.columns else "PROTOCOL"
    rows = []
    for (source, destination, protocol), group in flows.groupby(["IPV4_SRC_ADDR", "IPV4_DST_ADDR", protocol_column], dropna=False):
        rows.append({
            "source": str(source),
            "dest": str(destination),
            "protocol": format_protocol(protocol),
            "protocol_id": str(protocol),
            "bytes": numeric_total(group[["IN_BYTES", "OUT_BYTES"]].fillna(0).sum().sum()),
            "packets": int(group[["IN_PKTS", "OUT_PKTS"]].fillna(0).sum().sum()),
        })
    return sorted(rows, key=lambda row: row["bytes"], reverse=True)[:20]


@app.get("/api/network/traffic-over-time")
def get_traffic_over_time(host: str | None = None, step: int | None = None) -> List[Dict[str, Any]]:
    context = get_replay_context(host, step)
    if context.empty or "TimeWindow" not in context.columns:
        return []
    grouped = context.groupby("TimeWindow", dropna=False)
    return [
        {"step": index + 1, "timestamp": str(timestamp), "flows": int(len(group))}
        for index, (timestamp, group) in enumerate(grouped)
    ]


@app.get("/api/alerts")
def get_alerts(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    return {"alerts": get_dynamic_alerts(host, step)}


@app.get("/api/alerts/summary")
def get_alert_summary(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    alerts = get_dynamic_alerts(host, step)
    return {"summary": {severity.lower(): sum(1 for alert in alerts if alert["severity"] == severity) for severity in ("High", "Medium", "Low")}}


@app.get("/api/alerts/{alert_id}/details")
def get_alert_details(alert_id: str, host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    alert = next((item for item in get_dynamic_alerts(host, step) if item["id"] == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    context = get_replay_context(host, step)
    flows = get_raw_network_flows().loc[context.index] if not context.empty else context
    source_flows = flows[flows["IPV4_SRC_ADDR"].astype(str) == alert["source"]] if not flows.empty else flows
    byte_columns = [column for column in ("IN_BYTES", "OUT_BYTES") if column in source_flows.columns]
    packet_columns = [column for column in ("IN_PKTS", "OUT_PKTS") if column in source_flows.columns]
    return {
        **alert,
        "alert_type": alert["type"],
        "ports": sorted({str(port) for port in source_flows["L4_DST_PORT"].dropna()}) if "L4_DST_PORT" in source_flows else [],
        "duration": float(source_flows["FLOW_DURATION_MILLISECONDS"].sum()) if "FLOW_DURATION_MILLISECONDS" in source_flows else 0,
        "packets": int(source_flows[packet_columns].fillna(0).sum().sum()) if packet_columns else 0,
        "bytes": float(source_flows[byte_columns].fillna(0).sum().sum()) if byte_columns else 0,
        "description": f"Observed {alert['type']} activity for source {alert['source']} in the current replay window.",
        "recommendations": [f"Investigate {alert['type']} activity on {alert['source']}.", "Review related flow records and isolate the host if the signal persists."],
        "related_events": [{"time": alert["time"], "text": f"{alert['type']} flow observed from {alert['source']}"}],
    }


@app.get("/api/models/performance")
def get_model_performance() -> Dict[str, Any]:
    evaluation = load_json_file("experiments/nf_unsw_nb15_v3/lstm_metrics.json")
    if evaluation.get("error"):
        raise HTTPException(status_code=404, detail="NF-UNSW-NB15-v3 LSTM performance not found")
    metrics = evaluation.get("metrics", {})
    results: Dict[str, Any] = {
        "dataset": "NF-UNSW-NB15-v3",
        "model": "LSTM",
        "accuracy": float(metrics.get("accuracy", 0) * 100),
        "precision": float(metrics.get("macro_precision", 0) * 100),
        "recall": float(metrics.get("macro_recall", 0) * 100),
        "f1": float(metrics.get("macro_f1", 0) * 100),
        "attack_precision": float(metrics.get("attack_precision", 0) * 100),
        "attack_recall": float(metrics.get("attack_recall", 0) * 100),
        "attack_f1": float(metrics.get("attack_f1", 0) * 100),
        "auc_roc": None,
        "metric_note": "AUC-ROC was not reported by the held-out LSTM evaluation artifact.",
    }
    probabilities = [
        max(float(value) for value in row) * 100
        for row in evaluation.get("probabilities", [])
        if isinstance(row, list) and row
    ]
    if probabilities:
        bins = np.linspace(0, 100, 11)
        counts, _ = np.histogram(probabilities, bins=bins)
        results["probability_distribution"] = [
            {"bucket": f"{int(bins[index])}-{int(bins[index + 1])}", "count": int(count)}
            for index, count in enumerate(counts)
        ]
    return results


@app.get("/api/models/feature-importance")
def get_model_feature_importance() -> Dict[str, Any]:
    flows = get_live_flows()
    if flows.empty:
        return {"top_features": []}
    feature_frame = flows[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0)
    labels = flows["Label"].map({label: index for index, label in LABEL_MAP.items()})
    valid = labels.notna()
    if not valid.any():
        return {"top_features": []}
    sample = feature_frame.loc[valid].tail(500)
    target = labels.loc[valid].tail(500).astype(int)
    model = CURRENT_CLASSIFIER.model
    result = permutation_importance(model, SCALER.transform(sample.to_numpy()), target, n_repeats=1, random_state=42, n_jobs=1)
    ranked = sorted(zip(FEATURE_COLS, result.importances_mean), key=lambda item: item[1], reverse=True)[:6]
    return {
        "dataset": "NF-UNSW-NB15-v3",
        "scope": "global permutation importance for baseline classifier",
        "top_features": [{"name": name, "importance": float(value)} for name, value in ranked],
    }


@app.get("/api/reports/summary")
def get_reports_summary(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    alerts = get_dynamic_alerts(host, step)
    return {
        "summary": {
            "total_attacks": len(alerts),
            "high_severity": sum(1 for alert in alerts if alert["severity"] == "High"),
            "blocked_attacks": sum(1 for alert in alerts if alert["status"] == "Resolved"),
            "avg_response_time": 0,
        }
    }


@app.get("/api/reports/attack-types")
def get_attack_types(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    alerts = get_dynamic_alerts(host, step)
    counts: Dict[str, int] = {}
    for alert in alerts:
        counts[alert["type"]] = counts.get(alert["type"], 0) + 1
    total = max(len(alerts), 1)
    return {"attack_types": [{"type": label, "value": round(count / total * 100, 2), "count": count} for label, count in counts.items()]}


@app.get("/api/reports/attacks-over-time")
def get_attacks_over_time(host: str | None = None, step: int | None = None) -> Dict[str, Any]:
    alerts = get_dynamic_alerts(host, step)
    counts: Dict[str, int] = {}
    for alert in alerts:
        period = str(alert["time"])[:13]
        counts[period] = counts.get(period, 0) + 1
    return {"attacks_over_time": [{"period": period, "count": count} for period, count in sorted(counts.items())]}



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
        "data_source_note": "This project uses prepared NF-UNSW-NB15-v3 feature windows under data/processed.",
    }


@app.get("/api/reproducibility")
def get_reproducibility() -> Dict[str, Any]:
    return {
        "data_source": "NF-UNSW-NB15-v3 processed windows",
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


@app.get("/api/missions/j/models")
def mission_j_models() -> Dict[str, Any]:
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
    host = os.environ.get("CROSSTHREAT_HOST", DEFAULT_HOST)
    port_value = os.environ.get("CROSSTHREAT_PORT", str(DEFAULT_PORT))
    try:
        port = int(port_value)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid CROSSTHREAT_PORT value {port_value!r}; expected an integer between 1 and 65535."
        ) from exc
    if not 1 <= port <= 65535:
        raise SystemExit(
            f"Invalid CROSSTHREAT_PORT value {port}; expected an integer between 1 and 65535."
        )

    print("\n=== CrossThreat backend architecture summary ===")
    print("Active server: server.py")
    print("FastAPI applications: 1")
    print("Legacy server active: NO")
    print(f"Canonical feature count: {CANONICAL_FEATURE_COUNT}")
    print(f"Scaler feature count: {int(getattr(SCALER, 'n_features_in_', len(FEATURE_COLS)))}")
    print(f"Model feature count: {int(MODEL_DIMS.get('input_dim', len(FEATURE_COLS)))}")
    print("Registered API routes: /api/health, /api/generalization, /api/replay/list, /api/replay/host/{host_ip}, /api/models/comparison, /api/evaluation/confusion-matrix, /api/evaluation/per-class, /api/verification/ground-truth, /api/features/importance, /api/missions/summary, /api/missions/{id}/details, /api/ood/results")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((host, port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE or getattr(exc, "winerror", None) == 10048:
            raise SystemExit(
                f"CrossThreat cannot start because {host}:{port} is already in use. "
                f"Stop the existing server or choose another port, for example: "
                f'$env:CROSSTHREAT_PORT = "8001"; python server.py'
            ) from exc
        raise
    finally:
        server_socket.close()

    print(f"Server address: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)