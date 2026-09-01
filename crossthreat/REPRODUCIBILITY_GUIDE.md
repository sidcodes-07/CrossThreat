# Reproducibility Guide: Attack Forecasting Fix

## How to Reproduce Results

### Step 1: Verify Data Pipeline
```bash
cd C:\CyberShield\crossthreat
python engines/data_pipeline.py
```
**Outputs:**
- `data/processed/train_df.pkl` (2.2 MB)
- `data/processed/test_df.pkl` (560 KB)
- `data/processed/train_seq5_windows.npz` (3.9 MB)
- `data/processed/test_seq5_windows.npz` (1.0 MB)
- Temporal windows with no leakage

### Step 2: Run Diagnosis
```bash
python engines/attack_forecasting_diagnostic.py
```
**Output:**
- `data/processed/attack_forecasting_diagnosis.json`
- Confirms class imbalance as root cause
- Lists all fix options with expected impact

### Step 3: Test All Three Approaches

**Version 1 (Aggressive Oversampling):**
```bash
python engines/attack_forecasting_fix_impl.py
```
- Output: `attack_forecasting_fix_results.json`
- Result: 100% attack recall, 1.6% accuracy (TOO AGGRESSIVE)

**Version 2 (Conservative Class Weights):**
```bash
python engines/attack_forecasting_fix_v2.py
```
- Output: `attack_forecasting_fix_v2_results.json`
- Result: 80.5% attack recall, 28.2% accuracy (STILL TOO AGGRESSIVE)

**Version 3 (Focal Loss - RECOMMENDED):**
```bash
python engines/attack_forecasting_fix_v3.py
```
- Output: `attack_forecasting_fix_v3_results.json`
- Result: 38.3% attack recall, 74.3% accuracy (BALANCED ✓)

### Step 4: Review Final Summary
```bash
python engines/attack_forecasting_fix_final_summary.py
```
- Comprehensive comparison of all three approaches
- Recommendations and next steps

---

## Dataset Configuration

### CIC-IDS2018 Dataset
```
Source: Cybersecurity and Infrastructure Security Agency (CISA)
Location: data/raw/CIC_IDS2018_*.csv (10 files)
Date Range: 2018-02-14 to 2018-03-02
Total Samples: 20,000 network flows

File Organization:
  - 10 CSV files (2000 rows each)
  - Chronologically ordered (Feb 14 → Mar 02)
  - No random shuffling in loading
```

### Label Distribution
```
Training Set (16,000 samples):
  Benign:           14,194 (88.71%)
  SQL Injection:        97 (0.61%)
  Brute Force-Web:     150 (0.94%)
  Brute Force-XSS:     155 (0.97%)
  DDoS-LOIC-HTTP:      148 (0.93%)
  DoS-Hulk:            142 (0.89%)
  DoS-Slowloris:       156 (0.98%)
  Heartbleed:          100 (0.63%)
  DDoS-HOIC:           152 (0.95%)
  Bot:                 266 (1.67%)
  Infiltration:        423 (2.65%)

Test Set (4,000 samples):
  Benign:            3,596 (89.90%)
  All attacks:         404 (10.10%)
```

### Feature Set (12 numeric features)
```python
numeric_features = [
    'Protocol',                # 0=TCP, 1=UDP, 2=Other
    'Flow Duration',           # microseconds
    'Fwd Packet Count',        # forward packets
    'Bwd Packet Count',        # backward packets
    'Fwd Packet Len Max',      # maximum payload
    'Bwd Packet Len Max',      # maximum payload
    'Flow Byts/s',             # bytes per second
    'Flow Pkts/s',             # packets per second
    'Bwd PSH Flags',           # TCP PSH flags
    'Bwd URG Flags',           # TCP URG flags
    'Fwd Header Len',          # TCP/UDP header
    'Packet Length Std'        # standard deviation
]
```

### Data Preprocessing
```python
1. Missing Value Handling:
   - Flow Duration: 80 NaN in train, 28 in test → filled with column mean
   
2. Infinity Value Handling:
   - Flow Byts/s and Flow Pkts/s produce inf/-inf from division by zero
   - Replaced with NaN, then filled with column mean
   
3. Normalization:
   - StandardScaler fitted ONLY on training data
   - Applied to both training and test sets
   - Prevents data leakage
   
4. Label Encoding:
   - 11 classes (Benign + 10 attack types)
   - LabelEncoder fitted on training data
   - Classes: {0: 'Benign', 1-10: attack types}
```

---

## Temporal Windowing Configuration

### Window Creation Strategy
```python
seq_len = 5  # Number of timesteps per window
Input:  [t-5, t-4, t-3, t-2, t-1]  # 5 historical flows
Target: label(t)                     # Next flow's label

No Future Leakage: ✓
- Input uses only past timestamps
- Target is strictly future label
- No information flows backward in time
```

### Window Statistics
```
Training Windows (seq_len=5):
  Total: 15,925 windows
  Benign: 14,136 (88.77%)
  Attacks: 1,789 (11.23%)
  
Test Windows (seq_len=5):
  Total: 3,925 windows
  Benign: 3,596 (91.62%)
  Attacks: 329 (8.38%)
```

### Temporal Attack Transitions
```
Benign → Attack:   1,508 transitions (enough for forecasting)
Attack → Attack:     281 transitions (some attack persistence)
Attack → Benign:   1,508 transitions (attacks end)
```

---

## Model Configuration

