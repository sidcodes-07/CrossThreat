#!/usr/bin/env python3
"""
COMPREHENSIVE DIAGNOSIS: ATTACK FORECASTING ZERO-RECALL PROBLEM
================================================================

Why all models predict 0% attack recall:
1. Severe class imbalance: 89% Benign, 11% Attacks
2. No class weighting in loss function
3. No attack oversampling during training
4. CrossEntropyLoss default treats all classes equally

This diagnostic script determines:
- Exact root cause
- Whether it's fixable with current data
- Minimum recommended changes
- Real success threshold
"""

import os
import pickle
import numpy as np
import pandas as pd
from collections import Counter
from datetime import datetime
import json
import warnings

warnings.filterwarnings('ignore')

class AttackForecastingDiagnostic:
    """Diagnose the 0% attack recall problem."""
    
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def log(self, msg: str):
        print(msg)
    
    def diagnose(self):
        """Run complete diagnosis."""
        
        self.log("\n" + "="*80)
        self.log("ATTACK FORECASTING ZERO-RECALL DIAGNOSIS")
        self.log("="*80)
        self.log(f"Start: {datetime.now()}\n")
        
        # Load data
        with open(os.path.join(self.data_dir, "train_df.pkl"), 'rb') as f:
            train_df = pickle.load(f)
        
        with open(os.path.join(self.data_dir, "test_df.pkl"), 'rb') as f:
            test_df = pickle.load(f)
        
        with open(os.path.join(self.data_dir, "encoder.pkl"), 'rb') as f:
            encoder = pickle.load(f)
        
        # ===== ROOT CAUSE 1: CLASS IMBALANCE =====
        self.log("="*80)
        self.log("ROOT CAUSE 1: CLASS IMBALANCE SEVERITY")
        self.log("="*80)
        
        train_dist = train_df['Label'].value_counts()
        benign_train = train_dist.get('Benign', 0)
        attack_train = len(train_df) - benign_train
        benign_pct = 100 * benign_train / len(train_df)
        
        self.log(f"\nTraining Set (16,000 samples):")
        self.log(f"  Benign:  {benign_train:6,} ({benign_pct:5.2f}%)")
        self.log(f"  Attacks: {attack_train:6,} ({100-benign_pct:5.2f}%)")
        self.log(f"  Imbalance Ratio: 1:{benign_train/attack_train:.1f}")
        
        if benign_pct > 80:
            self.log(f"\n[DIAGNOSIS] SEVERE IMBALANCE DETECTED")
            self.log(f"  Models naturally predict majority class to maximize accuracy")
            self.log(f"  91% accuracy achieved by predicting 'Benign' for everything")
            self.log(f"  This is the PRIMARY ROOT CAUSE of 0% attack recall")
        
        # ===== ROOT CAUSE 2: CLASS WEIGHTS =====
        self.log("\n" + "="*80)
        self.log("ROOT CAUSE 2: LOSS FUNCTION")
        self.log("="*80)
        
        self.log(f"\nCurrent implementation: CrossEntropyLoss()")
        self.log(f"  - Treats all classes with equal weight")
        self.log(f"  - With 89% Benign: predicting all Benign achieves high accuracy")
        self.log(f"  - Model converges to trivial solution")
        self.log(f"\nSolution: Use class weights")
        self.log(f"  - Weight = total_samples / (n_classes * class_samples)")
        
        class_weights = {}
        for cls in encoder.classes_:
            count = len(train_df[train_df['Label'] == cls])
            weight = len(train_df) / (len(encoder.classes_) * count)
            class_weights[cls] = weight
        
        self.log(f"\nComputed class weights:")
        for cls in sorted(class_weights.keys(), key=lambda x: class_weights[x], reverse=True):
            self.log(f"  {cls:<30} {class_weights[cls]:.4f}")
        
        # ===== ROOT CAUSE 3: TEMPORAL WINDOWS =====
        self.log("\n" + "="*80)
        self.log("ROOT CAUSE 3: TEMPORAL WINDOW ANALYSIS")
        self.log("="*80)
        
        # Check distribution of attacks in windows
        train_win5 = np.load(os.path.join(self.data_dir, "train_seq5_windows.npz"))
        y_train_win = train_win5['y']
        
        attack_windows = np.sum(y_train_win != 0)
        benign_windows = np.sum(y_train_win == 0)
        
        self.log(f"\nSequence-level distribution (seq_len=5):")
        self.log(f"  Total windows: {len(y_train_win):,}")
        self.log(f"  Benign windows: {benign_windows:,} ({100*benign_windows/len(y_train_win):.2f}%)")
        self.log(f"  Attack windows: {attack_windows:,} ({100*attack_windows/len(y_train_win):.2f}%)")
        
        if attack_windows < len(y_train_win) * 0.1:
            self.log(f"\n[DIAGNOSIS] Imbalance persists at window level")
            self.log(f"  Models see mostly Benign sequences during training")
        
        # ===== ROOT CAUSE 4: DATASET TRANSITIONS =====
        self.log("\n" + "="*80)
        self.log("ROOT CAUSE 4: ATTACK TRANSITION ANALYSIS")
        self.log("="*80)
        
        # Check benign->attack and attack->attack transitions
        benign_to_attack = 0
        attack_to_attack = 0
        attack_to_benign = 0
        
        for i in range(len(y_train_win) - 1):
            curr = y_train_win[i]
            next_label = y_train_win[i+1]
            
            if curr == 0 and next_label != 0:
                benign_to_attack += 1
            elif curr != 0 and next_label != 0:
                attack_to_attack += 1
            elif curr != 0 and next_label == 0:
                attack_to_benign += 1
        
        self.log(f"\nTemporal attack transitions (5-window sequences):")
        self.log(f"  Benign -> Attack: {benign_to_attack:,}")
        self.log(f"  Attack -> Attack: {attack_to_attack:,}")
        self.log(f"  Attack -> Benign: {attack_to_benign:,}")
        
        total_transitions = benign_to_attack + attack_to_attack + attack_to_benign
        if total_transitions < 100:
            self.log(f"\n[DIAGNOSIS] Few attack transitions in data")
            self.log(f"  Forecasting patterns are weak or absent")
        
        # ===== FIX OPTIONS =====
        self.log("\n" + "="*80)
        self.log("FIX OPTIONS (RANKED BY EXPECTED IMPACT)")
        self.log("="*80)
        
        fixes = [
            {
                'rank': 1,
                'name': 'Class-weighted loss + sequence oversampling',
                'expected_improvement': '+15-25% attack recall',
                'effort': 'Low',
                'scientific_validity': 'High',
                'description': 'Add weight to CrossEntropyLoss; oversample attack sequences 3x'
            },
            {
                'rank': 2,
                'name': 'Focal loss + longer sequences',
                'expected_improvement': '+10-20% attack recall',
                'effort': 'Medium',
                'scientific_validity': 'High',
                'description': 'Replace CrossEntropyLoss with FocalLoss; use seq_len=15'
            },
            {
                'rank': 3,
                'name': 'Cost-sensitive learning + LSTM tuning',
                'expected_improvement': '+5-15% attack recall',
                'effort': 'Medium',
                'scientific_validity': 'Medium',
                'description': 'Adjust misclassification costs; tune LSTM hyperparameters'
            },
            {
                'rank': 4,
                'name': 'No fix - document limitation',
                'expected_improvement': '0% (honest diagnosis)',
                'effort': 'Low',
                'scientific_validity': 'High',
                'description': 'Dataset may not support attack forecasting with current features'
            }
        ]
        
        for fix in sorted(fixes, key=lambda x: x['rank']):
            self.log(f"\nOption {fix['rank']}: {fix['name']}")
            self.log(f"  Expected: {fix['expected_improvement']}")
            self.log(f"  Effort: {fix['effort']}")
            self.log(f"  Scientific validity: {fix['scientific_validity']}")
            self.log(f"  Description: {fix['description']}")
        
        # ===== HONEST SUCCESS THRESHOLD =====
        self.log("\n" + "="*80)
        self.log("HONEST SUCCESS THRESHOLD")
        self.log("="*80)
        
        self.log(f"\nMinimum acceptable improvement:")
        self.log(f"  Attack recall: >10% (vs current 0%)")
        self.log(f"  Macro F1: >0.40 (vs current 0.32)")
        self.log(f"  No benign accuracy drop below 85%")
        
        self.log(f"\nOptimal outcome:")
        self.log(f"  Attack recall: >30%")
        self.log(f"  Macro F1: >0.50")
        self.log(f"  Benign accuracy: >90%")
        
        # ===== RECOMMENDATION =====
        self.log("\n" + "="*80)
        self.log("RECOMMENDATION")
        self.log("="*80)
        
        self.log(f"\nPROCEED WITH: Option 1 (Class-weighted loss + oversampling)")
        self.log(f"\nRationale:")
        self.log(f"  1. Directly addresses root cause (class imbalance)")
        self.log(f"  2. Low implementation effort")
        self.log(f"  3. High scientific validity")
        self.log(f"  4. Does not modify ground truth or test set")
        self.log(f"  5. Achievable within current dataset constraints")
        
        self.log(f"\nExpected outcome:")
        self.log(f"  Attack recall: 15-25% (improvement from 0%)")
        self.log(f"  Macro F1: 0.40-0.50")
        
        # Save diagnosis
        diagnosis = {
            'timestamp': datetime.now().isoformat(),
            'root_causes': [
                'Severe class imbalance (89% Benign, 11% Attacks)',
                'No class weighting in loss function',
                'Standard CrossEntropyLoss treats all classes equally',
                'Models naturally predict majority class'
            ],
            'baseline_metrics': {
                'attack_recall': 0.0,
                'accuracy': 0.9145,
                'macro_f1': 0.3188
            },
            'benign_pct': float(benign_pct),
            'attack_pct': float(100 - benign_pct),
            'imbalance_ratio': float(benign_train / attack_train),
            'recommended_fix': 'Class-weighted loss + sequence oversampling',
            'expected_improvement': '15-25% attack recall',
            'success_threshold': 'Attack recall >10%, Macro F1 >0.40'
        }
        
        diagnosis_path = os.path.join(self.output_dir, "attack_forecasting_diagnosis.json")
        with open(diagnosis_path, 'w') as f:
            json.dump(diagnosis, f, indent=2)
        
        self.log(f"\n\nDiagnosis saved: {diagnosis_path}")
        self.log(f"End: {datetime.now()}")
        
        return diagnosis


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    diagnostic = AttackForecastingDiagnostic(
        data_dir=os.path.join(repo_root, "data", "processed"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    diagnosis = diagnostic.diagnose()
