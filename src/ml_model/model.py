import os
import pickle
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from typing import Dict, Any, List

class GradientBoostedTierModel:
    """Wrapper for Stage 1 model to predict P(retrieved again) with calibration."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.seed = config['project']['seed']
        params = config['training']['model_params']
        
        self.base_estimator = XGBClassifier(
            objective=params['objective'],
            eval_metric=params['eval_metric'],
            max_depth=params['max_depth'],
            learning_rate=params['learning_rate'],
            n_estimators=params['n_estimators'],
            random_state=self.seed
        )
        
        # Scikit-learn calibration: use FrozenEstimator if available, or cv='prefit'
        self.calibration_method = config['training'].get('calibration_method', 'isotonic')
        self.model = None
        self.feature_names_ = None
        self.is_fitted = False

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series):
        """Fit base model on train, then calibrate on validation set."""
        self.feature_names_ = X_train.columns.tolist()
        
        print("Fitting base XGBoost model...")
        self.base_estimator.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        print("Calibrating probabilities...")
        try:
            from sklearn.frozen import FrozenEstimator
            frozen_estimator = FrozenEstimator(self.base_estimator)
            self.model = CalibratedClassifierCV(
                estimator=frozen_estimator,
                method=self.calibration_method
            )
        except (ImportError, ModuleNotFoundError):
            self.model = CalibratedClassifierCV(
                estimator=self.base_estimator,
                method=self.calibration_method,
                cv='prefit'
            )
        self.model.fit(X_val, y_val)
        self.is_fitted = True

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities. Returns array of shape (n_samples, 2)."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")
        
        # Ensure column order
        X = X[self.feature_names_]
        return self.model.predict_proba(X)
        
    def get_feature_importances(self) -> Dict[str, float]:
        """Extract feature importances from the base estimator."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted to get importances.")
        
        importances = self.base_estimator.feature_importances_
        return {feat: float(imp) for feat, imp in zip(self.feature_names_, importances)}

    def save(self, path: str):
        """Serialize the model."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'base_estimator': self.base_estimator,
                'feature_names_': self.feature_names_,
                'is_fitted': self.is_fitted
            }, f)
            
    def load(self, path: str):
        """Deserialize the model."""
        with open(path, 'rb') as f:
            state = pickle.load(f)
            self.model = state['model']
            self.base_estimator = state['base_estimator']
            self.feature_names_ = state['feature_names_']
            self.is_fitted = state['is_fitted']