### LSTM Architecture (All Versions)
```python
class WeightedLSTM(nn.Module):
    Input:  (batch_size, seq_len=5, features=12)
    
    LSTM Layer 1:
      - hidden_size: 128
      - num_layers: 2
      - dropout: 0.3 (between layers)
      - bidirectional: False (unidirectional forecasting)
    
    Dense Layers:
      - FC1: 128 → 64 (ReLU activation + dropout)
      - FC2: 64 → 11 (output logits, one per class)
    
    Output: (batch_size, num_classes=11)
```

### Loss Functions

**Version 1 & 2: Weighted CrossEntropyLoss**
```python
weight = len(train_data) / (num_classes * class_count)

Weights:
  Benign:           0.1024
  SQL Injection:   14.9250
  Brute Force-Web:  9.6515
  Brute Force-XSS:  9.3402
  DDoS-LOIC-HTTP:   9.7819
  DoS-Hulk:        10.1953
  DoS-Slowloris:    9.2803
  Heartbleed:      14.4773
  DDoS-HOIC:        9.5245
  Bot:              5.4426
  Infiltration:     3.4225

Loss = CrossEntropyLoss(weight=weight_tensor)
```

**Version 3: Focal Loss (Recommended)**
```python
Focal Loss: FL(p_t) = -(1 - p_t)^gamma * log(p_t)

Parameters:
  gamma: 2.0 (focus parameter)
  alpha (weights): 0.7x inverse frequency (reduced aggression)
  
class FocalLoss(nn.Module):
    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, weight=alpha)
        p = torch.exp(-ce_loss)
        focal_loss = (1 - p) ** gamma * ce_loss
        return focal_loss.mean()
```

### Training Configuration

| Parameter | Value |
|-----------|-------|
| Optimizer | Adam (lr=0.0005, weight_decay=1e-5) |
| Batch Size | 32 |
| Epochs | 100 (with early stopping) |
| Early Stopping | Patience=20 epochs, metric=macro F1 |
| Gradient Clipping | max_norm=1.0 |
| Device | CPU (no CUDA required) |

---

## Validation Strategy

### Train/Validation/Test Split
```python
Full Training Set: 15,925 windows
  ├─ Train Split: 12,740 windows (80%)
  ├─ Validation Split: 3,185 windows (20%)
  └─ Used for: Early stopping on macro F1

Test Set: 3,925 windows (untouched)
  └─ Used for: Final evaluation only
```

### No Data Leakage Verification
```python
✓ Train samples: indices 0-15924
✓ Test samples: indices 16000-19999
✓ No overlap: max(train) < min(test)
✓ Chronological: Windows maintain time order
✓ Per-host: Windows grouped by source IP, then chronological
```

---

## Performance Metrics

### Metrics Computed
```python
For each class:
  - Precision = TP / (TP + FP)
  - Recall = TP / (TP + FN)
  - F1 = 2 * (Precision * Recall) / (Precision + Recall)
  - Support = total samples

Aggregated:
  - Macro F1 = mean(F1 for all classes)
  - Weighted F1 = weighted mean(F1)
  - Accuracy = correct predictions / total
  - Attack Recall = recall for all attack classes combined
```

### Inference Latency
```python
Measured: ~0.0168 ms per sample
Device: CPU (Intel/AMD processor)
Batch Size: 32

Throughput: ~59,500 samples/second
```

---

## Reproducibility Checklist

- [ ] Python 3.9+
- [ ] PyTorch installed: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu`
- [ ] scikit-learn installed: `pip install scikit-learn`
- [ ] NumPy/Pandas: `pip install numpy pandas`
- [ ] Data files present: `data/raw/CIC_IDS2018_*.csv` (10 files)
- [ ] Run `data_pipeline.py` first
- [ ] Run `attack_forecasting_diagnostic.py` to confirm root cause
- [ ] Run all three `attack_forecasting_fix_*.py` scripts
- [ ] Compare results in JSON output files
- [ ] Review `ATTACK_FORECASTING_FIX_REPORT.md` for detailed analysis

---

## Expected Runtime

```
Step 1 (Data Pipeline):        ~45 seconds
Step 2 (Diagnosis):             ~2 seconds
Step 3a (Version 1):           ~50 seconds
Step 3b (Version 2):           ~75 seconds
Step 3c (Version 3):           ~40 seconds
Step 4 (Final Summary):         ~1 second

Total Time: ~3-4 minutes on CPU
```

---

## Key Files to Examine

### For Results
- `data/processed/attack_forecasting_fix_final_summary.json` - Complete comparison

### For Implementation
- `engines/attack_forecasting_fix_v3.py` - RECOMMENDED model
- `engines/attack_forecasting_diagnostic.py` - Root cause analysis

### For Details
- `ATTACK_FORECASTING_FIX_REPORT.md` - This guide

---

## Known Limitations

1. **CPU Only**: No CUDA/GPU support currently (slow for large batches)
2. **seq_len=5 Only**: Only tested at sequence length 5 (could improve with longer sequences)
3. **Single Dataset**: Only evaluated on CIC-IDS2018 (generalization unknown)
4. **8 Attack Classes Undetected**: Version 3 only detects 2-3 attack types well
5. **Dataset Design**: CIC-IDS2018 not originally designed for temporal forecasting

---

## Future Improvements

1. Test seq_len ∈ {10, 15, 20, 25}
2. Feature engineering (derived features, aggregations)
3. Multi-dataset training (CIC-IDS2017 + CIC-IDS2018)
4. Alternative architectures (Transformer, Mamba)
5. Hyperparameter tuning (hidden_size, dropout, learning_rate)
6. Analysis of undetected attack classes (why are they invisible?)

---

**Last Updated**: 2026-09-01  
**Tested Python Version**: 3.14  
**Tested PyTorch Version**: 2.x (CPU)
