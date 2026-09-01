import json
import os
import pickle
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import StandardScaler

def compute_correlation_matrix(df: pd.DataFrame, feature_cols: List[str]):
    """Compute Pearson correlation between all features."""
    corr_matrix = df[feature_cols].corr()
    
    # Find highly correlated pairs (> 0.85)
    redundant_pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i + 1, len(corr_matrix.columns)):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) > 0.85:
                redundant_pairs.append({
                    "feature_1": corr_matrix.columns[i],
                    "feature_2": corr_matrix.columns[j],
                    "correlation": float(corr_val),
                    "recommendation": "Consider dropping one of this pair; they convey redundant information"
                })
    
    return corr_matrix, redundant_pairs


def compute_mutual_information(X: np.ndarray, y: np.ndarray, feature_names: List[str]):
    """Compute mutual information between each feature and target label."""
    from sklearn.feature_selection import mutual_info_classif
    
    mi_scores = mutual_info_classif(X, y, random_state=42)
    mi_dict = {name: float(score) for name, score in zip(feature_names, mi_scores)}
    
    # Sort by MI score (descending)
    mi_sorted = dict(sorted(mi_dict.items(), key=lambda x: x[1], reverse=True))
    return mi_sorted


def compute_permutation_importance(model, X_test: np.ndarray, y_test: np.ndarray, feature_names: List[str]):
    """Compute permutation importance on a trained baseline model."""
    perm_result = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42, n_jobs=-1)
    
    perm_dict = {name: float(imp) for name, imp in zip(feature_names, perm_result.importances_mean)}
    perm_sorted = dict(sorted(perm_dict.items(), key=lambda x: x[1], reverse=True))
    
    return perm_sorted, perm_result


