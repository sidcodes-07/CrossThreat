"""Mission K: progress summary API helper."""

import json
import os
from pathlib import Path


class MissionKAPI:
    @staticmethod
    def get_processed_data_dir():
        return str(Path(__file__).resolve().parents[2] / "data" / "processed")

    @staticmethod
    def load_json_file(filename):
        try:
            with open(os.path.join(MissionKAPI.get_processed_data_dir(), filename), "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return None

    @staticmethod
    def get_missions_summary():
        return {
            "timestamp": "2026-09-01T00:00:00Z",
            "total_missions": 6,
            "completed": 6,
            "missions": [
                {
                    "id": "d",
                    "name": "Model Architecture Comparison",
                    "status": "Complete",
                    "key_finding": "Mamba achieved the best measured attack recall of 17.7%, while LSTM and Transformer remained near 2%.",
                    "order": 1,
                },
                {
                    "id": "e",
                    "name": "Confusion Matrix Analysis",
                    "status": "Complete",
                    "key_finding": "The full confusion matrix confirms most attack classes remain weakly detected and are easy to miss.",
                    "order": 2,
                },
                {
                    "id": "f",
                    "name": "OSI-Layer Attack Mapping",
                    "status": "Complete",
                    "key_finding": "Attack classes were mapped to their primary OSI layer and mitigation control families.",
                    "order": 3,
                },
                {
                    "id": "g",
                    "name": "Feature Dependency Analysis",
                    "status": "Complete",
                    "key_finding": "Flow-rate and packet-volume features dominate signal; a reduced feature set was checked for degradation.",
                    "order": 4,
                },
                {
                    "id": "h",
                    "name": "Ground-Truth Verification",
                    "status": "Complete",
                    "key_finding": "Verification log confirms predictions align with documented attack windows and timing constraints.",
                    "order": 5,
                },
                {
                    "id": "i",
                    "name": "Dataset Landscape Justification",
                    "status": "Complete",
                    "key_finding": "CIC-IDS2018 is chosen because day-by-day attack scheduling supports genuine temporal forecasting.",
                    "order": 6,
                },
            ],
        }