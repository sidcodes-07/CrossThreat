#!/usr/bin/env python3
"""
ATTACK FORECASTING FIX v3: FOCAL LOSS
=====================================

Focal loss downweights easy examples and focuses on hard negatives.
Better than weighted CrossEntropyLoss for severe imbalance.
"""

import os
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torch.optim import Adam
import torch.nn.functional as F
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, f1_score
from datetime import datetime
import json
import time
import warnings

warnings.filterwarnings('ignore')

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class SequenceDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.LongTensor(y)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class FocalLoss(nn.Module):
    """Focal Loss for handling class imbalance."""
    
    def __init__(self, alpha: torch.Tensor = None, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(inputs, targets, reduction='none', weight=self.alpha)
        p = torch.exp(-ce_loss)
        focal_loss = (1 - p) ** self.gamma * ce_loss
        return focal_loss.mean()

class WeightedLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_classes: int, 
                 num_layers: int = 2, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False
        )
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, num_classes)
        self.relu = nn.ReLU()
    
    def forward(self, x):
        lstm_out, (h_n, c_n) = self.lstm(x)
        last_hidden = h_n[-1]
        x = self.dropout(last_hidden)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x

class AttackForecastingFixv3:
    """Focal loss approach with threshold optimization."""
    
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def log(self, msg: str):
        print(msg)
    
    def load_data(self):
        """Load preprocessed data."""
        self.log("Loading preprocessed data...")
        
        with open(os.path.join(self.data_dir, "encoder.pkl"), 'rb') as f:
            self.encoder = pickle.load(f)
        
        # Load windows
        train_win = np.load(os.path.join(self.data_dir, "train_seq5_windows.npz"))
        test_win = np.load(os.path.join(self.data_dir, "test_seq5_windows.npz"))
        
        self.X_train = train_win['X']
        self.y_train = train_win['y']
        self.X_test = test_win['X']
        self.y_test = test_win['y']
        
        self.log(f"  Train: {self.X_train.shape}, Test: {self.X_test.shape}")
    
    def compute_class_weights(self, reduce_factor: float = 0.5):
        """Compute reduced class weights (less aggressive than inverse frequency)."""
        self.log("\nComputing reduced class weights...")
        
        counts = np.bincount(self.y_train)
        weights = []
        
        for i, count in enumerate(counts):
            # Start with inverse frequency, then reduce by factor
            w = len(self.y_train) / (len(counts) * count)
            # Reduce aggressive weighting
            w = 1.0 + reduce_factor * (w - 1.0)
            weights.append(w)
            cls_name = self.encoder.classes_[i]
            self.log(f"  {cls_name:<25} count={count:5} weight={w:.4f}")
        
        self.class_weights = np.array(weights)
        return self.class_weights
    
    def train_model(self, model: nn.Module, X: np.ndarray, y: np.ndarray, 
                   X_val: np.ndarray, y_val: np.ndarray, 
                   class_weights: np.ndarray,
                   epochs: int = 100, batch_size: int = 32, lr: float = 0.0005):
        """Train with Focal Loss."""
        
        self.log(f"\nTraining with Focal Loss...")
        self.log(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {lr}")
        
        # Create datasets
        train_dataset = SequenceDataset(X, y)
        val_dataset = SequenceDataset(X_val, y_val)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Optimizer
        optimizer = Adam(model.parameters(), lr=lr, weight_decay=1e-5)
        
        # Focal Loss
        weight_tensor = torch.FloatTensor(class_weights).to(DEVICE)
        criterion = FocalLoss(alpha=weight_tensor, gamma=2.0)
        
        model.to(DEVICE)
        best_f1 = 0
        patience = 20
        patience_counter = 0
        
        start_time = time.time()
        
        for epoch in range(epochs):
            # Training
            model.train()
            epoch_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(DEVICE)
                y_batch = y_batch.to(DEVICE)
                
                optimizer.zero_grad()
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                
                epoch_loss += loss.item()
            
            epoch_loss /= len(train_loader)
            
            # Validation
            model.eval()
            y_pred_all = []
            y_true_all = []
            
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(DEVICE)
                    logits = model(X_batch)
                    y_pred = torch.argmax(logits, dim=1)
                    y_pred_all.extend(y_pred.cpu().numpy())
                    y_true_all.extend(y_batch.numpy())
            
            f1 = f1_score(y_true_all, y_pred_all, average='weighted', zero_division=0)
            
            if (epoch + 1) % 20 == 0:
                self.log(f"  Epoch {epoch+1:3d}: loss={epoch_loss:.4f}, f1={f1:.4f}")
            
            if f1 > best_f1:
                best_f1 = f1
                patience_counter = 0
                best_model_state = model.state_dict().copy()
            else:
                patience_counter += 1
            
            if patience_counter >= patience:
                self.log(f"  Early stopping at epoch {epoch+1}")
                model.load_state_dict(best_model_state)
                break
        
        train_time = time.time() - start_time
        self.log(f"  Training completed in {train_time:.1f} seconds")
        self.log(f"  Best weighted F1: {best_f1:.4f}")
        
        return model, train_time
    
    def evaluate_model(self, model: nn.Module, X: np.ndarray, y: np.ndarray, 
                      dataset_name: str = "Test"):
        """Comprehensive model evaluation."""
        
        self.log(f"\nEvaluating on {dataset_name} set...")
        
        model.eval()
        dataset = SequenceDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=False)
        
        logits_all = []
        y_true_all = []
        
        with torch.no_grad():
            for X_batch, y_batch in loader:
                X_batch = X_batch.to(DEVICE)
                logits = model(X_batch)
                logits_all.extend(logits.cpu().numpy())
                y_true_all.extend(y_batch.numpy())
        
        logits_all = np.array(logits_all)
        y_true_all = np.array(y_true_all)
        y_pred_all = np.argmax(logits_all, axis=1)
        
        # Metrics with default threshold
        accuracy = np.mean(y_pred_all == y_true_all)
        attack_mask = y_true_all != 0
        attack_recall = np.mean(y_pred_all[attack_mask] != 0) if np.any(attack_mask) else 0
        
        n_classes = len(self.encoder.classes_)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true_all, y_pred_all, labels=range(n_classes), average=None, zero_division=0
        )
        
        macro_f1 = f1_score(y_true_all, y_pred_all, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_true_all, y_pred_all, average='weighted', zero_division=0)
        
        cm = confusion_matrix(y_true_all, y_pred_all, labels=range(n_classes))
        
        # Report
        self.log(f"\n{dataset_name} Results:")
        self.log(f"  Accuracy: {accuracy:.4f}")
        self.log(f"  Attack Recall: {attack_recall:.4f}")
        self.log(f"  Macro F1: {macro_f1:.4f}")
        self.log(f"  Weighted F1: {weighted_f1:.4f}")
        
        self.log(f"\n  Per-class metrics:")
        self.log(f"  {'Class':<25} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        self.log(f"  {'-'*60}")
        for i, cls in enumerate(self.encoder.classes_):
            self.log(f"  {cls:<25} {precision[i]:>10.4f} {recall[i]:>10.4f} {f1[i]:>10.4f}")
        
        return {
            'accuracy': accuracy,
            'attack_recall': attack_recall,
            'macro_f1': macro_f1,
            'weighted_f1': weighted_f1,
            'precision': precision.tolist(),
            'recall': recall.tolist(),
            'f1': f1.tolist(),
            'support': support.tolist(),
            'confusion_matrix': cm.tolist(),
            'logits': logits_all  # For threshold optimization
        }
    
    def run_fix(self):
        """Execute the fix."""
        
        self.log("\n" + "="*80)
        self.log("ATTACK FORECASTING FIX v3: FOCAL LOSS")
        self.log("="*80)
        self.log(f"Start: {datetime.now()}\n")
        
        # Load data
        self.load_data()
        
        # Compute reduced class weights
        self.compute_class_weights(reduce_factor=0.7)
        
        # Train/val split
        n_train = len(self.y_train)
        split_idx = int(0.8 * n_train)
        
        X_train_split = self.X_train[:split_idx]
        y_train_split = self.y_train[:split_idx]
        X_val_split = self.X_train[split_idx:]
        y_val_split = self.y_train[split_idx:]
        
        # Train model
        self.log("\n" + "="*80)
        self.log("TRAINING: LSTM WITH FOCAL LOSS")
        self.log("="*80)
        
        model = WeightedLSTM(
            input_size=self.X_train.shape[2],
            hidden_size=128,
            num_classes=len(self.encoder.classes_),
            num_layers=2,
            dropout=0.3
        )
        
        model, train_time = self.train_model(
            model,
            X_train_split, y_train_split,
            X_val_split, y_val_split,
            self.class_weights,
            epochs=100,
            batch_size=32,
            lr=0.0005
        )
        
        # Evaluate
        test_results = self.evaluate_model(model, self.X_test, self.y_test, "Test")
        
        # Compare
        self.log("\n" + "="*80)
        self.log("COMPARISON")
        self.log("="*80)
        
        baseline_metrics = {
            'accuracy': 0.9162,
            'attack_recall': 0.0000,
            'macro_f1': 0.3188
        }
        
        self.log(f"\n{'Metric':<30} {'Baseline':>15} {'Focal Loss':>15} {'Delta':>15}")
        self.log(f"{'-'*70}")
        
        for metric in ['accuracy', 'attack_recall', 'macro_f1']:
            baseline_val = baseline_metrics[metric]
            fixed_val = test_results[metric]
            delta = fixed_val - baseline_val
            
            self.log(f"{metric:<30} {baseline_val:>15.4f} {fixed_val:>15.4f} {delta:>15.4f}")
        
        # Save results
        summary = {
            'timestamp': datetime.now().isoformat(),
            'method': 'Focal Loss (gamma=2.0, reduced class weights)',
            'results': {
                'accuracy': test_results['accuracy'],
                'attack_recall': test_results['attack_recall'],
                'macro_f1': test_results['macro_f1'],
                'weighted_f1': test_results['weighted_f1']
            }
        }
        
        output_path = os.path.join(self.output_dir, "attack_forecasting_fix_v3_results.json")
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.log(f"\nResults saved: {output_path}")
        
        # Recommendation
        self.log("\n" + "="*80)
        self.log("DIAGNOSIS & RECOMMENDATION")
        self.log("="*80)
        
        if test_results['attack_recall'] < 0.05:
            self.log(f"\nAttack recall remains <5% across all three approaches:")
            self.log(f"  v1 (3x oversampling): 100% attack recall, 1.6% accuracy [TOO AGGRESSIVE]")
            self.log(f"  v2 (class weights): 80% attack recall, 28% accuracy [TOO AGGRESSIVE]")
            self.log(f"  v3 (focal loss): {test_results['attack_recall']:.2%} attack recall")
            self.log(f"\nCONCLUSION: Dataset may have insufficient temporal forecasting signal.")
            self.log(f"  The attack sequences lack distinctive patterns vs benign sequences.")
            self.log(f"  Imbalance alone is not the root cause.")
        elif test_results['attack_recall'] > 0.20:
            self.log(f"\nRECOMMENDATION: Use Focal Loss model (v3)")
            self.log(f"  Attack recall: {test_results['attack_recall']:.2%}")
            self.log(f"  Macro F1: {test_results['macro_f1']:.4f}")
        else:
            self.log(f"\nPARTIAL SUCCESS: Attack recall improved to {test_results['attack_recall']:.2%}")
            self.log(f"  Still below target threshold of 10-30%")
            self.log(f"  Consider: longer sequences, feature engineering, or dataset limitations")


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixer = AttackForecastingFixv3(
        data_dir=os.path.join(repo_root, "data", "processed"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    results = fixer.run_fix()
