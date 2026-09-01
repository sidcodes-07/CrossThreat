#!/usr/bin/env python3
"""
ATTACK FORECASTING FIX: BALANCED APPROACH
==========================================

The first fix was too aggressive (100% attack recall but 1.6% accuracy).

This version uses a more conservative approach:
1. Class-weighted loss only (no oversampling)
2. Lower learning rate for more stable training
3. Careful validation to avoid overcorrection
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
    """PyTorch dataset for temporal sequences."""
    
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.LongTensor(y)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class WeightedLSTM(nn.Module):
    """LSTM designed for class-imbalanced sequence classification."""
    
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

class AttackForecastingFixv2:
    """Implement balanced attack forecasting fix."""
    
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results = {}
    
    def log(self, msg: str):
        print(msg)
    
    def load_data(self):
        """Load preprocessed data."""
        self.log("Loading preprocessed data...")
        
        with open(os.path.join(self.data_dir, "train_df.pkl"), 'rb') as f:
            self.train_df = pickle.load(f)
        
        with open(os.path.join(self.data_dir, "test_df.pkl"), 'rb') as f:
            self.test_df = pickle.load(f)
        
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
    
    def compute_class_weights(self):
        """Compute inverse frequency class weights."""
        self.log("\nComputing class weights...")
        
        counts = np.bincount(self.y_train)
        weights = []
        
        for i, count in enumerate(counts):
            w = len(self.y_train) / (len(counts) * count)
            weights.append(w)
            cls_name = self.encoder.classes_[i]
            self.log(f"  {cls_name:<25} count={count:5} weight={w:.4f}")
        
        self.class_weights = np.array(weights)
        return self.class_weights
    
    def train_model(self, model: nn.Module, X: np.ndarray, y: np.ndarray, 
                   X_val: np.ndarray, y_val: np.ndarray, 
                   class_weights: np.ndarray,
                   epochs: int = 100, batch_size: int = 32, lr: float = 0.0005):
        """Train LSTM with class weights."""
        
        self.log(f"\nTraining LSTM...")
        self.log(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {lr}")
        
        # Create datasets
        train_dataset = SequenceDataset(X, y)
        val_dataset = SequenceDataset(X_val, y_val)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Optimizer
        optimizer = Adam(model.parameters(), lr=lr, weight_decay=1e-5)
        
        # Loss with class weights
        weight_tensor = torch.FloatTensor(class_weights).to(DEVICE)
        criterion = nn.CrossEntropyLoss(weight=weight_tensor)
        
        model.to(DEVICE)
        best_macro_f1 = 0
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
            
            macro_f1 = f1_score(y_true_all, y_pred_all, average='macro', zero_division=0)
            attack_recall = self._compute_attack_recall(np.array(y_true_all), np.array(y_pred_all))
            
            if (epoch + 1) % 20 == 0:
                self.log(f"  Epoch {epoch+1:3d}: loss={epoch_loss:.4f}, macro_f1={macro_f1:.4f}, attack_recall={attack_recall:.4f}")
            
            # Early stopping based on macro F1
            if macro_f1 > best_macro_f1:
                best_macro_f1 = macro_f1
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
        self.log(f"  Best macro F1: {best_macro_f1:.4f}")
        
        return model, train_time
    
    def _compute_attack_recall(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Compute attack recall (recall for all attack classes combined)."""
        attack_mask = y_true != 0
        if not np.any(attack_mask):
            return 0.0
        return np.mean(y_pred[attack_mask] != 0)
    
    def evaluate_model(self, model: nn.Module, X: np.ndarray, y: np.ndarray, 
                      dataset_name: str = "Test"):
        """Comprehensive model evaluation."""
        
        self.log(f"\nEvaluating on {dataset_name} set...")
        
        model.eval()
        dataset = SequenceDataset(X, y)
        loader = DataLoader(dataset, batch_size=32, shuffle=False)
        
        y_pred_all = []
        y_true_all = []
        inference_times = []
        
        with torch.no_grad():
            for X_batch, y_batch in loader:
                X_batch = X_batch.to(DEVICE)
                
                # Measure inference latency
                start = time.time()
                logits = model(X_batch)
                end = time.time()
                inference_times.append((end - start) / len(X_batch))
                
                y_pred = torch.argmax(logits, dim=1)
                y_pred_all.extend(y_pred.cpu().numpy())
                y_true_all.extend(y_batch.numpy())
        
        y_pred_all = np.array(y_pred_all)
        y_true_all = np.array(y_true_all)
        
        # Metrics
        accuracy = np.mean(y_pred_all == y_true_all)
        attack_recall = self._compute_attack_recall(y_true_all, y_pred_all)
        
        # Ensure we get metrics for all classes
        n_classes = len(self.encoder.classes_)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true_all, y_pred_all, labels=range(n_classes), average=None, zero_division=0
        )
        
        macro_f1 = f1_score(y_true_all, y_pred_all, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_true_all, y_pred_all, average='weighted', zero_division=0)
        
        avg_latency = np.mean(inference_times) * 1000  # ms
        
        # Confusion matrix
        cm = confusion_matrix(y_true_all, y_pred_all, labels=range(n_classes))
        
        # Report
        self.log(f"\n{dataset_name} Results:")
        self.log(f"  Accuracy: {accuracy:.4f}")
        self.log(f"  Attack Recall: {attack_recall:.4f}")
        self.log(f"  Macro F1: {macro_f1:.4f}")
        self.log(f"  Weighted F1: {weighted_f1:.4f}")
        self.log(f"  Avg Inference Latency: {avg_latency:.4f} ms")
        
        self.log(f"\n  Per-class metrics:")
        self.log(f"  {'Class':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
        self.log(f"  {'-'*70}")
        for i, cls in enumerate(self.encoder.classes_):
            if i < len(precision):
                self.log(f"  {cls:<25} {precision[i]:>10.4f} {recall[i]:>10.4f} {f1[i]:>10.4f} {support[i]:>10.0f}")
        
        return {
            'accuracy': accuracy,
            'attack_recall': attack_recall,
            'macro_f1': macro_f1,
            'weighted_f1': weighted_f1,
            'latency_ms': avg_latency,
            'precision': precision.tolist(),
            'recall': recall.tolist(),
            'f1': f1.tolist(),
            'support': support.tolist(),
            'confusion_matrix': cm.tolist()
        }
    
    def run_fix(self):
        """Execute the complete fix."""
        
        self.log("\n" + "="*80)
        self.log("ATTACK FORECASTING FIX v2: BALANCED APPROACH")
        self.log("="*80)
        self.log(f"Start: {datetime.now()}\n")
        
        # Load data
        self.load_data()
        
        # Compute class weights
        self.compute_class_weights()
        
        # Split data for training/validation
        # Use first 80% of training data for training, last 20% for validation
        n_train = len(self.y_train)
        split_idx = int(0.8 * n_train)
        
        X_train_split = self.X_train[:split_idx]
        y_train_split = self.y_train[:split_idx]
        X_val_split = self.X_train[split_idx:]
        y_val_split = self.y_train[split_idx:]
        
        # Train model with class weights
        self.log("\n" + "="*80)
        self.log("TRAINING: LSTM WITH CLASS WEIGHTS")
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
        
        # Evaluate on test set
        test_results = self.evaluate_model(model, self.X_test, self.y_test, "Test")
        
        # Compare to baseline metrics from previous run
        self.log("\n" + "="*80)
        self.log("IMPROVEMENT ANALYSIS")
        self.log("="*80)
        
        baseline_metrics = {
            'accuracy': 0.9162,
            'attack_recall': 0.0000,
            'macro_f1': 0.3188,
            'weighted_f1': 0.8761
        }
        
        self.log(f"\n{'Metric':<30} {'Baseline':>15} {'Fixed':>15} {'Change':>15}")
        self.log(f"{'-'*75}")
        
        for metric in ['accuracy', 'attack_recall', 'macro_f1', 'weighted_f1']:
            baseline_val = baseline_metrics[metric]
            fixed_val = test_results[metric]
            change = fixed_val - baseline_val
            pct = (change / (abs(baseline_val) + 1e-6)) * 100
            
            self.log(f"{metric:<30} {baseline_val:>15.4f} {fixed_val:>15.4f} {pct:>14.1f}%")
        
        # Evaluate success
        self.log("\n" + "="*80)
        self.log("SUCCESS CRITERIA")
        self.log("="*80)
        
        min_thresh_met = (
            test_results['attack_recall'] > 0.10 and
            test_results['macro_f1'] > 0.40 and
            test_results['accuracy'] > 0.80
        )
        
        optimal_thresh_met = (
            test_results['attack_recall'] > 0.30 and
            test_results['macro_f1'] > 0.50 and
            test_results['accuracy'] > 0.85
        )
        
        self.log(f"\nMinimum (Attack recall >10%, Macro F1 >0.40, Accuracy >80%):")
        self.log(f"  Attack recall: {test_results['attack_recall']:.4f} {'[MET]' if test_results['attack_recall'] > 0.10 else '[NOT MET]'}")
        self.log(f"  Macro F1: {test_results['macro_f1']:.4f} {'[MET]' if test_results['macro_f1'] > 0.40 else '[NOT MET]'}")
        self.log(f"  Accuracy: {test_results['accuracy']:.4f} {'[MET]' if test_results['accuracy'] > 0.80 else '[NOT MET]'}")
        self.log(f"  Overall: {'SUCCESS' if min_thresh_met else 'FAILED'}")
        
        self.log(f"\nOptimal (Attack recall >30%, Macro F1 >0.50, Accuracy >85%):")
        self.log(f"  Attack recall: {test_results['attack_recall']:.4f} {'[MET]' if test_results['attack_recall'] > 0.30 else '[NOT MET]'}")
        self.log(f"  Macro F1: {test_results['macro_f1']:.4f} {'[MET]' if test_results['macro_f1'] > 0.50 else '[NOT MET]'}")
        self.log(f"  Accuracy: {test_results['accuracy']:.4f} {'[MET]' if test_results['accuracy'] > 0.85 else '[NOT MET]'}")
        self.log(f"  Overall: {'SUCCESS' if optimal_thresh_met else 'FAILED'}")
        
        # Save results
        summary = {
            'timestamp': datetime.now().isoformat(),
            'method': 'Class-weighted loss (conservative approach)',
            'hyperparameters': {
                'epochs': 100,
                'batch_size': 32,
                'learning_rate': 0.0005,
                'hidden_size': 128,
                'num_layers': 2,
                'dropout': 0.3
            },
            'baseline': baseline_metrics,
            'results': test_results,
            'improvement': {
                'attack_recall_delta': test_results['attack_recall'] - baseline_metrics['attack_recall'],
                'macro_f1_delta': test_results['macro_f1'] - baseline_metrics['macro_f1'],
                'accuracy_delta': test_results['accuracy'] - baseline_metrics['accuracy']
            },
            'minimum_threshold_met': min_thresh_met,
            'optimal_threshold_met': optimal_thresh_met,
            'train_time_seconds': train_time
        }
        
        output_path = os.path.join(self.output_dir, "attack_forecasting_fix_v2_results.json")
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.log(f"\nResults saved: {output_path}")
        
        # Save model
        torch.save(model.state_dict(), os.path.join(self.output_dir, "lstm_weighted_v2.pt"))
        self.log(f"Model saved: lstm_weighted_v2.pt")
        
        self.log(f"End: {datetime.now()}")
        
        return summary


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixer = AttackForecastingFixv2(
        data_dir=os.path.join(repo_root, "data", "processed"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    results = fixer.run_fix()
