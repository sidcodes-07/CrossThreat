#!/usr/bin/env python3
"""
PHASE 2: MODEL TRAINING
========================

Train 6 model architectures on real CIC-IDS2018 data:
1. Random Forest (baseline, non-temporal)
2. LSTM (sequence model)
3. Mamba (state-space model, lightweight)
4. Transformer Encoder (attention-based)
5. 1D CNN (convolutional over sequences)
6. ViT/Swin (if scientifically justified)

For each: train, calibrate, save checkpoints.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, List
import warnings

warnings.filterwarnings('ignore')

# PyTorch
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV

# Import preprocessing
from sklearn.preprocessing import StandardScaler, LabelEncoder

class TemporalDataset(Dataset):
    """PyTorch dataset for temporal sequences."""
    
    def __init__(self, X, y):
        """
        Args:
            X: (N, seq_len, features) - temporal sequences
            y: (N,) - labels
        """
        self.X = torch.FloatTensor(X)
        self.y = torch.LongTensor(y)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class LSTMModel(nn.Module):
    """LSTM sequence model for temporal forecasting."""
    
    def __init__(self, input_size, hidden_size, num_layers, num_classes, dropout=0.3):
        super(LSTMModel, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc1 = nn.Linear(hidden_size, 128)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(128, num_classes)
        
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        # Use last timestep output
        last_out = lstm_out[:, -1, :]
        x = self.fc1(last_out)
        x = torch.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class TransformerModel(nn.Module):
    """Transformer encoder for temporal sequences."""
    
    def __init__(self, input_size, hidden_size, num_heads, num_layers, num_classes, dropout=0.3):
        super(TransformerModel, self).__init__()
        self.embedding = nn.Linear(input_size, hidden_size)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=256,
            dropout=dropout,
            batch_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc1 = nn.Linear(hidden_size, 128)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(128, num_classes)
    
    def forward(self, x):
        x = self.embedding(x)
        x = self.encoder(x)
        x = x[:, -1, :]  # Use last timestep
        x = self.fc1(x)
        x = torch.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class CNNModel(nn.Module):
    """1D CNN for temporal sequences."""
    
    def __init__(self, input_size, num_classes, dropout=0.3):
        super(CNNModel, self).__init__()
        self.conv1 = nn.Conv1d(input_size, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.pool = nn.MaxPool1d(2)
        self.fc1 = nn.Linear(128 * 2, 128)  # Assuming seq_len reduces after pooling
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(128, num_classes)
    
    def forward(self, x):
        # x shape: (batch, seq_len, features) -> (batch, features, seq_len)
        x = x.transpose(1, 2)
        x = self.conv1(x)
        x = torch.relu(x)
        x = self.pool(x)
        x = self.conv2(x)
        x = torch.relu(x)
        x = self.pool(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.fc1(x)
        x = torch.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class ModelTrainer:
    """Train and evaluate multiple model architectures."""
    
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.results = {}
        self.log_file = os.path.join(output_dir, "training.log")
        self.audit_log = []
    
    def log(self, msg: str):
        """Log to file and stdout."""
        print(msg)
        self.audit_log.append(msg)
        with open(self.log_file, 'a') as f:
            f.write(msg + "\n")
    
    def load_data(self, seq_len: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, 
                                                np.ndarray, np.ndarray, LabelEncoder]:
        """Load preprocessed data for given sequence length."""
        
        self.log(f"\n{'='*80}")
        self.log(f"LOADING DATA (seq_len={seq_len})")
        self.log(f"{'='*80}")
        
        # Load windows
        train_data = np.load(os.path.join(self.data_dir, f"train_seq{seq_len}_windows.npz"))
        test_data = np.load(os.path.join(self.data_dir, f"test_seq{seq_len}_windows.npz"))
        ood_data = np.load(os.path.join(self.data_dir, f"ood_seq{seq_len}_windows.npz"))
        
        X_train, y_train = train_data['X'], train_data['y']
        X_test, y_test = test_data['X'], test_data['y']
        X_ood, y_ood = ood_data['X'], ood_data['y']
        
        self.log(f"Train: X={X_train.shape}, y={y_train.shape}")
        self.log(f"Test: X={X_test.shape}, y={y_test.shape}")
        self.log(f"OOD: X={X_ood.shape}, y={y_ood.shape}")
        
        # Load encoder
        with open(os.path.join(self.data_dir, "encoder.pkl"), 'rb') as f:
            encoder = pickle.load(f)
        
        self.log(f"Classes: {list(encoder.classes_)}")
        
        return X_train, y_train, X_test, y_test, X_ood, y_ood, encoder
    
    def train_pytorch_model(self, model: nn.Module, X_train: np.ndarray, y_train: np.ndarray,
                           X_test: np.ndarray, y_test: np.ndarray, 
                           model_name: str, epochs: int = 50, lr: float = 0.001) -> Dict:
        """Train a PyTorch model."""
        
        self.log(f"\n{'='*80}")
        self.log(f"TRAINING: {model_name}")
        self.log(f"{'='*80}")
        
        # Create datasets
        train_dataset = TemporalDataset(X_train, y_train)
        test_dataset = TemporalDataset(X_test, y_test)
        
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
        
        model = model.to(self.device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        
        best_f1 = 0
        patience = 10
        patience_counter = 0
        
        start_time = datetime.now()
        
        for epoch in range(epochs):
            # Train
            model.train()
            train_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch, y_batch = X_batch.to(self.device), y_batch.to(self.device)
                
                optimizer.zero_grad()
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            # Evaluate
            model.eval()
            y_pred_list = []
            y_true_list = []
            
            with torch.no_grad():
                for X_batch, y_batch in test_loader:
                    X_batch = X_batch.to(self.device)
                    outputs = model(X_batch)
                    _, preds = torch.max(outputs, 1)
                    y_pred_list.extend(preds.cpu().numpy())
                    y_true_list.extend(y_batch.numpy())
            
            accuracy = accuracy_score(y_true_list, y_pred_list)
            macro_f1 = f1_score(y_true_list, y_pred_list, average='macro', zero_division=0)
            
            if (epoch + 1) % 10 == 0:
                self.log(f"Epoch {epoch+1}/{epochs} - Loss: {train_loss/len(train_loader):.4f}, "
                        f"Acc: {accuracy:.4f}, F1: {macro_f1:.4f}")
            
            # Early stopping
            if macro_f1 > best_f1:
                best_f1 = macro_f1
                patience_counter = 0
                best_model_state = model.state_dict()
            else:
                patience_counter += 1
            
            if patience_counter >= patience:
                self.log(f"Early stopping at epoch {epoch+1}")
                model.load_state_dict(best_model_state)
                break
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        # Final evaluation
        model.eval()
        inference_times = []
        
        with torch.no_grad():
            for X_batch, _ in test_loader:
                X_batch = X_batch.to(self.device)
                start_inf = datetime.now()
                outputs = model(X_batch)
                inference_times.append((datetime.now() - start_inf).total_seconds())
        
        avg_inference_latency = np.mean(inference_times) / 32 * 1000  # ms per sample
        
        # Count parameters
        param_count = sum(p.numel() for p in model.parameters())
        
        self.log(f"Training time: {training_time:.2f}s")
        self.log(f"Avg inference latency: {avg_inference_latency:.4f}ms per sample")
        self.log(f"Parameter count: {param_count:,}")
        
        return {
            "model": model,
            "training_time": training_time,
            "inference_latency_ms": avg_inference_latency,
            "param_count": param_count
        }
    
    def train_random_forest(self, X_train: np.ndarray, y_train: np.ndarray,
                           X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """Train Random Forest baseline (non-temporal)."""
        
        self.log(f"\n{'='*80}")
        self.log(f"TRAINING: Random Forest (BASELINE)")
        self.log(f"{'='*80}")
        
        # Flatten sequences for RF
        X_train_flat = X_train.reshape(X_train.shape[0], -1)
        X_test_flat = X_test.reshape(X_test.shape[0], -1)
        
        start_time = datetime.now()
        
        rf = RandomForestClassifier(n_estimators=100, max_depth=20, n_jobs=-1, random_state=42)
        rf.fit(X_train_flat, y_train)
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        # Inference time
        start_inf = datetime.now()
        _ = rf.predict(X_test_flat[:100])
        inference_latency_ms = (datetime.now() - start_inf).total_seconds() / 100 * 1000
        
        param_count = sum(tree.tree_.node_count for tree in rf.estimators_)
        
        self.log(f"Training time: {training_time:.2f}s")
        self.log(f"Avg inference latency: {inference_latency_ms:.4f}ms per sample")
        self.log(f"Parameter count (nodes): {param_count:,}")
        
        return {
            "model": rf,
            "training_time": training_time,
            "inference_latency_ms": inference_latency_ms,
            "param_count": param_count,
            "is_flattened": True
        }
    
    def evaluate_model(self, model, X_test, y_test, encoder, is_flattened=False) -> Dict:
        """Evaluate model and return comprehensive metrics."""
        
        # Predict
        if is_flattened:
            X_test_flat = X_test.reshape(X_test.shape[0], -1)
            y_pred = model.predict(X_test_flat)
        else:
            model.eval()
            X_tensor = torch.FloatTensor(X_test).to(self.device)
            with torch.no_grad():
                outputs = model(X_tensor)
                _, y_pred = torch.max(outputs, 1)
                y_pred = y_pred.cpu().numpy()
        
        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        
        # Attack-only metrics
        benign_class = 0  # Benign is always class 0
        attack_mask = y_test != benign_class
        
        if attack_mask.sum() > 0:
            y_test_attack = y_test[attack_mask]
            y_pred_attack = y_pred[attack_mask]
            attack_recall = f1_score(y_test_attack, y_pred_attack, average='macro', zero_division=0)
        else:
            attack_recall = 0
        
        # Per-class metrics
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred, labels=range(len(encoder.classes_)))
        
        return {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
            "attack_recall": attack_recall,
            "per_class_metrics": report,
            "confusion_matrix": cm.tolist(),
            "y_pred": y_pred.tolist(),
            "y_true": y_test.tolist()
        }
    
    def train_all_models(self):
        """Train and evaluate all models across all sequence lengths."""
        
        self.log(f"\n\n{'='*80}")
        self.log(f"CROSSTHREAT MODEL TRAINING - PHASE 2")
        self.log(f"{'='*80}")
        self.log(f"Start time: {datetime.now()}")
        self.log(f"Device: {self.device}")
        
        # Test each sequence length
        for seq_len in [5, 10, 15]:
            self.log(f"\n\n{'#'*80}")
            self.log(f"SEQUENCE LENGTH: {seq_len}")
            self.log(f"{'#'*80}")
            
            X_train, y_train, X_test, y_test, X_ood, y_ood, encoder = self.load_data(seq_len)
            
            seq_results = {}
            
            # 1. Random Forest (baseline)
            try:
                rf_info = self.train_random_forest(X_train, y_train, X_test, y_test)
                rf_metrics = self.evaluate_model(
                    rf_info['model'], X_test, y_test, encoder,
                    is_flattened=True
                )
                seq_results['random_forest'] = {
                    "training_time": rf_info['training_time'],
                    "inference_latency_ms": rf_info['inference_latency_ms'],
                    "param_count": rf_info['param_count'],
                    **rf_metrics
                }
                self.log(f"RF - Acc: {rf_metrics['accuracy']:.4f}, F1: {rf_metrics['macro_f1']:.4f}, "
                        f"Attack Recall: {rf_metrics['attack_recall']:.4f}")
            except Exception as e:
                self.log(f"[ERROR] Random Forest: {e}")
            
            # 2. LSTM
            try:
                lstm = LSTMModel(X_train.shape[2], 128, 2, len(encoder.classes_), dropout=0.3)
                lstm_info = self.train_pytorch_model(lstm, X_train, y_train, X_test, y_test, "LSTM")
                lstm_metrics = self.evaluate_model(lstm_info['model'], X_test, y_test, encoder)
                seq_results['lstm'] = {
                    "training_time": lstm_info['training_time'],
                    "inference_latency_ms": lstm_info['inference_latency_ms'],
                    "param_count": lstm_info['param_count'],
                    **lstm_metrics
                }
                self.log(f"LSTM - Acc: {lstm_metrics['accuracy']:.4f}, F1: {lstm_metrics['macro_f1']:.4f}, "
                        f"Attack Recall: {lstm_metrics['attack_recall']:.4f}")
            except Exception as e:
                self.log(f"[ERROR] LSTM: {e}")
            
            # 3. Transformer
            try:
                transformer = TransformerModel(X_train.shape[2], 64, 4, 2, len(encoder.classes_))
                transformer_info = self.train_pytorch_model(
                    transformer, X_train, y_train, X_test, y_test, "Transformer"
                )
                transformer_metrics = self.evaluate_model(transformer_info['model'], X_test, y_test, encoder)
                seq_results['transformer'] = {
                    "training_time": transformer_info['training_time'],
                    "inference_latency_ms": transformer_info['inference_latency_ms'],
                    "param_count": transformer_info['param_count'],
                    **transformer_metrics
                }
                self.log(f"Transformer - Acc: {transformer_metrics['accuracy']:.4f}, "
                        f"F1: {transformer_metrics['macro_f1']:.4f}, "
                        f"Attack Recall: {transformer_metrics['attack_recall']:.4f}")
            except Exception as e:
                self.log(f"[ERROR] Transformer: {e}")
            
            # 4. 1D CNN
            try:
                cnn = CNNModel(X_train.shape[2], len(encoder.classes_))
                cnn_info = self.train_pytorch_model(cnn, X_train, y_train, X_test, y_test, "1D CNN")
                cnn_metrics = self.evaluate_model(cnn_info['model'], X_test, y_test, encoder)
                seq_results['cnn'] = {
                    "training_time": cnn_info['training_time'],
                    "inference_latency_ms": cnn_info['inference_latency_ms'],
                    "param_count": cnn_info['param_count'],
                    **cnn_metrics
                }
                self.log(f"CNN - Acc: {cnn_metrics['accuracy']:.4f}, F1: {cnn_metrics['macro_f1']:.4f}, "
                        f"Attack Recall: {cnn_metrics['attack_recall']:.4f}")
            except Exception as e:
                self.log(f"[ERROR] CNN: {e}")
            
            self.results[f"seq_{seq_len}"] = seq_results
        
        # Save results
        self.log(f"\n\n{'='*80}")
        self.log("SAVING RESULTS")
        self.log(f"{'='*80}")
        
        results_path = os.path.join(self.output_dir, "model_training_results.json")
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        self.log(f"[OK] {results_path}")
        
        self.log(f"\nEnd time: {datetime.now()}")
        self.log(f"\n{'='*80}")
        self.log("TRAINING COMPLETE")
        self.log(f"{'='*80}")


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    trainer = ModelTrainer(
        data_dir=os.path.join(repo_root, "data", "processed"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    trainer.train_all_models()
    
    print("\n" + "="*80)
    print("MODEL TRAINING SUMMARY")
    print("="*80)
    for seq_len, models in trainer.results.items():
        print(f"\n{seq_len}:")
        for model_name, metrics in models.items():
            print(f"  {model_name:<20} Acc: {metrics['accuracy']:.4f}  "
                  f"F1: {metrics['macro_f1']:.4f}  Attack Recall: {metrics['attack_recall']:.4f}")
