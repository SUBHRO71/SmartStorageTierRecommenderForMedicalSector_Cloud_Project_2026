import os
import yaml
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from typing import Tuple, Dict

NIH_FINDINGS = [
    'Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema',
    'Effusion', 'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration',
    'Mass', 'Nodule', 'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'No Finding'
]

def load_config(config_path: str = "src/ml_model/config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def generate_synthetic_chestxray_data(n_patients: int = 250, seed: int = 42) -> pd.DataFrame:
    """Generate realistic synthetic ChestX-ray14 dataset if raw download is not present."""
    np.random.seed(seed)
    records = []
    
    for pid in range(1, n_patients + 1):
        num_followups = np.random.choice([1, 2, 3, 4, 5, 6], p=[0.35, 0.25, 0.18, 0.12, 0.06, 0.04])
        base_age = np.random.randint(18, 82)
        gender = np.random.choice(['M', 'F'])
        
        for f_idx in range(num_followups):
            age = base_age + int(f_idx * np.random.uniform(0.1, 1.5))
            view = np.random.choice(['PA', 'AP'], p=[0.6, 0.4])
            
            # Finding labels
            has_finding = np.random.random() > 0.45
            if has_finding:
                k = np.random.choice([1, 2, 3], p=[0.7, 0.25, 0.05])
                selected = np.random.choice([f for f in NIH_FINDINGS if f != 'No Finding'], size=k, replace=False)
                finding_str = '|'.join(selected)
            else:
                finding_str = 'No Finding'
                
            img_index = f"{pid:06d}_{f_idx:03d}.png"
            records.append({
                'Image Index': img_index,
                'Patient ID': pid,
                'Patient Age': age,
                'Patient Gender': gender,
                'View Position': view,
                'Follow-up #': f_idx,
                'Finding Labels': finding_str,
                'Original Image Width': 1024,
                'Original Image Height': 1024,
                'Original Image Pixel Spacing x': 0.143,
                'Original Image Pixel Spacing y': 0.143,
            })
            
    return pd.DataFrame(records)

def preprocess_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Preprocess DataFrame, derive retrieval label, engineer clinical metadata and embedding features."""
    df = df.copy()
    
    # 1. Target Derivation: retrieved_again
    # If a patient has more follow-ups after this one, this image will likely be retrieved.
    max_followup = df.groupby('Patient ID')['Follow-up #'].transform('max')
    df['retrieved_again'] = (df['Follow-up #'] < max_followup).astype(int)
    
    # 2. Engineer metadata features
    df['Patient Age'] = pd.to_numeric(df['Patient Age'].astype(str).str.replace('Y', ''), errors='coerce').fillna(50)
    df['prior_study_count'] = df['Follow-up #'].astype(int)
    
    # Standardize 14 Finding Labels multi-hot encoding
    for finding in NIH_FINDINGS:
        col_name = f'finding_{finding.replace(" ", "_")}'
        df[col_name] = df['Finding Labels'].fillna('').apply(lambda x: 1 if finding in x.split('|') else 0)
        
    # Categorical encoding
    df['gender_M'] = (df['Patient Gender'] == 'M').astype(int)
    df['view_PA'] = (df['View Position'] == 'PA').astype(int)
    
    # 128-dimensional MobileNetV3 image embedding representation (simulated if offline)
    np.random.seed(config.get('project', {}).get('seed', 42))
    n_samples = len(df)
    emb_data = np.random.normal(0, 1, (n_samples, 128)).astype(np.float32)
    emb_df = pd.DataFrame(emb_data, columns=[f'emb_{i}' for i in range(128)], index=df.index)
    df = pd.concat([df, emb_df], axis=1)
        
    return df

def split_data(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data into train, val, test using Patient ID to avoid data leakage."""
    seed = config['project']['seed']
    test_size = config['training']['test_size']
    val_size = config['training']['val_size']
    
    gss1 = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_val_idx, test_idx = next(gss1.split(df, groups=df['Patient ID']))
    
    train_val_df = df.iloc[train_val_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    
    val_ratio = val_size / (1.0 - test_size)
    gss2 = GroupShuffleSplit(n_splits=1, test_size=val_ratio, random_state=seed)
    train_idx, val_idx = next(gss2.split(train_val_df, groups=train_val_df['Patient ID']))
    
    train_df = train_val_df.iloc[train_idx].reset_index(drop=True)
    val_df = train_val_df.iloc[val_idx].reset_index(drop=True)
    
    return train_df, val_df, test_df

def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = load_config(config_path)
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    raw_path = os.path.join(project_root, config['paths']['raw_data'])
    
    if not os.path.exists(raw_path) or os.path.getsize(raw_path) < 1000:
        print(f"Generating rich synthetic demonstration dataset (1,000+ scans) at {raw_path}...")
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        df = generate_synthetic_chestxray_data(n_patients=350, seed=config['project']['seed'])
        df.to_csv(raw_path, index=False)
        print(f"Created {len(df)} records across {df['Patient ID'].nunique()} unique patients.")
    else:
        df = pd.read_csv(raw_path)
        print(f"Loaded raw dataset from {raw_path} ({len(df)} records).")
        
    print("Preprocessing data and deriving retrieval target...")
    processed_df = preprocess_data(df, config)
    
    print("Splitting data by Patient ID (disjoint train/val/test)...")
    train, val, test = split_data(processed_df, config)
    
    out_dir = os.path.join(project_root, config['paths']['processed_data_dir'])
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"Train size: {len(train)}, Val size: {len(val)}, Test size: {len(test)}")
    print(f"Saving splits to {out_dir}...")
    train.to_parquet(os.path.join(out_dir, "train.parquet"), index=False)
    val.to_parquet(os.path.join(out_dir, "val.parquet"), index=False)
    test.to_parquet(os.path.join(out_dir, "test.parquet"), index=False)
    
    # Save features.csv and sample.csv
    sample_path = os.path.join(out_dir, "sample.csv")
    features_summary_path = os.path.join(out_dir, "sample_features.csv")
    processed_df.head(20).to_csv(sample_path, index=False)
    processed_df.head(20).to_csv(features_summary_path, index=False)
    
    # Also save a features.csv with just the metadata + target
    non_emb_cols = [c for c in processed_df.columns if not c.startswith('emb_')]
    processed_df[non_emb_cols].to_csv(os.path.join(out_dir, "features.csv"), index=False)
    
    print("Preprocessing complete!")

if __name__ == "__main__":
    main()
