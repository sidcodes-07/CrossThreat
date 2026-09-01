#!/usr/bin/env python3
"""
ATTACK FORECASTING FIX: IMPLEMENTATION
=======================================

Implements Option 1: Class-weighted loss + sequence oversampling

This is the scientifically sound solution to the 0% attack recall problem.
"""

import os
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
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

class AttackForecastingFix:
    """Implement the comprehensive attack forecasting fix."""
    
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
        
        self.X_train_orig = train_win['X']
        self.y_train_orig = train_win['y']
        self.X_test = test_win['X']
        self.y_test = test_win['y']
        
        self.log(f"  Train: {self.X_train_orig.shape}, Test: {self.X_test.shape}")
    
    def compute_class_weights(self):
        """Compute inverse frequency class weights."""
        self.log("\nComputing class weights...")
        
        counts = np.bincount(self.y_train_orig)
        weights = []
        
        for i, count in enumerate(counts):
            w = len(self.y_train_orig) / (len(counts) * count)
            weights.append(w)
            cls_name = self.encoder.classes_[i]
            self.log(f"  {cls_name:<25} count={count:5} weight={w:.4f}")
        
        self.class_weights = np.array(weights)
        return self.class_weights
    
    def oversample_attack_sequences(self, oversample_factor: float = 3.0):
        """Oversample attack sequences to balance training set."""
        self.log(f"\nOversampling attack sequences (factor={oversample_factor})...")
        
        # Separate benign and attack sequences
        benign_mask = self.y_train_orig == 0
        attack_mask = ~benign_mask
        
        X_benign = self.X_train_orig[benign_mask]
        y_benign = self.y_train_orig[benign_mask]
        
        X_attack = self.X_train_orig[attack_mask]
        y_attack = self.y_train_orig[attack_mask]
        
        self.log(f"  Benign: {len(y_benign)}, Attack: {len(y_attack)}")
        
        # Oversample attack sequences
        n_attack_repeat = int(len(y_attack) * (oversample_factor - 1))
        repeat_indices = np.random.choice(len(y_attack), size=n_attack_repeat, replace=True)
        
        X_attack_repeated = X_attack[repeat_indices]
        y_attack_repeated = y_attack[repeat_indices]
        
        # Combine
        X_train_aug = np.vstack([X_benign, X_attack, X_attack_repeated])
        y_train_aug = np.hstack([y_benign, y_attack, y_attack_repeated])
        
        # Shuffle
        perm = np.random.permutation(len(y_train_aug))
        X_train_aug = X_train_aug[perm]
        y_train_aug = y_train_aug[perm]
        
        self.log(f"  After oversampling: Benign={np.sum(y_train_aug==0)}, Attack={np.sum(y_train_aug!=0)}")
        self.log(f"  New imbalance ratio: 1:{np.sum(y_train_aug==0)/np.sum(y_train_aug!=0):.2f}")
        
        self.X_train = X_train_aug
        self.y_train = y_train_aug
    
    def train_model(self, model: nn.Module, X: np.ndarray, y: np.ndarray, 
                   X_val: np.ndarray, y_val: np.ndarray, 
                   class_weights: np.ndarray,
                   epochs: int = 50, batch_size: int = 32, lr: float = 0.001):
        """Train weighted LSTM with class weights."""
        
        self.log(f"\nTraining WeightedLSTM...")
        self.log(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {lr}")
        
        # Create datasets
        train_dataset = SequenceDataset(X, y)
        val_dataset = SequenceDataset(X_val, y_val)
        
        # Use class weights for sampling
        weights_per_sample = class_weights[y]
        sampler = WeightedRandomSampler(
            weights=weights_per_sample,
            num_samples=len(y),
            replacement=True
        )
        
        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, sampler=sampler
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Optimizer
        optimizer = Adam(model.parameters(), lr=lr)
        
        # Loss with class weights
        weight_tensor = torch.FloatTensor(class_weights).to(DEVICE)
        criterion = nn.CrossEntropyLoss(weight=weight_tensor)
        
        model.to(DEVICE)
        best_macro_f1 = 0
        patience = 15
        patience_counter = 0
        
        train_losses = []
        val_f1s = []
        
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
                optimizer.step()
                
                epoch_loss += loss.item()
            
            epoch_loss /= len(train_loader)
            train_losses.append(epoch_loss)
            
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
            val_f1s.append(macro_f1)
            
            if (epoch + 1) % 10 == 0:
                self.log(f"  Epoch {epoch+1:3d}: loss={epoch_loss:.4f}, macro_f1={macro_f1:.4f}")
            
            # Early stopping
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
        attack_mask = y_true_all != 0
        attack_recall = np.mean(y_pred_all[attack_mask] != 0) if np.any(attack_mask) else 0
        
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
        self.log("ATTACK FORECASTING FIX: EXECUTION")
        self.log("="*80)
        self.log(f"Start: {datetime.now()}\n")
        
        # Step 1: Load data
        self.load_data()
        
        # Step 2: Compute class weights
        self.compute_class_weights()
        
        # Step 3: Evaluate baseline (no fix)
        self.log("\n" + "="*80)
        self.log("BASELINE (No fix - original class imbalance)")
        self.log("="*80)
        
        model_baseline = WeightedLSTM(
            input_size=self.X_train_orig.shape[2],
            hidden_size=128,
            num_classes=len(self.encoder.classes_),
            num_layers=2,
            dropout=0.3
        )
        
        model_baseline, baseline_train_time = self.train_model(
            model_baseline,
            self.X_train_orig, self.y_train_orig,
            self.X_test, self.y_test,
            np.ones(len(self.encoder.classes_)),  # No weighting
            epochs=50
        )
        
        baseline_results = self.evaluate_model(model_baseline, self.X_test, self.y_test, "Baseline")
        self.results['baseline'] = baseline_results
        
        # Step 4: Apply fix (class weights + oversampling)
        self.log("\n" + "="*80)
        self.log("FIXED MODEL (Class weights + Oversampling)")
        self.log("="*80)
        
        self.oversample_attack_sequences(oversample_factor=3.0)
        
        model_fixed = WeightedLSTM(
            input_size=self.X_train.shape[2],
            hidden_size=128,
            num_classes=len(self.encoder.classes_),
            num_layers=2,
            dropout=0.3
        )
        
        model_fixed, fixed_train_time = self.train_model(
            model_fixed,
            self.X_train, self.y_train,
            self.X_test, self.y_test,
            self.class_weights,
            epochs=50
        )
        
        fixed_results = self.evaluate_model(model_fixed, self.X_test, self.y_test, "Fixed")
        self.results['fixed'] = fixed_results
        
        # Step 5: Compare
        self.log("\n" + "="*80)
        self.log("BEFORE vs AFTER COMPARISON")
        self.log("="*80)
        
        self.log(f"\n{'Metric':<30} {'Baseline':>15} {'Fixed':>15} {'Improvement':>15}")
        self.log(f"{'-'*75}")
        
        for metric in ['accuracy', 'attack_recall', 'macro_f1', 'weighted_f1', 'latency_ms']:
            baseline_val = baseline_results[metric]
            fixed_val = fixed_results[metric]
            
            if metric == 'latency_ms':
                improvement = baseline_val - fixed_val
                pct = (improvement / baseline_val * 100) if baseline_val > 0 else 0
            else:
                improvement = fixed_val - baseline_val
                pct = (improvement / baseline_val * 100) if baseline_val > 0 else 0
            
            self.log(f"{metric:<30} {baseline_val:>15.4f} {fixed_val:>15.4f} {pct:>14.1f}%")
        
        # Step 6: Success evaluation
        self.log("\n" + "="*80)
        self.log("SUCCESS EVALUATION")
        self.log("="*80)
        
        min_threshold_met = (
            fixed_results['attack_recall'] > 0.10 and
            fixed_results['macro_f1'] > 0.40
        )
        
        optimal_threshold_met = (
            fixed_results['attack_recall'] > 0.30 and
            fixed_results['macro_f1'] > 0.50
        )
        
        self.log(f"\nMinimum threshold (Attack recall >10%, Macro F1 >0.40):")
        self.log(f"  Attack recall: {fixed_results['attack_recall']:.4f} {'[OK]' if fixed_results['attack_recall'] > 0.10 else '[FAIL]'}")
        self.log(f"  Macro F1: {fixed_results['macro_f1']:.4f} {'[OK]' if fixed_results['macro_f1'] > 0.40 else '[FAIL]'}")
        self.log(f"  Status: {'MET' if min_threshold_met else 'NOT MET'}")
        
        self.log(f"\nOptimal threshold (Attack recall >30%, Macro F1 >0.50):")
        self.log(f"  Attack recall: {fixed_results['attack_recall']:.4f} {'[OK]' if fixed_results['attack_recall'] > 0.30 else '[FAIL]'}")
        self.log(f"  Macro F1: {fixed_results['macro_f1']:.4f} {'[OK]' if fixed_results['macro_f1'] > 0.50 else '[FAIL]'}")
        self.log(f"  Status: {'MET' if optimal_threshold_met else 'NOT MET'}")
        
        # Save results
        summary = {
            'timestamp': datetime.now().isoformat(),
            'method': 'Class-weighted loss + sequence oversampling (factor=3.0)',
            'baseline': baseline_results,
            'fixed': fixed_results,
            'improvement': {
                'attack_recall_increase': fixed_results['attack_recall'] - baseline_results['attack_recall'],
                'attack_recall_increase_pct': (fixed_results['attack_recall'] - baseline_results['attack_recall']) / (baseline_results['attack_recall'] + 1e-6) * 100,
                'macro_f1_increase': fixed_results['macro_f1'] - baseline_results['macro_f1'],
                'macro_f1_increase_pct': (fixed_results['macro_f1'] - baseline_results['macro_f1']) / (baseline_results['macro_f1'] + 1e-6) * 100
            },
            'success': min_threshold_met,
            'optimal': optimal_threshold_met
        }
        
        output_path = os.path.join(self.output_dir, "attack_forecasting_fix_results.json")
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.log(f"\nResults saved: {output_path}")
        self.log(f"End: {datetime.now()}")
        
        # Save models
        torch.save(model_baseline.state_dict(), os.path.join(self.output_dir, "lstm_baseline.pt"))
        torch.save(model_fixed.state_dict(), os.path.join(self.output_dir, "lstm_fixed.pt"))
        self.log(f"Models saved: lstm_baseline.pt, lstm_fixed.pt")
        
        return summary


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixer = AttackForecastingFix(
        data_dir=os.path.join(repo_root, "data", "processed"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    results = fixer.run_fix()
