import json
import os
import pickle
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, precision_recall_fscore_support
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


class LSTMSequenceModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_classes: int, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_dim, hidden_size=hidden_dim, num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out)


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


class TransformerSequenceModel(nn.Module):
    def __init__(self, input_dim: int, d_model: int, num_classes: int, num_heads: int = 4, num_layers: int = 2):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        self.positional = nn.Parameter(torch.zeros(1, SEQ_LEN, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=d_model * 4,
            dropout=0.1,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output = nn.Linear(d_model, num_classes)

    def forward(self, x):
        x = self.input_proj(x)
        x = x + self.positional
        x = self.encoder(x)
        x = x[:, -1, :]
        return self.output(x)


def build_data_loaders(processed_dir: str, batch_size: int = 32):
    train_df = pd.read_pickle(os.path.join(processed_dir, "train_windows.pkl"))
    test_df = pd.read_pickle(os.path.join(processed_dir, "test_windows.pkl"))
    with open(os.path.join(processed_dir, "metadata.pkl"), "rb") as f:
        metadata = pickle.load(f)

    feature_cols = metadata["feature_cols"]
    label_map = metadata["label_mapping"]
    label_names = {v: k for k, v in label_map.items()}

    train_dataset = HostSequenceDataset(train_df, feature_cols, label_map, seq_len=SEQ_LEN)
    test_dataset = HostSequenceDataset(test_df, feature_cols, label_map, seq_len=SEQ_LEN)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    print(f"[INFO] Train sequences: {len(train_dataset)}")
    print(f"[INFO] Test sequences: {len(test_dataset)}")
    print(f"[INFO] Train attack classes: {sorted(train_df['Label'].unique())}")
    print(f"[INFO] Test attack classes: {sorted(test_df['Label'].unique())}")
    print(f"[INFO] Note: Test set contains unseen attack types (generalization challenge)")
    
    return train_loader, test_loader, feature_cols, label_map, label_names


def train_one_epoch(model, loader, criterion, optimizer):
    model.train()
    total_loss = 0.0
    total_samples = 0

    for batch_x, batch_y in loader:
        batch_x = batch_x.to(DEVICE)
        batch_y = batch_y.to(DEVICE)

        optimizer.zero_grad()
        logits = model(batch_x)
        loss = criterion(logits, batch_y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch_x.size(0)
        total_samples += batch_x.size(0)

    return total_loss / max(total_samples, 1)


@torch.no_grad()
def evaluate_model(model, loader, label_names):
    model.eval()
    all_true = []
    all_pred = []

    for batch_x, batch_y in loader:
        batch_x = batch_x.to(DEVICE)
        logits = model(batch_x)
        preds = logits.argmax(dim=1).detach().cpu().numpy()
        all_pred.extend(preds.tolist())
        all_true.extend(batch_y.numpy().tolist())

    y_true = np.asarray(all_true, dtype=int)
    y_pred = np.asarray(all_pred, dtype=int)
    classes = sorted(label_names.keys())

    per_class_f1 = f1_score(y_true, y_pred, labels=classes, average=None)
    class_f1 = {label_names[c]: float(f1) for c, f1 in zip(classes, per_class_f1)}

    attack_mask = y_true != 0
    attack_recall = float(((y_true != 0) & (y_pred != 0)).sum() / max((y_true != 0).sum(), 1))
    return {
        "y_true": y_true,
        "y_pred": y_pred,
        "f1_by_class": class_f1,
        "attack_recall": attack_recall,
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
    }


def count_parameters(model):
    return sum(p.numel() for p in model.parameters())


def measure_latency(model, loader, n_warmup: int = 20, n_runs: int = 100):
    model.eval()
    sample = next(iter(loader))
    x = sample[0].to(DEVICE)

    for _ in range(n_warmup):
        with torch.no_grad():
            _ = model(x)

    times = []
    for _ in range(n_runs):
        with torch.no_grad():
            start = time.perf_counter()
            _ = model(x)
            times.append(time.perf_counter() - start)

    return float(np.mean(times) * 1000.0 / x.size(0))


def train_model(model_name: str, model_class, input_dim: int, num_classes: int, train_loader, test_loader, label_names):
    if model_name == "lstm":
        model = LSTMSequenceModel(input_dim=input_dim, hidden_dim=64, num_classes=num_classes).to(DEVICE)
    elif model_name == "mamba":
        model = MambaSequenceModel(input_dim=input_dim, hidden_dim=64, num_classes=num_classes).to(DEVICE)
    else:
        model = TransformerSequenceModel(input_dim=input_dim, d_model=64, num_classes=num_classes, num_heads=4, num_layers=2).to(DEVICE)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    start_train = time.perf_counter()
    for epoch in range(8):
        loss = train_one_epoch(model, train_loader, criterion, optimizer)
    train_time = time.perf_counter() - start_train

    metrics = evaluate_model(model, test_loader, label_names)
    latency_ms = measure_latency(model, test_loader)

    summary = {
        "model": model_name,
        "train_time_seconds": round(train_time, 3),
        "inference_latency_ms_per_batch": round(latency_ms, 4),
        "parameters": count_parameters(model),
        "macro_f1": metrics["macro_f1"],
        "weighted_f1": metrics["weighted_f1"],
        "attack_recall": metrics["attack_recall"],
        "f1_by_class": metrics["f1_by_class"],
    }
    return model, summary


def run_ablation(processed_dir: str = None):
    if processed_dir is None:
        processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    train_loader, test_loader, feature_cols, label_map, label_names = build_data_loaders(processed_dir)
    num_classes = len(label_map)

    exclusion_note = (
        "CNN/ViT/Swin were excluded because they are designed for 2D spatial image data and do not have a natural fit "
        "for tabular flow sequences; forcing flow windows into image-like grids would be an unjustifiable stretch."
    )

    results = []
    for model_name in ["lstm", "mamba", "transformer"]:
        _, result = train_model(model_name, None, len(feature_cols), num_classes, train_loader, test_loader, label_names)
        results.append(result)

    summary = {
        "dataset": "CSE-CIC-IDS2018",
        "split": "Time-based: Train days 1-7, Test days 8-10 (different attack scenarios per day)",
        "sequence_length": SEQ_LEN,
        "note": "Test set contains unseen attack types from training — this tests model generalization to new threats",
        "exclude_note": exclusion_note,
        "models": results,
    }

    output_path = os.path.join(processed_dir, "model_ablation_summary.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*80)
    print("MISSION D: TEMPORAL MODEL ABLATION SUMMARY")
    print("="*80)
    print(json.dumps(summary, indent=2))
    
    # Generate comparison table
    print("\n" + "="*80)
    print("COMPARISON TABLE")
    print("="*80)
    print(f"{'Model':<15} {'Train Time (s)':<15} {'Latency (ms)':<15} {'Params':<10} {'Macro F1':<12} {'Attack Recall':<15}")
    print("-"*80)
    for m in results:
        print(f"{m['model']:<15} {m['train_time_seconds']:<15.3f} {m['inference_latency_ms_per_batch']:<15.4f} {m['parameters']:<10} {m['macro_f1']:<12.4f} {m['attack_recall']:<15.4f}")
    
    return summary


if __name__ == "__main__":
    run_ablation()
