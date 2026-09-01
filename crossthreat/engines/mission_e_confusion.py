import json
import os
import pickle
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
)
from torch.utils.data import DataLoader, Dataset

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEQ_LEN = 5


class HostSequenceDataset(Dataset):
    def __init__(self, df: pd.DataFrame, feature_cols: List[str], label_map: Dict[str, int], seq_len: int = SEQ_LEN):
        self.sequences = []
        self.targets = []

        for host, group in df.groupby("Host"):
            group = group.sort_values("TimeWindow")
            features = group[feature_cols].values.astype(np.float32)
            labels = group["Label"].map(label_map).fillna(0).values.astype(np.int64)

            if len(features) >= seq_len + 1:
                for i in range(len(features) - seq_len):
                    self.sequences.append(features[i : i + seq_len])
                    self.targets.append(labels[i + seq_len])

        if len(self.sequences) > 0:
            self.sequences = np.array(self.sequences, dtype=np.float32)
            self.targets = np.array(self.targets, dtype=np.int64)
        else:
            self.sequences = np.empty((0, seq_len, len(feature_cols)), dtype=np.float32)
            self.targets = np.empty((0,), dtype=np.int64)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.sequences[idx], dtype=torch.float32),
            torch.tensor(self.targets[idx], dtype=torch.long),
        )


class MambaStateSpaceBlock(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.norm = nn.LayerNorm(d_model)
        self.input_proj = nn.Linear(d_model, d_model * 2)
        self.output_proj = nn.Linear(d_model, d_model)
        self.conv = nn.Conv1d(d_model, d_model, kernel_size=3, padding=1, groups=d_model)
        self.activation = nn.GELU()

    def forward(self, x):
        residual = x
        x = self.norm(x)
        x_gate = self.input_proj(x)
        x, gate = x_gate.chunk(2, dim=-1)

        x = x.transpose(1, 2)
        x = self.conv(x)
        x = x.transpose(1, 2)
        x = self.activation(x)

        state = torch.zeros(x.size(0), x.size(1), x.size(2), device=x.device, dtype=x.dtype)
        state[:, 0, :] = x[:, 0, :]
        for t in range(1, x.size(1)):
            state[:, t, :] = 0.7 * state[:, t - 1, :] + 0.3 * x[:, t, :]

        out = state * torch.sigmoid(gate)
        out = self.output_proj(out)
        return residual + out


class MambaSequenceModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_classes: int):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.block = MambaStateSpaceBlock(hidden_dim)
        self.output = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        x = self.input_proj(x)
        x = self.block(x)
        x = x[:, -1, :]
        return self.output(x)


def load_baseline_model(processed_dir: str):
    model_path = os.path.join(processed_dir, "baseline_model.pkl")
    with open(model_path, "rb") as f:
        return pickle.load(f)


def train_and_save_mamba(train_df, test_df, feature_cols, label_map, processed_dir):
    """Train Mamba model and save it alongside baseline predictions."""
    print("[TEMPORAL] Training Mamba state-space model...")
    
    train_dataset = HostSequenceDataset(train_df, feature_cols, label_map, seq_len=SEQ_LEN)
    test_dataset = HostSequenceDataset(test_df, feature_cols, label_map, seq_len=SEQ_LEN)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    
    model = MambaSequenceModel(input_dim=len(feature_cols), hidden_dim=64, num_classes=len(label_map)).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    for epoch in range(8):
        model.train()
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
            optimizer.zero_grad()
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
    
    # Save model
    model_path = os.path.join(processed_dir, "mamba_model_for_confusion.pth")
    torch.save(model.state_dict(), model_path)
    print(f"[INFO] Mamba model saved to {model_path}")
    
    return model, test_loader


@torch.no_grad()
def predict_mamba(model, loader):
    all_pred = []
    all_true = []
    for batch_x, batch_y in loader:
        batch_x = batch_x.to(DEVICE)
        logits = model(batch_x)
        preds = logits.argmax(dim=1).detach().cpu().numpy()
        all_pred.extend(preds.tolist())
        all_true.extend(batch_y.numpy().tolist())
    return np.array(all_pred), np.array(all_true)


def predict_baseline(model, X_test):
    return model.predict(X_test)


def generate_confusion_matrix_and_metrics(y_true, y_pred, label_names, model_name: str):
    unique_labels = sorted(label_names.keys())
    cm = confusion_matrix(y_true, y_pred, labels=unique_labels)

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=unique_labels, zero_division=0
    )

    per_class_metrics = []
    low_recall_flags = []

    for i, label_idx in enumerate(unique_labels):
        label_name = label_names[label_idx]
        recall_val = recall[i]
        flag = "[ALERT] RECALL < 50%" if recall_val < 0.5 else "[OK]"

        per_class_metrics.append(
            {
                "class_name": label_name,
                "support": int(support[i]),
                "precision": float(precision[i]),
                "recall": float(recall_val),
                "f1": float(f1[i]),
                "sanity_check": flag,
            }
        )

        if recall_val < 0.5 and support[i] > 0:
            low_recall_flags.append(
                {
                    "class": label_name,
                    "recall": float(recall_val),
                    "support": int(support[i]),
                    "reason": "Low recall indicates poor detection rate for this class; may require feature engineering, class balancing, or retraining",
                }
            )

    return cm, per_class_metrics, low_recall_flags


