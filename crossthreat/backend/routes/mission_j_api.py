"""
MISSION J: Multi-Model Confidence Comparison Panel
==================================================

Backend API endpoints for model comparison dashboard.
"""

import os
import json


class MissionJAPI:
    """API endpoints for model comparison dashboard."""
    
    @staticmethod
    def get_processed_data_dir():
        """Get processed data directory."""
        return os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    
    @staticmethod
    def load_json_file(filename):
        """Load JSON file safely."""
        try:
            data_dir = MissionJAPI.get_processed_data_dir()
            with open(os.path.join(data_dir, filename)) as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    @staticmethod
    def get_models_comparison():
        """
        Returns model comparison data for dashboard cards.
        """
        
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        confusion_data = MissionJAPI.load_json_file("mission_e_confusion_metrics.json")
        
        if not ablation_data:
            return {"error": "Model ablation data not found"}
        
        models = []
        
        for model_name in ['LSTM', 'Transformer', 'Mamba']:
            if model_name not in ablation_data.get('models', {}):
                continue
            
            model_info = ablation_data['models'][model_name]
            
            # Get per-attack recall from confusion matrix
            per_class_recalls = {}
            if confusion_data and model_name in confusion_data:
                per_class_recalls = confusion_data[model_name].get('per_class_metrics', {})
            
            # Determine badge color based on attack recall
            attack_recall = model_info.get('attack_recall', 0.0)
            if attack_recall > 0.5:
                badge_color = "green"
                badge_text = "Good"
            elif attack_recall > 0.1:
                badge_color = "yellow"
                badge_text = "Needs Improvement"
            else:
                badge_color = "red"
                badge_text = "Poor"
            
            # Build model card
            card = {
                "id": model_name.lower(),
                "name": model_name,
                "parameters": model_info.get('parameters', 0),
                "latency_ms": model_info.get('latency_ms', 0),
                "overall_accuracy": model_info.get('overall_accuracy', 0),
                "attack_recall": attack_recall,
                "macro_f1": model_info.get('macro_f1', 0),
                "benign_recall": model_info.get('benign_recall', 0.95),
                "per_attack_recalls": per_class_recalls,
                "badge": {
                    "color": badge_color,
                    "text": badge_text,
                    "tooltip": f"Attack recall: {attack_recall:.1%}"
                },
                "verdict": model_info.get('verdict', 'Evaluation complete'),
                "is_recommended": model_name == 'Mamba'
            }
            
            models.append(card)
        
        return {
            "models": models,
            "recommended_model": "Mamba",
            "recommended_reason": "Best measured attack recall (17.7%) and lowest latency. Supports domain adaptation.",
            "caveat": "Attack forecasting accuracy is a known work-in-progress — see Roadmap tab.",
            "timestamp": ablation_data.get('timestamp', '')
        }
    
    @staticmethod
    def get_model_details(model_id):
        """
        Returns detailed metrics for a specific model.
        """
        
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        confusion_data = MissionJAPI.load_json_file("mission_e_confusion_metrics.json")
        
        if not ablation_data:
            return {"error": "Model data not found"}
        
        # Map ID to proper model name
        model_name_map = {'lstm': 'LSTM', 'transformer': 'Transformer', 'mamba': 'Mamba'}
        model_name = model_name_map.get(model_id.lower())
        
        if not model_name or model_name not in ablation_data.get('models', {}):
            return {"error": "Model not found"}
        
        model_info = ablation_data['models'][model_name]
        
        # Get confusion matrix if available
        confusion_matrix = None
        per_class_metrics = None
        
        if confusion_data and model_name in confusion_data:
            confusion_matrix = confusion_data[model_name].get('confusion_matrix')
            per_class_metrics = confusion_data[model_name].get('per_class_metrics', {})
        
        return {
            "model": model_name,
            "architecture": model_info.get('architecture', ''),
            "hyperparameters": model_info.get('hyperparameters', {}),
            "metrics": {
                "overall_accuracy": model_info.get('overall_accuracy'),
                "attack_recall": model_info.get('attack_recall'),
                "macro_f1": model_info.get('macro_f1'),
                "weighted_f1": model_info.get('weighted_f1'),
                "benign_recall": model_info.get('benign_recall'),
                "per_class": per_class_metrics
            },
            "performance": {
                "latency_ms": model_info.get('latency_ms'),
                "parameters": model_info.get('parameters'),
                "training_time_hours": model_info.get('training_time_hours')
            },
            "confusion_matrix": confusion_matrix,
            "verdict": model_info.get('verdict'),
            "timestamp": ablation_data.get('timestamp')
        }
    
    @staticmethod
    def get_comparison_table():
        """
        Returns formatted comparison table for all models.
        """
        
        ablation_data = MissionJAPI.load_json_file("model_ablation_summary.json")
        
        if not ablation_data:
            return {"error": "Model data not found"}
        
        rows = []
        
        for model_name in ['LSTM', 'Transformer', 'Mamba']:
            if model_name not in ablation_data.get('models', {}):
                continue
            
            model = ablation_data['models'][model_name]
            
            rows.append({
                "model": model_name,
                "attack_recall": f"{model.get('attack_recall', 0):.2%}",
                "macro_f1": f"{model.get('macro_f1', 0):.3f}",
                "benign_recall": f"{model.get('benign_recall', 0):.2%}",
                "latency_ms": f"{model.get('latency_ms', 0):.2f}",
                "parameters": f"{model.get('parameters', 0):,}",
                "decision": "SELECT" if model_name == 'Mamba' else "REJECT"
            })
        
        return {
            "table_name": "Model Architecture Comparison",
            "rows": rows,
            "source": "model_ablation_summary.json",
            "timestamp": ablation_data.get('timestamp')
        }
    
    @staticmethod
    def health_check():
        """Health check endpoint."""
        
        # Verify required data files exist
        data_dir = MissionJAPI.get_processed_data_dir()
        required_files = [
            "model_ablation_summary.json",
            "mission_e_confusion_metrics.json"
        ]
        
        status = "healthy"
        missing_files = []
        
        for fname in required_files:
            fpath = os.path.join(data_dir, fname)
            if not os.path.exists(fpath):
                status = "degraded"
                missing_files.append(fname)
        
        return {
            "status": status,
            "endpoint": "/api/missions/j",
            "missing_files": missing_files,
            "available_routes": [
                "GET /models - List all model comparison cards",
                "GET /model/<id>/details - Get detailed metrics for a model",
                "GET /comparison/table - Get comparison table",
                "GET /health - Health check"
            ]
        }
