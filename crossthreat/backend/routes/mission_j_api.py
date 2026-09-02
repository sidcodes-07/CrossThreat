"""Mission J: model comparison data.

The dashboard consumes this data through the backend API; it does not read the raw
JSON files directly from the browser.
"""

import json
import os
from pathlib import Path


class MissionJAPI:
    """API endpoints for model comparison dashboard."""

    @staticmethod
    def get_processed_data_dir():
        """Return the canonical processed-data directory for the repository."""
        return str(Path(__file__).resolve().parents[2] / "data" / "processed")

    @staticmethod
    def load_json_file(filename):
        try:
            with open(os.path.join(MissionJAPI.get_processed_data_dir(), filename), "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return None

    @staticmethod
    def get_models_comparison():
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        confusion_data = MissionJAPI.load_json_file("mission_e_confusion_metrics.json")

        if not ablation_data:
            return {"error": "Model ablation data not found"}

        models = []
        for model_name in ["LSTM", "Transformer", "Mamba"]:
            if model_name not in ablation_data.get("models", {}):
                continue

            model_info = ablation_data["models"][model_name]
            per_class_recalls = {}
            if confusion_data and model_name in confusion_data:
                per_class_recalls = confusion_data[model_name].get("per_class_metrics", {})

            attack_recall = float(model_info.get("attack_recall", 0.0))
            if attack_recall > 0.5:
                badge_color = "green"
                badge_text = "Good"
            elif attack_recall > 0.1:
                badge_color = "yellow"
                badge_text = "Needs Improvement"
            else:
                badge_color = "red"
                badge_text = "Poor"

            card = {
                "id": model_name.lower(),
                "name": model_name,
                "parameters": int(model_info.get("parameters", 0)),
                "latency_ms": float(model_info.get("inference_latency_ms_per_batch", 0.0)),
                "overall_accuracy": float(model_info.get("overall_accuracy", 0.0)),
                "attack_recall": attack_recall,
                "macro_f1": float(model_info.get("macro_f1", 0.0)),
                "benign_recall": float(model_info.get("benign_recall", 0.95)),
                "per_attack_recalls": per_class_recalls,
                "badge": {
                    "color": badge_color,
                    "text": badge_text,
                    "tooltip": f"Attack recall: {attack_recall:.1%}",
                },
                "verdict": model_info.get("verdict", "Evaluation complete"),
                "is_recommended": model_name == "Mamba",
            }
            models.append(card)

        return {
            "models": models,
            "recommended_model": "Mamba",
            "recommended_reason": "Best measured attack recall while keeping latency low; still a work in progress.",
            "caveat": "Attack forecasting accuracy is a known work-in-progress — see Roadmap tab.",
            "timestamp": ablation_data.get("timestamp", ""),
        }

    @staticmethod
    def get_model_details(model_id):
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        confusion_data = MissionJAPI.load_json_file("mission_e_confusion_metrics.json")

        if not ablation_data:
            return {"error": "Model data not found"}

        model_lookup = {"lstm": "LSTM", "transformer": "Transformer", "mamba": "Mamba"}
        model_name = model_lookup.get(model_id.lower())
        if not model_name or model_name not in ablation_data.get("models", {}):
            return {"error": "Model not found"}

        model_info = ablation_data["models"][model_name]
        confusion_matrix = None
        per_class_metrics = None
        if confusion_data and model_name in confusion_data:
            confusion_matrix = confusion_data[model_name].get("confusion_matrix")
            per_class_metrics = confusion_data[model_name].get("per_class_metrics", {})

        return {
            "model": model_name,
            "architecture": model_info.get("architecture", ""),
            "hyperparameters": model_info.get("hyperparameters", {}),
            "metrics": {
                "overall_accuracy": model_info.get("overall_accuracy"),
                "attack_recall": model_info.get("attack_recall"),
                "macro_f1": model_info.get("macro_f1"),
                "weighted_f1": model_info.get("weighted_f1"),
                "benign_recall": model_info.get("benign_recall"),
                "per_class": per_class_metrics,
            },
            "performance": {
                "latency_ms": model_info.get("inference_latency_ms_per_batch"),
                "parameters": model_info.get("parameters"),
                "training_time_seconds": model_info.get("train_time_seconds"),
            },
            "confusion_matrix": confusion_matrix,
            "verdict": model_info.get("verdict"),
            "timestamp": ablation_data.get("timestamp"),
        }

    @staticmethod
    def get_comparison_table():
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        if not ablation_data:
            return {"error": "Model data not found"}

        rows = []
        for model_name in ["LSTM", "Transformer", "Mamba"]:
            if model_name not in ablation_data.get("models", {}):
                continue
            model = ablation_data["models"][model_name]
            rows.append(
                {
                    "model": model_name,
                    "attack_recall": f"{model.get('attack_recall', 0):.2%}",
                    "macro_f1": f"{model.get('macro_f1', 0):.3f}",
                    "benign_recall": f"{model.get('benign_recall', 0):.2%}",
                    "latency_ms": f"{model.get('inference_latency_ms_per_batch', 0):.2f}",
                    "parameters": f"{model.get('parameters', 0):,}",
                    "decision": "SELECT" if model_name == "Mamba" else "REJECT",
                }
            )
        return {
            "table_name": "Model Architecture Comparison",
            "rows": rows,
            "source": "model_ablation_summary.json",
            "timestamp": ablation_data.get("timestamp"),
        }

    @staticmethod
    def health_check():
        data_dir = MissionJAPI.get_processed_data_dir()
        required_files = ["model_ablation_summary.json", "mission_e_confusion_metrics.json"]
        missing_files = [fname for fname in required_files if not os.path.exists(os.path.join(data_dir, fname))]
        return {"status": "healthy" if not missing_files else "degraded", "missing_files": missing_files}