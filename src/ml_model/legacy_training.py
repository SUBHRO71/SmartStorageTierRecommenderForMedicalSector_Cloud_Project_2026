import os
import yaml
import json
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import roc_auc_score, brier_score_loss, roc_curve, precision_recall_curve
from sklearn.calibration import calibration_curve

# Local imports
from preprocessing import load_config
from model import GradientBoostedTierModel

def plot_calibration_curve(y_true, y_prob, save_path):
    plt.figure(figsize=(8, 8))
    ax1 = plt.subplot2grid((3, 1), (0, 0), rowspan=2)
    ax2 = plt.subplot2grid((3, 1), (2, 0))

    ax1.plot([0, 1], [0, 1], "k:", label="Perfectly calibrated")
    
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10)
    
    ax1.plot(prob_pred, prob_true, "s-", label="XGBoost + Isotonic")
    ax1.set_ylabel("Fraction of positives")
    ax1.set_ylim([-0.05, 1.05])
    ax1.legend(loc="lower right")
    ax1.set_title("Calibration Curve")

    ax2.hist(y_prob, range=(0, 1), bins=10, histtype="step", lw=2)
    ax2.set_xlabel("Mean predicted value")
    ax2.set_ylabel("Count")
    
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()

def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = load_config(config_path)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    
    data_dir = os.path.join(project_root, config['paths']['processed_data_dir'])
    train_df = pd.read_parquet(os.path.join(data_dir, "train.parquet"))
    val_df = pd.read_parquet(os.path.join(data_dir, "val.parquet"))
    test_df = pd.read_parquet(os.path.join(data_dir, "test.parquet"))
    
    target_col = config['features']['target']
    # Select features (excluding target and identifiers / raw string columns)
    drop_cols = [target_col, 'Image Index', 'Patient ID', 'Finding Labels', 'Patient Gender', 'View Position']
    
    X_train = train_df.drop(columns=[c for c in drop_cols if c in train_df.columns])
    y_train = train_df[target_col]
    
    X_val = val_df.drop(columns=[c for c in drop_cols if c in val_df.columns])
    y_val = val_df[target_col]
    
    X_test = test_df.drop(columns=[c for c in drop_cols if c in test_df.columns])
    y_test = test_df[target_col]
    
    # Train
    print("Training model...")
    model = GradientBoostedTierModel(config)
    model.fit(X_train, y_train, X_val, y_val)
    
    # Evaluate
    print("Evaluating on test set...")
    y_prob = model.predict_proba(X_test)[:, 1]
    
    auc = roc_auc_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)
    
    metrics = {
        "roc_auc": float(auc),
        "brier_score": float(brier),
        "train_samples": len(X_train),
        "test_samples": len(X_test)
    }
    
    print(f"Test AUC: {auc:.4f}")
    print(f"Test Brier Score: {brier:.4f}")
    
    # Save artifacts
    timestamp = int(time.time())
    model_dir = os.path.join(project_root, config['paths']['model_dir'])
    results_dir = os.path.join(project_root, config['paths']['results_dir'], str(timestamp))
    
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, "latest_model.pkl")
    model.save(model_path)
    print(f"Model saved to {model_path}")
    
    with open(os.path.join(results_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=4)
        
    # Calibration Curve Plot
    plot_calibration_curve(y_test, y_prob, os.path.join(results_dir, "calibration_curve.png"))
    
    # ROC Curve Plot
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.3f})', color='#1F3B63', lw=2)
    plt.plot([0, 1], [0, 1], 'k--', lw=1)
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Stage 1 Retrieval Probability ROC Curve')
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, "roc_curve.png"))
    plt.close()
    
    # Feature Importances
    importances = model.get_feature_importances()
    pd.Series(importances).sort_values(ascending=False).to_csv(os.path.join(results_dir, "feature_importances.csv"))
    
    # Also save copy to results/ for easy access by evaluate.py / reports
    with open(os.path.join(project_root, "results", "latest_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=4)
        
    print(f"Experiment artifacts saved to {results_dir}")

if __name__ == "__main__":
    main()