def identify_load_bearing_features(corr_matrix, mi_scores, perm_importance, feature_names):
    """Identify features that are:
    - High importance (top 50%)
    - Low redundancy (not in highly-correlated pairs)
    """
    # Get top 50% of features by permutation importance
    perm_sorted = dict(sorted(perm_importance.items(), key=lambda x: x[1], reverse=True))
    top_50_count = max(1, len(feature_names) // 2)
    top_50_features = set(list(perm_sorted.keys())[:top_50_count])
    
    # Build set of features in redundant pairs
    redundant_set = set()
    for i in range(len(corr_matrix.columns)):
        for j in range(i + 1, len(corr_matrix.columns)):
            if abs(corr_matrix.iloc[i, j]) > 0.85:
                # Mark the lower-importance one as redundant
                feat_i, feat_j = corr_matrix.columns[i], corr_matrix.columns[j]
                mi_i = mi_scores.get(feat_i, 0)
                mi_j = mi_scores.get(feat_j, 0)
                lower = feat_i if mi_i <= mi_j else feat_j
                redundant_set.add(lower)
    
    # Load-bearing: high importance + not redundant
    load_bearing = top_50_features - redundant_set
    dropable = (set(feature_names) - top_50_features) | (redundant_set & top_50_features)
    
    return {
        "load_bearing": sorted(list(load_bearing)),
        "dropable": sorted(list(dropable)),
        "load_bearing_count": len(load_bearing),
        "dropable_count": len(dropable),
    }


def train_reduced_model(train_df, test_df, feature_cols_full, reduced_features, label_map, metadata):
    """Train Random Forest on reduced feature set and compare performance."""
    from sklearn.metrics import f1_score
    
    # Full model performance (on test set)
    X_train_full = train_df[feature_cols_full].values
    X_test_full = test_df[feature_cols_full].values
    y_train = train_df['Label'].map(label_map).fillna(0).values.astype(int)
    y_test = test_df['Label'].map(label_map).fillna(0).values.astype(int)
    
    scaler_full = StandardScaler()
    X_train_full_scaled = scaler_full.fit_transform(X_train_full)
    X_test_full_scaled = scaler_full.transform(X_test_full)
    
    clf_full = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf_full.fit(X_train_full_scaled, y_train)
    y_pred_full = clf_full.predict(X_test_full_scaled)
    f1_full = f1_score(y_test, y_pred_full, average='weighted', zero_division=0)
    
    # Reduced model performance
    X_train_reduced = train_df[reduced_features].values
    X_test_reduced = test_df[reduced_features].values
    
    scaler_reduced = StandardScaler()
    X_train_reduced_scaled = scaler_reduced.fit_transform(X_train_reduced)
    X_test_reduced_scaled = scaler_reduced.transform(X_test_reduced)
    
    clf_reduced = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf_reduced.fit(X_train_reduced_scaled, y_train)
    y_pred_reduced = clf_reduced.predict(X_test_reduced_scaled)
    f1_reduced = f1_score(y_test, y_pred_reduced, average='weighted', zero_division=0)
    
    performance_delta = abs(f1_full - f1_reduced)
    delta_percent = (performance_delta / max(f1_full, 0.001)) * 100
    
    return {
        "full_model_f1": float(f1_full),
        "reduced_model_f1": float(f1_reduced),
        "features_dropped": len(feature_cols_full) - len(reduced_features),
        "performance_delta": float(performance_delta),
        "delta_percent": float(delta_percent),
        "verdict": "PASS" if delta_percent < 5.0 else "MARGINAL" if delta_percent < 10.0 else "FAIL"
    }


def render_heatmap_correlation(corr_matrix, processed_dir):
    """Render correlation matrix heatmap."""
    fig, ax = plt.subplots(figsize=(14, 12))
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    sns.heatmap(
        corr_matrix,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        square=True,
        cbar_kws={"label": "Correlation Coefficient"},
        ax=ax,
    )
    ax.set_title("Feature Correlation Matrix (CSE-CIC-IDS2018)", fontsize=14, fontweight="bold")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    output_path = os.path.join(processed_dir, "feature_correlation_heatmap.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"[INFO] Correlation heatmap saved: {output_path}")
    plt.close()


def render_feature_importance(importance_dict, title, processed_dir, filename):
    """Render feature importance bar chart."""
    features = list(importance_dict.keys())
    importances = list(importance_dict.values())
    
    fig, ax = plt.subplots(figsize=(12, 10))
    indices = np.arange(len(features))
    ax.barh(indices, importances, color='steelblue')
    ax.set_yticks(indices)
    ax.set_yticklabels(features)
    ax.set_xlabel("Importance Score", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    
    output_path = os.path.join(processed_dir, filename)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"[INFO] Importance chart saved: {output_path}")
    plt.close()


def mission_g(processed_dir: str = None):
    if processed_dir is None:
        processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    print("="*80)
    print("MISSION G: FEATURE DEPENDENCY & IMPORTANCE ANALYSIS")
    print("="*80)
    
    # Load data
    train_df = pd.read_pickle(os.path.join(processed_dir, "train_windows.pkl"))
    test_df = pd.read_pickle(os.path.join(processed_dir, "test_windows.pkl"))
    
    with open(os.path.join(processed_dir, "metadata.pkl"), "rb") as f:
        metadata = pickle.load(f)
    
    with open(os.path.join(processed_dir, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    
    feature_cols = metadata["feature_cols"]
    label_map = metadata["label_mapping"]
    
    print(f"\n[INFO] Analyzing {len(feature_cols)} features from CSE-CIC-IDS2018")
    
    # 1. Correlation Analysis
    print("\n[1/4] Computing correlation matrix...")
    corr_matrix, redundant_pairs = compute_correlation_matrix(train_df, feature_cols)
    print(f"  - Found {len(redundant_pairs)} highly correlated pairs (> 0.85)")
    if redundant_pairs:
        for pair in redundant_pairs[:3]:
            print(f"    * {pair['feature_1']} <-> {pair['feature_2']}: r={pair['correlation']:.3f}")
    
    render_heatmap_correlation(corr_matrix, processed_dir)
    
    # 2. Mutual Information
    print("\n[2/4] Computing mutual information with target label...")
    X_train = train_df[feature_cols].values
    y_train = train_df['Label'].map(label_map).fillna(0).values.astype(int)
    
    mi_scores = compute_mutual_information(X_train, y_train, feature_cols)
    print(f"  - Top 5 features by MI:")
    for feat, score in list(mi_scores.items())[:5]:
        print(f"    * {feat}: {score:.4f}")
    
    # 3. Permutation Importance
    print("\n[3/4] Computing permutation importance (training baseline model)...")
    X_train_scaled = scaler.fit_transform(X_train)
    X_test = test_df[feature_cols].values
    X_test_scaled = scaler.transform(X_test)
    y_test = test_df['Label'].map(label_map).fillna(0).values.astype(int)
    
    baseline_clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    baseline_clf.fit(X_train_scaled, y_train)
    
    perm_importance_dict, perm_result = compute_permutation_importance(baseline_clf, X_test_scaled, y_test, feature_cols)
    print(f"  - Top 5 features by permutation importance:")
    for feat, score in list(perm_importance_dict.items())[:5]:
        print(f"    * {feat}: {score:.4f}")
    
    render_feature_importance(perm_importance_dict, "Permutation Feature Importance", processed_dir, "feature_permutation_importance.png")
    
    # 4. Combined Ranking
    print("\n[4/4] Combining importance scores...")
    combined_scores = {}
    for feat in feature_cols:
        perm_score = perm_importance_dict.get(feat, 0)
        mi_score = mi_scores.get(feat, 0)
        combined_scores[feat] = (perm_score + mi_score) / 2.0
    
    combined_sorted = dict(sorted(combined_scores.items(), key=lambda x: x[1], reverse=True))
    
    # Identify load-bearing features
    bearing_analysis = identify_load_bearing_features(corr_matrix, mi_scores, perm_importance_dict, feature_cols)
    
    print(f"\n  - Load-bearing features (high importance, low redundancy): {bearing_analysis['load_bearing_count']}")
    print(f"    {bearing_analysis['load_bearing']}")
    print(f"\n  - Dropable features (low importance or redundant): {bearing_analysis['dropable_count']}")
    print(f"    {bearing_analysis['dropable'][:5]}...")  # Print first 5
    
    # Test reduced model
    print("\n[VALIDATION] Retraining with reduced feature set...")
    reduced_features = bearing_analysis['load_bearing']
    if len(reduced_features) < len(feature_cols):
        perf_comparison = train_reduced_model(train_df, test_df, feature_cols, reduced_features, label_map, metadata)
        print(f"  - Full model F1: {perf_comparison['full_model_f1']:.4f}")
        print(f"  - Reduced model F1: {perf_comparison['reduced_model_f1']:.4f}")
        print(f"  - Delta: {perf_comparison['delta_percent']:.2f}%")
        print(f"  - Verdict: {perf_comparison['verdict']}")
        
        if perf_comparison['verdict'] == 'PASS':
            print(f"  [SUCCESS] Reduced feature set maintains performance; {perf_comparison['features_dropped']} features can be safely dropped")
        else:
            print(f"  [CAUTION] Performance degradation is {perf_comparison['delta_percent']:.1f}%; consider keeping more features")
    else:
        perf_comparison = None
        print("  - All features are load-bearing; no reduction possible")
    
    # Compile results
    results = {
        "dataset": "CSE-CIC-IDS2018",
        "total_features": len(feature_cols),
        "correlation_analysis": {
            "redundant_pairs": redundant_pairs,
            "recommendation": "Drop one feature from each pair; they convey redundant information"
        },
        "mutual_information": {
            "top_10": dict(list(mi_scores.items())[:10]),
            "explanation": "MI between each feature and attack label; higher = more predictive"
        },
        "permutation_importance": {
            "top_10": dict(list(perm_importance_dict.items())[:10]),
            "explanation": "Importance computed by permuting feature on held-out test set"
        },
        "feature_ranking": dict(list(combined_sorted.items())[:10]),
        "load_bearing_analysis": bearing_analysis,
        "performance_comparison": perf_comparison,
        "visualizations": [
            "feature_correlation_heatmap.png",
            "feature_permutation_importance.png"
        ]
    }
    
    output_path = os.path.join(processed_dir, "mission_g_feature_importance.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[INFO] Results saved to: {output_path}")
    print("\n" + "="*80)
    return results


if __name__ == "__main__":
    mission_g()
