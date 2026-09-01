#!/usr/bin/env python3
"""
MISSION A: Diagnose Attack Forecasting 0% Accuracy
=====================================================

Step 1: Audit data class distribution
Step 2: Verify target alignment (no future leakage)
Step 3: Identify class imbalance
Step 4: Report findings

Goal: Understand why attack recall is effectively 0%.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def load_data():
    """Load train/test windows from pickle files."""
    train_path = os.path.join(PROCESSED_DIR, "train_windows.pkl")
    test_path = os.path.join(PROCESSED_DIR, "test_windows.pkl")
    
    if not os.path.exists(train_path) or not os.path.exists(test_path):
        raise FileNotFoundError(f"Data files not found in {PROCESSED_DIR}")
    
    train_df = pd.read_pickle(train_path)
    test_df = pd.read_pickle(test_path)
    
    return train_df, test_df


def analyze_class_distribution(df, name="Dataset"):
    """Analyze class distribution: count, percentage, attack samples."""
    print(f"\n{'='*80}")
    print(f"{name} — CLASS DISTRIBUTION")
    print(f"{'='*80}")
    
    total_samples = len(df)
    print(f"[Total Samples] {total_samples}")
    
    class_counts = df['Label'].value_counts()
    benign_count = class_counts.get('Benign', 0)
    attack_count = total_samples - benign_count
    
    print(f"[Benign] {benign_count} ({100*benign_count/total_samples:.1f}%)")
    print(f"[Attack (Total)] {attack_count} ({100*attack_count/total_samples:.1f}%)")
    
    print(f"\n[Per-Attack-Type Distribution]")
    for label, count in class_counts.items():
        if label != 'Benign':
            pct = 100 * count / total_samples
            print(f"  {label:<30} {count:>6} ({pct:>5.2f}%)")
    
    # Check if attacks <5-10% (danger zone for model collapse)
    if attack_count < 0.1 * total_samples:
        print(f"\n[WARNING] Attacks are {100*attack_count/total_samples:.1f}% of samples (<10%).")
        print("         This is a CRITICAL class imbalance that will cause models to collapse to Benign prediction.")
    elif attack_count < 0.15 * total_samples:
        print(f"\n[CAUTION] Attacks are {100*attack_count/total_samples:.1f}% of samples (10-15%).")
        print("         Significant class imbalance — model bias toward Benign expected.")
    else:
        print(f"\n[OK] Attack samples are {100*attack_count/total_samples:.1f}% of data (>15%).")
    
    return class_counts, benign_count, attack_count


def verify_target_alignment(df, name="Dataset"):
    """Verify that sequences have correct target alignment (no future leakage)."""
    print(f"\n{'='*80}")
    print(f"{name} — TARGET ALIGNMENT VERIFICATION")
    print(f"{'='*80}")
    
    # Check if dataframe has the expected columns
    if 'TimeWindow' not in df.columns or 'Label' not in df.columns:
        print("[ERROR] DataFrame missing TimeWindow or Label column. Cannot verify alignment.")
        return False
    
    # Sample a few sequences to inspect
    print(f"\n[Sampling 5 sequences for inspection]")
    
    sample_indices = np.random.choice(len(df), min(5, len(df)), replace=False)
    
    for i, idx in enumerate(sample_indices):
        row = df.iloc[idx]
        print(f"\nSequence {i+1}:")
        print(f"  TimeWindow: {row['TimeWindow']}")
        print(f"  Label: {row['Label']}")
        print(f"  Host (if available): {row.get('Host', 'N/A')}")
    
    # Verify chronological ordering (if Host column exists)
    if 'Host' in df.columns:
        print(f"\n[Checking chronological ordering per host]")
        hosts = df['Host'].unique()
        violations = 0
        
        for host in hosts[:5]:  # Check first 5 hosts
            host_data = df[df['Host'] == host].sort_index()
            if len(host_data) > 1:
                time_diffs = np.diff(host_data['TimeWindow'].values)
                if np.any(time_diffs < 0):
                    violations += 1
                    print(f"  [VIOLATION] Host {host} has non-monotonic timestamps!")
        
        if violations == 0:
            print(f"  [OK] Chronological ordering verified for sampled hosts.")
        else:
            print(f"  [WARNING] Found {violations} hosts with timestamp violations.")
    
    return True


def count_attack_transitions(train_df, test_df):
    """Count temporal transitions: benign→attack, attack→attack, etc."""
    print(f"\n{'='*80}")
    print("ATTACK TRANSITION ANALYSIS")
    print(f"{'='*80}")
    
    if 'Host' not in train_df.columns:
        print("[SKIP] Host column not found — cannot analyze transitions.")
        return
    
    def analyze_transitions(df, name):
        print(f"\n{name}:")
        
        benign_to_attack = 0
        attack_to_attack = 0
        attack_to_benign = 0
        benign_to_benign = 0
        
        for host in df['Host'].unique():
            host_data = df[df['Host'] == host].sort_values('TimeWindow')
            labels = host_data['Label'].values
            
            for i in range(len(labels) - 1):
                current = labels[i]
                next_label = labels[i + 1]
                
                is_current_benign = current == 'Benign'
                is_next_benign = next_label == 'Benign'
                
                if is_current_benign and not is_next_benign:
                    benign_to_attack += 1
                elif not is_current_benign and not is_next_benign:
                    attack_to_attack += 1
                elif not is_current_benign and is_next_benign:
                    attack_to_benign += 1
                elif is_current_benign and is_next_benign:
                    benign_to_benign += 1
        
        total_transitions = benign_to_attack + attack_to_attack + attack_to_benign + benign_to_benign
        
        print(f"  Total Transitions: {total_transitions}")
        print(f"    Benign -> Benign:   {benign_to_benign:6} ({100*benign_to_benign/max(1,total_transitions):>5.1f}%)")
        print(f"    Benign -> Attack:   {benign_to_attack:6} ({100*benign_to_attack/max(1,total_transitions):>5.1f}%) [FORECASTING TARGET]")
        print(f"    Attack -> Benign:   {attack_to_benign:6} ({100*attack_to_benign/max(1,total_transitions):>5.1f}%)")
        print(f"    Attack -> Attack:   {attack_to_attack:6} ({100*attack_to_attack/max(1,total_transitions):>5.1f}%)")
    
    analyze_transitions(train_df, "TRAIN SET")
    analyze_transitions(test_df, "TEST SET")


def check_unseen_classes(train_df, test_df):
    """Check if test set contains attack classes not in training."""
    print(f"\n{'='*80}")
    print("UNSEEN ATTACK CLASS DETECTION")
    print(f"{'='*80}")
    
    train_classes = set(train_df['Label'].unique())
    test_classes = set(test_df['Label'].unique())
    
    unseen = test_classes - train_classes
    seen = test_classes & train_classes
    
    print(f"\nTrain Classes: {len(train_classes)}")
    for c in sorted(train_classes):
        print(f"  - {c}")
    
    print(f"\nTest Classes: {len(test_classes)}")
    for c in sorted(test_classes):
        marker = "[UNSEEN]" if c in unseen else "[SEEN]"
        print(f"  - {c} {marker}")
    
    if unseen:
        print(f"\n[CRITICAL] Test set contains {len(unseen)} UNSEEN attack classes not in training!")
        print("           This is a DATASET LIMITATION, not a model failure.")
        print("           Unseen classes:")
        for c in sorted(unseen):
            test_count = (test_df['Label'] == c).sum()
            print(f"             - {c}: {test_count} samples")
        return True  # Return True to indicate unseen classes exist
    else:
        print(f"\n[OK] All test classes present in training data.")
        return False


def main():
    """Run complete audit."""
    print("\n" + "="*80)
    print("MISSION A: ATTACK FORECASTING DIAGNOSIS")
    print("="*80)
    
    try:
        train_df, test_df = load_data()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return
    
    # STEP 1: Analyze class distribution
    train_class_dist, train_benign, train_attacks = analyze_class_distribution(train_df, "TRAIN SET")
    test_class_dist, test_benign, test_attacks = analyze_class_distribution(test_df, "TEST SET")
    
    # STEP 2: Verify target alignment
    verify_target_alignment(train_df, "TRAIN SET")
    verify_target_alignment(test_df, "TEST SET")
    
    # STEP 3: Analyze attack transitions
    count_attack_transitions(train_df, test_df)
    
    # STEP 4: Check for unseen classes
    has_unseen = check_unseen_classes(train_df, test_df)
    
    # STEP 5: Generate summary report
    print(f"\n{'='*80}")
    print("SUMMARY & DIAGNOSIS")
    print(f"{'='*80}")
    
    train_attack_pct = 100 * train_attacks / len(train_df)
    test_attack_pct = 100 * test_attacks / len(test_df)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "dataset_analysis": {
            "train": {
                "total_samples": len(train_df),
                "benign_samples": int(train_benign),
                "benign_pct": float(train_attack_pct),
                "attack_samples": int(train_attacks),
                "attack_pct": float(train_attack_pct),
                "class_distribution": {k: int(v) for k, v in train_class_dist.items()}
            },
            "test": {
                "total_samples": len(test_df),
                "benign_samples": int(test_benign),
                "benign_pct": float(test_attack_pct),
                "attack_samples": int(test_attacks),
                "attack_pct": float(test_attack_pct),
                "class_distribution": {k: int(v) for k, v in test_class_dist.items()}
            }
        },
        "issues": []
    }
    
    # Identify issues
    if train_attack_pct < 10:
        report["issues"].append({
            "severity": "CRITICAL",
            "issue": "SEVERE CLASS IMBALANCE IN TRAINING",
            "description": f"Only {train_attack_pct:.1f}% of training data is attacks. Model will collapse to Benign prediction.",
            "mitigation": "Implement class weighting, oversampling, or cost-sensitive loss function."
        })
    
    if has_unseen:
        report["issues"].append({
            "severity": "CRITICAL",
            "issue": "UNSEEN ATTACK CLASSES IN TEST SET",
            "description": "Test set contains attack types not present in training. Model cannot predict unseen classes.",
            "mitigation": "Use time-based split where test attacks differ from train (expected), but accept this limits generalization."
        })
    
    if test_attack_pct < train_attack_pct:
        report["issues"].append({
            "severity": "HIGH",
            "issue": "TEST SET HAS FEWER ATTACKS THAN TRAINING",
            "description": f"Train: {train_attack_pct:.1f}% attacks, Test: {test_attack_pct:.1f}% attacks. Different data distribution.",
            "mitigation": "Evaluate per-class metrics (recall/precision/F1) separately, not just overall accuracy."
        })
    
    print(json.dumps(report, indent=2))
    
    # Save report
    output_path = os.path.join(PROCESSED_DIR, "mission_a_audit_report.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n[INFO] Audit report saved to: {output_path}")
    
    # Print key recommendations
    print(f"\n{'='*80}")
    print("NEXT STEPS (MISSION A RESOLUTION)")
    print(f"{'='*80}")
    
    if train_attack_pct < 10:
        print("\n1. [PRIORITY] Fix class imbalance:")
        print("   - Option A: Use WeightedRandomSampler for training (increase attack weight)")
        print("   - Option B: Use FocalLoss instead of CrossEntropyLoss")
        print("   - Option C: Oversample attack sequences (SMOTE or simple duplication)")
        print("   - Test ONLY on unchanged test set (don't modify ground truth)")
    
    if has_unseen:
        print("\n2. [ACCEPT] Test set has unseen attacks:")
        print("   - This is EXPECTED in time-based split (realistic scenario)")
        print("   - Do NOT fake high accuracy on unseen classes")
        print("   - Instead, measure 'generalization to new attacks' separately")
    
    print("\n3. [ALWAYS] Report per-class metrics:")
    print("   - Overall accuracy is misleading with class imbalance")
    print("   - Report: Precision, Recall, F1 per class")
    print("   - Report: Macro F1 and Weighted F1")
    print("   - Emphasize Attack Recall as primary metric")
    
    print("\nSee mission_a_audit_report.json for full details.")


if __name__ == "__main__":
    main()
