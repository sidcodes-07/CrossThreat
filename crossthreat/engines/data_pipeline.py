#!/usr/bin/env python3
"""Build CrossThreat artifacts from the official NF-UNSW-NB15-v3 flow dataset."""

import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
import pickle
import json
from datetime import datetime
from typing import Tuple, Dict, List
import warnings

warnings.filterwarnings('ignore')

class DataPipeline:
    """Unified data pipeline for CrossThreat."""
    
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.audit_log = []
    
    def log(self, msg: str):
        """Log to both stdout and audit log."""
        print(msg)
        self.audit_log.append(msg)
    
    def load_real_dataset(self) -> pd.DataFrame:
        """Load and normalize the official NF-UNSW-NB15-v3 flow export."""
        
        self.log("\n" + "="*80)
        self.log("LOADING REAL NF-UNSW-NB15-v3 DATASET")
        self.log("="*80)
        
        self.log(f"Data directory: {self.data_dir}")
        fpath = os.path.join(self.data_dir, "external", "NF-UNSW-NB15-v3.csv")
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Official dataset not found: {fpath}")

        dataset = pd.read_csv(fpath, low_memory=False)
        self.log(f"[OK] {os.path.basename(fpath)} loaded: {len(dataset):,} rows")
        self.log(f"Columns ({len(dataset.columns)}): {dataset.columns.tolist()}")
        self.log(f"Label distribution: {dataset['Attack'].value_counts(dropna=False).to_dict()}")

        dataset["TimeWindow"] = pd.to_datetime(
            dataset["FLOW_START_MILLISECONDS"], unit="ms", errors="coerce"
        )
        dataset = dataset.dropna(subset=["TimeWindow", "IPV4_SRC_ADDR", "IPV4_DST_ADDR"])
        dataset["Host"] = dataset["IPV4_SRC_ADDR"].astype(str)
        dataset["Label"] = dataset["Attack"].fillna("Unknown").astype(str)
        dataset["Protocol"] = dataset["PROTOCOL"].astype(str)
        dataset = dataset.sort_values(["TimeWindow", "Host"]).reset_index(drop=True)
        self.log(
            f"Flow time range: {dataset['TimeWindow'].min().isoformat()} to "
            f"{dataset['TimeWindow'].max().isoformat()}"
        )
        return dataset
    
    def load_ood_dataset(self) -> pd.DataFrame:
        """NF-UNSW-NB15-v3 is the sole supported dataset; there is no OOD set."""
        self.log("No OOD dataset configured: NF-UNSW-NB15-v3 is the official source.")
        return None
    
    def analyze_columns(self, df: pd.DataFrame) -> Dict:
        """Analyze dataset columns and identify feature/label columns."""
        
        self.log("\n" + "="*80)
        self.log("COLUMN ANALYSIS")
        self.log("="*80)
        
        cols = df.columns.tolist()
        self.log(f"\nColumns ({len(cols)}):")
        for i, col in enumerate(cols, 1):
            print(f"  {i:2}. {col}")
        
        label_cols = ["Label"]
        timestamp_cols = ["TimeWindow"]
        ip_cols = ["Host", "IPV4_SRC_ADDR", "IPV4_DST_ADDR"]
        feature_cols = [
            "L4_SRC_PORT", "L4_DST_PORT", "PROTOCOL", "L7_PROTO",
            "IN_BYTES", "IN_PKTS", "OUT_BYTES", "OUT_PKTS",
            "TCP_FLAGS", "FLOW_DURATION_MILLISECONDS", "DURATION_IN",
            "DURATION_OUT", "MIN_TTL", "MAX_TTL", "LONGEST_FLOW_PKT",
            "SHORTEST_FLOW_PKT",
        ]
        missing = [column for column in feature_cols if column not in df.columns]
        if missing:
            raise ValueError(f"NF-UNSW-NB15-v3 is missing required numeric features: {missing}")
        self.log(f"\nIdentified columns:")
        self.log(f"  Label columns: {label_cols}")
        self.log(f"  Timestamp columns: {timestamp_cols}")
        self.log(f"  IP/Host columns: {ip_cols}")
        self.log(f"  Feature columns (numeric): {len(feature_cols)} features")
        self.log(f"    {feature_cols}")
        
        # Analyze class distribution
        label_col = "Label"
        self.log(f"\nClass distribution ({label_col}):")
        for label, count in df[label_col].value_counts().items():
            self.log(f"  {label:<30} {count:>8} ({100 * count / len(df):>6.2f}%)")
        
        return {
            "label_col": label_col,
            "timestamp_col": "TimeWindow",
            "feature_cols": feature_cols,
            "ip_cols": ip_cols,
            "all_cols": cols
        }
    
    def create_chronological_split(self, df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create 80/20 train/test split chronologically (NO random shuffle).
        
        Since temporal data should not be randomly split, we split by index.
        """
        
        self.log("\n" + "="*80)
        self.log("CREATING CHRONOLOGICAL 80/20 SPLIT")
        self.log("="*80)
        
        split_idx = int(len(df) * (1 - test_size))
        
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
        
        self.log(f"\nTotal samples: {len(df):,}")
        self.log(f"Train samples: {len(train_df):,} ({100*len(train_df)/len(df):.1f}%)")
        self.log(f"Test samples:  {len(test_df):,} ({100*len(test_df)/len(df):.1f}%)")
        
        # Verify no overlap
        self.log("\nSplit verification:")
        self.log(f"  Train index range: {train_df.index.min()} to {train_df.index.max()}")
        self.log(f"  Test index range:  {test_df.index.min()} to {test_df.index.max()}")
        self.log(f"  No overlap: {train_df.index.max() < test_df.index.min()}")
        
        return train_df, test_df
    
    def create_temporal_windows(self, df: pd.DataFrame, feature_cols: List[str], 
                                label_col: str, seq_lengths: List[int] = [5, 10, 15]) -> Dict:
        """
        Create temporal windows for forecasting.
        
        INPUT: [t-seq_len, ..., t-2, t-1]
        TARGET: label(t)
        
        Ensures no future features/labels in input.
        """
        
        self.log("\n" + "="*80)
        self.log("CREATING TEMPORAL WINDOWS")
        self.log("="*80)
        
        results = {}
        
        for seq_len in seq_lengths:
            self.log(f"\nSequence length: {seq_len}")
            
            X_sequences = []
            y_targets = []
            
            # Group by source host and never allow windows to cross host boundaries.
            if 'Host' in df.columns:
                groups = df.groupby('Host', sort=False)
                self.log(f"  Grouping by Host: {len(groups)} hosts")
            else:
                groups = [("all", df)]
                self.log(f"  No host grouping available")
            
            for group_key, group_df in groups:
                if len(group_df) < seq_len + 1:
                    continue
                
                # Sort by timestamp if available
                if 'TimeWindow' in df.columns:
                    group_df = group_df.sort_values('TimeWindow')
                
                features = group_df[feature_cols].values.astype(np.float32)
                labels = group_df[label_col].values
                
                # Create windows
                for i in range(len(features) - seq_len):
                    X_seq = features[i:i+seq_len]  # Past seq_len steps
                    y = labels[i+seq_len]           # Target at step i+seq_len
                    
                    X_sequences.append(X_seq)
                    y_targets.append(y)
            
            X = np.array(X_sequences)
            y = np.array(y_targets)
            
            self.log(f"  Windows created: {len(X)}")
            self.log(f"  Input shape: {X.shape}")
            self.log(f"  Target shape: {y.shape}")
            
            results[seq_len] = {"X": X, "y": y}
        
        return results
    
    def preprocess_features(self, train_df: pd.DataFrame, test_df: pd.DataFrame, 
                           feature_cols: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, StandardScaler]:
        """
        Preprocess features: handle missing values, normalize.
        
        CRITICAL: Fit scaler ONLY on training data.
        """
        
        self.log("\n" + "="*80)
        self.log("PREPROCESSING FEATURES")
        self.log("="*80)
        
        self.log(f"\nFeatures to preprocess: {len(feature_cols)}")
        
        # Handle infinity values first
        self.log(f"\nReplacing infinity values with NaN:")
        for df_name, df in [("train", train_df), ("test", test_df)]:
            inf_count = (np.isinf(df[feature_cols])).sum().sum()
            if inf_count > 0:
                self.log(f"  {df_name}: {inf_count} infinity values")
                df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)
            else:
                self.log(f"  {df_name}: None")
        
        # Handle missing values
        self.log(f"\nMissing values (train):")
        missing_train = train_df[feature_cols].isnull().sum()
        if missing_train.sum() > 0:
            self.log(f"  {missing_train[missing_train > 0].to_dict()}")
            train_df[feature_cols] = train_df[feature_cols].fillna(train_df[feature_cols].mean())
        else:
            self.log(f"  None")
        
        self.log(f"Missing values (test):")
        missing_test = test_df[feature_cols].isnull().sum()
        if missing_test.sum() > 0:
            self.log(f"  {missing_test[missing_test > 0].to_dict()}")
            test_df[feature_cols] = test_df[feature_cols].fillna(test_df[feature_cols].mean())
        else:
            self.log(f"  None")
        
        # Fit scaler ONLY on training data
        self.log(f"\nNormalizing features (fit on TRAINING data only):")
        scaler = StandardScaler()
        train_scaled = scaler.fit_transform(train_df[feature_cols])
        test_scaled = scaler.transform(test_df[feature_cols])
        
        train_df_processed = train_df.copy()
        test_df_processed = test_df.copy()
        
        train_df_processed[feature_cols] = train_scaled
        test_df_processed[feature_cols] = test_scaled
        
        self.log(f"  Scaler fit on {len(train_df)} training samples")
        self.log(f"  Applied to {len(test_df)} test samples")
        
        return train_df_processed, test_df_processed, scaler
    
    def encode_labels(self, train_df: pd.DataFrame, test_df: pd.DataFrame, 
                     ood_df: pd.DataFrame, label_col: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, LabelEncoder, Dict]:
        """
        Encode categorical labels to integers.
        
        Fit encoder on TRAINING data only.
        """
        
        self.log("\n" + "="*80)
        self.log("ENCODING LABELS")
        self.log("="*80)
        
        encoder = LabelEncoder()
        
        # Fit on training labels only
        train_labels = train_df[label_col].unique()
        encoder.fit(train_labels)
        
        self.log(f"\nLabel encoder fit on {len(train_labels)} classes from training data:")
        for i, cls in enumerate(encoder.classes_):
            self.log(f"  {i}: {cls}")
        
        # Encode all datasets
        train_df[f"{label_col}_encoded"] = encoder.transform(train_df[label_col])
        test_df[f"{label_col}_encoded"] = test_df[label_col].map(
            lambda x: encoder.transform([x])[0] if x in encoder.classes_ else -1
        )
        
        if ood_df is not None:
            ood_df[f"{label_col}_encoded"] = ood_df[label_col].map(
                lambda x: encoder.transform([x])[0] if x in encoder.classes_ else -1
            )
        
        self.log(f"\nClass distribution after encoding:")
        self.log(f"  Train: {len(train_df[f'{label_col}_encoded'].unique())} classes")
        self.log(f"  Test: {len(test_df[f'{label_col}_encoded'].unique())} classes")
        if ood_df is not None:
            self.log(f"  OOD: {len(ood_df[f'{label_col}_encoded'].unique())} classes")
        
        # Create reverse mapping
        label_map = {i: cls for i, cls in enumerate(encoder.classes_)}
        
        return train_df, test_df, ood_df, encoder, label_map
    
    def verify_no_leakage(self, train_df: pd.DataFrame, test_df: pd.DataFrame, 
                         feature_cols: List[str], label_col: str) -> Dict:
        """
        Verify no data leakage between train and test sets.
        """
        
        self.log("\n" + "="*80)
        self.log("LEAKAGE VERIFICATION")
        self.log("="*80)
        
        results = {
            "no_index_overlap": train_df.index.max() < test_df.index.min(),
            "train_mean": float(train_df[feature_cols].mean().mean()),
            "test_mean": float(test_df[feature_cols].mean().mean()),
            "train_test_label_overlap": len(set(train_df[label_col]) & set(test_df[label_col]))
        }
        
        self.log(f"Index overlap: {not results['no_index_overlap']}")
        self.log(f"Train feature mean: {results['train_mean']:.4f}")
        self.log(f"Test feature mean: {results['test_mean']:.4f}")
        self.log(f"Label class overlap: {results['train_test_label_overlap']} classes")
        
        if results['no_index_overlap']:
            self.log("[OK] No index overlap detected")
        else:
            self.log("[WARNING] Index overlap detected!")
        
        return results
    
    def build_pipeline(self) -> Dict:
        """Execute complete data pipeline."""
        
        self.log("\n" + "="*80)
        self.log("CROSSTHREAT DATA PIPELINE - REAL NF-UNSW-NB15-v3")
        self.log("="*80)
        self.log(f"Start time: {datetime.now()}")
        
        # Step 1: Load datasets
        official_df = self.load_real_dataset()
        ood_df = self.load_ood_dataset()
        
        # Step 2: Analyze columns
        col_info = self.analyze_columns(official_df)
        
        # Step 3: Chronological split (80/20, NO shuffle)
        train_df, test_df = self.create_chronological_split(official_df)
        
        # Step 4: Preprocess features
        train_df, test_df, scaler = self.preprocess_features(
            train_df, test_df, col_info['feature_cols']
        )
        
        # Step 5: Encode labels
        train_df, test_df, ood_df, encoder, label_map = self.encode_labels(
            train_df, test_df, ood_df, col_info['label_col']
        )
        
        # Step 6: Create temporal windows
        train_windows = self.create_temporal_windows(
            train_df, col_info['feature_cols'], f"{col_info['label_col']}_encoded", 
            seq_lengths=[5, 10, 15]
        )
        test_windows = self.create_temporal_windows(
            test_df, col_info['feature_cols'], f"{col_info['label_col']}_encoded",
            seq_lengths=[5, 10, 15]
        )
        
        if ood_df is not None:
            ood_windows = self.create_temporal_windows(
                ood_df, col_info['feature_cols'], f"{col_info['label_col']}_encoded",
                seq_lengths=[5, 10, 15]
            )
        else:
            ood_windows = None
        
        # Step 7: Verify no leakage
        leakage_results = self.verify_no_leakage(
            train_df, test_df, col_info['feature_cols'], col_info['label_col']
        )
        
        # Save all artifacts
        self.log("\n" + "="*80)
        self.log("SAVING ARTIFACTS")
        self.log("="*80)
        
        artifacts = {
            "train_df": train_df,
            "test_df": test_df,
            "ood_df": ood_df,
            "scaler": scaler,
            "encoder": encoder,
            "label_map": label_map,
            "train_windows": train_windows,
            "test_windows": test_windows,
            "ood_windows": ood_windows,
            "column_info": col_info,
            "leakage_results": leakage_results
        }
        
        # Save DataFrames
        for key in ["train_df", "test_df", "ood_df"]:
            if artifacts[key] is not None:
                fpath = os.path.join(self.output_dir, f"{key}.pkl")
                with open(fpath, 'wb') as f:
                    pickle.dump(artifacts[key], f)
                self.log(f"[OK] {key}.pkl")

        # Replay and legacy trainers consume the chronological window tables.
        for key, frame in [("train_windows", train_df), ("test_windows", test_df)]:
            frame.to_pickle(os.path.join(self.output_dir, f"{key}.pkl"))
            self.log(f"[OK] {key}.pkl")
        
        # Save scaler and encoder
        for key in ["scaler", "encoder", "label_map"]:
            fpath = os.path.join(self.output_dir, f"{key}.pkl")
            with open(fpath, 'wb') as f:
                pickle.dump(artifacts[key], f)
            self.log(f"[OK] {key}.pkl")
        
        # Save windows as NPZ
        for split_name, windows_dict in [("train", train_windows), ("test", test_windows), ("ood", ood_windows)]:
            if windows_dict is None:
                continue
            for seq_len, data in windows_dict.items():
                fpath = os.path.join(self.output_dir, f"{split_name}_seq{seq_len}_windows.npz")
                np.savez_compressed(fpath, X=data["X"], y=data["y"])
                self.log(f"[OK] {split_name}_seq{seq_len}_windows.npz")
        
        # Save metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "dataset": "NF-UNSW-NB15-v3",
            "dataset_path": os.path.join(self.data_dir, "external", "NF-UNSW-NB15-v3.csv"),
            "total_rows": len(official_df),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "ood_rows": 0,
            "feature_cols": col_info['feature_cols'],
            "label_col": col_info['label_col'],
            "num_features": len(col_info['feature_cols']),
            "num_classes": len(encoder.classes_),
            "classes": list(encoder.classes_),
            "label_map": label_map,
            "label_mapping": label_map,
            "leakage_verified": leakage_results['no_index_overlap']
        }
        
        metadata_path = os.path.join(self.output_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        self.log(f"[OK] metadata.json")
        with open(os.path.join(self.output_dir, "metadata.pkl"), "wb") as f:
            pickle.dump(
                {
                    "feature_cols": col_info["feature_cols"],
                    "label_mapping": label_map,
                    "dataset": "NF-UNSW-NB15-v3",
                    "label_col": col_info["label_col"],
                    "timestamp_col": col_info["timestamp_col"],
                    "host_col": "Host",
                },
                f,
            )
        self.log("[OK] metadata.pkl")
        
        # Save audit log
        audit_path = os.path.join(self.output_dir, "pipeline_audit.log")
        with open(audit_path, 'w') as f:
            f.write("\n".join(self.audit_log))
        self.log(f"[OK] pipeline_audit.log")
        
        self.log(f"\nEnd time: {datetime.now()}")
        self.log("\n" + "="*80)
        self.log("DATA PIPELINE COMPLETE")
        self.log("="*80)
        
        return artifacts


if __name__ == "__main__":
    # Use absolute paths for robustness
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pipeline = DataPipeline(
        data_dir=os.path.join(repo_root, "data"),
        output_dir=os.path.join(repo_root, "data", "processed")
    )
    
    artifacts = pipeline.build_pipeline()
    
    print("\n" + "="*80)
    print("PIPELINE STATUS SUMMARY")
    print("="*80)
    print(f"\nTrain samples: {len(artifacts['train_df']):,}")
    print(f"Test samples: {len(artifacts['test_df']):,}")
    print(f"OOD samples: {len(artifacts['ood_df']) if artifacts['ood_df'] is not None else 0:,}")
    print(f"Features: {len(artifacts['column_info']['feature_cols'])}")
    print(f"Classes: {len(artifacts['encoder'].classes_)}")
    print(f"No leakage: {artifacts['leakage_results']['no_index_overlap']}")
