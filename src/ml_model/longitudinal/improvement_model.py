"""CPU XGBoost with native missingness, optional cohort specialization."""
import numpy as np
from sklearn.impute import SimpleImputer
from xgboost import XGBRegressor
from benchmark import subject_weights


class ImprovedXGB:
    def __init__(self, config, features, task="classification"):
        self.config, self.features, self.task = config, features, task

    def fit(self, frame):
        self.models, self.imputers = {}, {}
        groups = [("pooled", frame)] if self.config["strategy"] == "pooled" else list(frame.groupby("cohort"))
        for key, data in groups:
            x = data[self.features].to_numpy(dtype=float)
            if self.config["missing"] == "median":
                imp = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
                x = imp.fit_transform(x); self.imputers[key] = imp
            y = data.next_days.to_numpy(float)
            if self.task == "classification":
                y = (y <= 90).astype(float)
                if self.config["week91"] == "soft":
                    # Sensitivity assumption: independent uniform offsets 0..6
                    # within each anonymized week imply 21/49 <=90-day gaps
                    # when recorded week difference is 91 days. Never relabel
                    # evaluation rows or omit them from the headline score.
                    uncertain = (data.cohort == "LUMIERE") & (data.next_days == 91)
                    y[uncertain.to_numpy()] = 21/49
            params = dict(self.config["params"])
            model = XGBRegressor(objective="binary:logistic" if self.task == "classification" else "reg:absoluteerror",
                tree_method="hist", device="cpu", n_jobs=2, random_state=42, verbosity=0, **params)
            model.fit(x, y, sample_weight=subject_weights(data))
            self.models[key] = model
        return self

    def predict(self, frame):
        result = np.empty(len(frame), dtype=float)
        groups = [("pooled", np.arange(len(frame)))] if self.config["strategy"] == "pooled" else [(c, np.flatnonzero(frame.cohort.to_numpy() == c)) for c in frame.cohort.unique()]
        for key, idx in groups:
            x = frame.iloc[idx][self.features].to_numpy(dtype=float)
            if key in self.imputers: x = self.imputers[key].transform(x)
            result[idx] = self.models[key].predict(x)
        return np.clip(result, 0, 1) if self.task == "classification" else np.clip(result, 1, 3650)
