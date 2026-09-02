#!/usr/bin/env python3
"""
FINAL INTEGRATION MISSION: Dataset Audit & Inventory
=====================================================

Step 1: Inspect real CIC-IDS2018 dataset
- Load all raw CSV files
- Print metadata: filenames, row counts, columns, timestamps
- Class distribution analysis
- NO mock data - REAL dataset only
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import json

def audit_dataset():
    """Comprehensive audit of real CIC-IDS2018 dataset."""
    
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
    print("\n" + "="*80)
    print("CROSSTHREAT FINAL INTEGRATION: REAL DATASET AUDIT")
    print("="*80)
    
    print(f"\nDATA DIRECTORY: {data_dir}")
    
    # List all CSV files
    csv_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.csv')])
    
    print(f"\nFOUND {len(csv_files)} CSV FILES:")
    for f in csv_files:
        fpath = os.path.join(data_dir, f)
        size_mb = os.path.getsize(fpath) / (1024 * 1024)
        print(f"  [OK] {f:<40} ({size_mb:>6.1f} MB)")
    
    # Detailed audit of each file
    audit_data = {}
    total_rows = 0
    all_labels = set()
    
    print("\n" + "="*80)
    print("DETAILED FILE INSPECTION")
    print("="*80)
    
    for fname in csv_files:
        fpath = os.path.join(data_dir, fname)
        print(f"\n[FILE] {fname}")
        print("-" * 80)
        
        try:
            # Load with mixed dtypes (some columns might be text)
            df = pd.read_csv(fpath, low_memory=False)
            
            print(f"  Rows: {len(df):>10}")
            print(f"  Columns: {len(df.columns):>10}")
            total_rows += len(df)
            
            # Column info
            print(f"  Column names ({len(df.columns)}):")
            for i, col in enumerate(df.columns[:5]):
                print(f"    {i+1:2}. {col}")
            if len(df.columns) > 5:
                print(f"    ... and {len(df.columns) - 5} more")
            
            # Date/time analysis (if timestamp column exists)
            date_cols = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower() or 'timestamp' in c.lower()]
            if date_cols:
                print(f"  Time columns found: {date_cols}")
                for col in date_cols:
                    try:
                        print(f"    {col}: {df[col].min()} to {df[col].max()}")
                    except:
                        pass
            
            # Label analysis
            label_cols = [c for c in df.columns if 'label' in c.lower() or 'attack' in c.lower() or 'class' in c.lower()]
            if label_cols:
                print(f"  Label columns: {label_cols}")
                for col in label_cols:
                    unique_labels = df[col].unique()
                    all_labels.update(unique_labels)
                    print(f"    {col}:")
                    for label in sorted(unique_labels):
                        count = (df[col] == label).sum()
                        pct = 100 * count / len(df)
                        print(f"      - {label:<30} {count:>10} ({pct:>6.2f}%)")
            
            # Data types
            print(f"  Data types:")
            dtypes = df.dtypes.value_counts()
            for dtype, count in dtypes.items():
                dtype_str = str(dtype)
                print(f"    - {dtype_str:<20} {count:>3} columns")
            
            # Store metadata
            audit_data[fname] = {
                "rows": len(df),
                "columns": list(df.columns),
                "num_columns": len(df.columns),
                "shape": df.shape
            }
            
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "="*80)
    print("DATASET SUMMARY")
    print("="*80)
    print(f"\nTotal files: {len(csv_files)}")
    print(f"Total rows: {total_rows:,}")
    print(f"Unique attack labels: {len(all_labels)}")
    print(f"Attack types: {sorted(all_labels)}")
    
    print("\n" + "="*80)
    print("DATASET STRUCTURE VERIFICATION")
    print("="*80)
    
    # Verify all files have same columns
    all_columns = [set(audit_data[f]["columns"]) for f in csv_files if f in audit_data]
    if all_columns:
        if all(cols == all_columns[0] for cols in all_columns):
            print("[OK] All files have consistent column structure")
        else:
            print("[WARN] Column structure varies between files:")
            for fname in csv_files:
                if fname in audit_data:
                    print(f"  {fname}: {len(audit_data[fname]['columns'])} columns")
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("""
1. Load all files with consistent schema
2. Create 80/20 chronological train/test split (NO random shuffle)
3. Implement temporal windowing (5, 10, 15 step sequences)
4. Build 6 model architectures
5. Evaluate on test set
6. Generate confusion matrices
7. Perform OOD evaluation on CIC-IDS2017
8. Build dashboard with API backend
    """)
    
    return audit_data, total_rows, all_labels


if __name__ == "__main__":
    audit_data, total_rows, labels = audit_dataset()
    
    # Save audit results
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "dataset_audit.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_rows": total_rows,
            "total_files": len(audit_data),
            "attack_labels": sorted(list(labels)),
            "files": {k: {"rows": v["rows"], "columns": len(v["columns"])} for k, v in audit_data.items()}
        }, f, indent=2)
    
    print(f"\n[OK] Audit results saved to: {output_path}")