def render_heatmap(cm, label_names, model_name: str, processed_dir: str):
    unique_labels = sorted(label_names.keys())
    class_names = [label_names[i] for i in unique_labels]

    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        cbar_kws={"label": "Count"},
        ax=ax,
    )
    ax.set_title(f"Confusion Matrix: {model_name} Model on CSE-CIC-IDS2018 Test Set", fontsize=14, fontweight="bold")
    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_ylabel("True Label", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()

    output_path = os.path.join(processed_dir, f"confusion_matrix_{model_name}.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"[INFO] Heatmap saved: {output_path}")
    plt.close()

    return output_path


def mission_e(processed_dir: str = None):
    if processed_dir is None:
        processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    print("="*80)
    print("MISSION E: CONFUSION MATRIX & PER-CLASS VERIFICATION")
    print("="*80)

    # Load data
    train_df = pd.read_pickle(os.path.join(processed_dir, "train_windows.pkl"))
    test_df = pd.read_pickle(os.path.join(processed_dir, "test_windows.pkl"))

    with open(os.path.join(processed_dir, "metadata.pkl"), "rb") as f:
        metadata = pickle.load(f)

    with open(os.path.join(processed_dir, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)

    feature_cols = metadata["feature_cols"]
    label_map = metadata["label_mapping"]
    label_names = {v: k for k, v in label_map.items()}

    X_test = test_df[feature_cols].values
    X_test_scaled = scaler.transform(X_test)
    y_test = test_df["Label"].map(label_map).fillna(0).values.astype(int)

    # Baseline (Random Forest)
    print("\n[BASELINE] Evaluating Random Forest classifier...")
    baseline_clf = load_baseline_model(processed_dir)
    y_pred_baseline = predict_baseline(baseline_clf, X_test_scaled)

    cm_baseline, metrics_baseline, flags_baseline = generate_confusion_matrix_and_metrics(
        y_test, y_pred_baseline, label_names, "Random Forest Baseline"
    )
    render_heatmap(cm_baseline, label_names, "baseline_random_forest", processed_dir)

    # Mamba (Temporal) - Train fresh model
    mamba_model, test_loader = train_and_save_mamba(train_df, test_df, feature_cols, label_map, processed_dir)
    y_pred_mamba, y_true_mamba = predict_mamba(mamba_model, test_loader)

    cm_mamba, metrics_mamba, flags_mamba = generate_confusion_matrix_and_metrics(
        y_true_mamba, y_pred_mamba, label_names, "Mamba Temporal"
    )
    render_heatmap(cm_mamba, label_names, "temporal_mamba", processed_dir)

    # Consolidate results
    results = {
        "dataset": "CSE-CIC-IDS2018",
        "test_set_note": "Days 8-10 (unseen attack types from training)",
        "baseline_model": {
            "type": "Random Forest",
            "samples_evaluated": int(len(y_test)),
            "per_class_metrics": metrics_baseline,
            "low_recall_flags": flags_baseline,
            "confusion_matrix_path": "confusion_matrix_baseline_random_forest.png",
        },
        "temporal_model": {
            "type": "Mamba State-Space",
            "samples_evaluated": int(len(y_true_mamba)),
            "per_class_metrics": metrics_mamba,
            "low_recall_flags": flags_mamba,
            "confusion_matrix_path": "confusion_matrix_temporal_mamba.png",
        },
    }

    output_path = os.path.join(processed_dir, "mission_e_confusion_metrics.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print("BASELINE (RANDOM FOREST) - PER-CLASS METRICS")
    print("="*80)
    print(f"{'Class':<20} {'Support':<10} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Status':<20}")
    print("-"*86)
    for m in metrics_baseline:
        print(f"{m['class_name']:<20} {m['support']:<10} {m['precision']:<12.4f} {m['recall']:<12.4f} {m['f1']:<12.4f} {m['sanity_check']:<20}")

    if flags_baseline:
        print("\n[ALERT] FLAGGED CLASSES (Recall < 50%):")
        for flag in flags_baseline:
            print(f"  - {flag['class']}: recall={flag['recall']:.4f}, support={flag['support']}")

    print("\n" + "="*80)
    print("TEMPORAL MAMBA - PER-CLASS METRICS")
    print("="*80)
    print(f"{'Class':<20} {'Support':<10} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Status':<20}")
    print("-"*86)
    for m in metrics_mamba:
        print(f"{m['class_name']:<20} {m['support']:<10} {m['precision']:<12.4f} {m['recall']:<12.4f} {m['f1']:<12.4f} {m['sanity_check']:<20}")

    if flags_mamba:
        print("\n[ALERT] FLAGGED CLASSES (Recall < 50%):")
        for flag in flags_mamba:
            print(f"  - {flag['class']}: recall={flag['recall']:.4f}, support={flag['support']}")

    print(f"\n[INFO] Full results saved to: {output_path}")
    print(f"[INFO] Heatmaps saved to: confusion_matrix_baseline_random_forest.png, confusion_matrix_temporal_mamba.png")
    return results


if __name__ == "__main__":
    mission_e()
