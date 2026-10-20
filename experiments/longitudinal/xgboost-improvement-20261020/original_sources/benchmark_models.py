"""Twelve CPU model families; paired classification and interval regression."""
import inspect
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (RandomForestClassifier, RandomForestRegressor,
    ExtraTreesClassifier, ExtraTreesRegressor, AdaBoostClassifier, AdaBoostRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
    HistGradientBoostingClassifier, HistGradientBoostingRegressor)
from sklearn.svm import SVC, SVR
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv
from xgboost import XGBClassifier, XGBRegressor

FAMILIES = ["linear", "decision_tree", "random_forest", "extra_trees", "adaboost",
            "gradient_boosting", "hist_gradient_boosting", "xgboost", "rbf_svm",
            "nearest_neighbors", "neural_network", "survival_forest"]
LABELS = dict(zip(FAMILIES, ["Logistic / Ridge", "Decision tree", "Random forest",
    "Extra Trees", "AdaBoost", "Gradient boosting", "Histogram boosting", "XGBoost",
    "RBF SVM", "Nearest neighbors", "Small neural network", "Random survival forest"]))


def estimators(family, setting):
    s = setting
    if family == "linear":
        return LogisticRegression(C=[.1, 2.][s], max_iter=2000, random_state=42), Ridge(alpha=[10., 1.][s])
    if family == "decision_tree":
        kwargs = dict(max_depth=[3, 5][s], min_samples_leaf=[15, 10][s], random_state=42)
        return DecisionTreeClassifier(**kwargs), DecisionTreeRegressor(criterion="absolute_error", **kwargs)
    if family in ("random_forest", "extra_trees"):
        kwargs = dict(n_estimators=120, max_depth=[4, 8][s], min_samples_leaf=[10, 5][s], random_state=42, n_jobs=2)
        cls, reg = (RandomForestClassifier, RandomForestRegressor) if family == "random_forest" else (ExtraTreesClassifier, ExtraTreesRegressor)
        return cls(**kwargs), reg(criterion="absolute_error", **kwargs)
    if family == "adaboost":
        kwargs = dict(n_estimators=100, learning_rate=[.05, .3][s], random_state=42)
        return (AdaBoostClassifier(estimator=DecisionTreeClassifier(max_depth=[1, 2][s], min_samples_leaf=10), **kwargs),
                AdaBoostRegressor(estimator=DecisionTreeRegressor(max_depth=[2, 3][s], min_samples_leaf=10), **kwargs))
    if family == "gradient_boosting":
        kwargs = dict(n_estimators=[100, 180][s], learning_rate=.04, max_depth=[2, 3][s], min_samples_leaf=12, random_state=42)
        return GradientBoostingClassifier(**kwargs), GradientBoostingRegressor(loss="absolute_error", **kwargs)
    if family == "hist_gradient_boosting":
        kwargs = dict(max_iter=160, learning_rate=.05, max_leaf_nodes=[7, 15][s], min_samples_leaf=15, l2_regularization=[10., 1.][s], early_stopping=False, random_state=42)
        return HistGradientBoostingClassifier(**kwargs), HistGradientBoostingRegressor(loss="absolute_error", **kwargs)
    if family == "xgboost":
        kwargs = dict(n_estimators=[120, 220][s], max_depth=[2, 3][s], learning_rate=.04,
                      min_child_weight=8, reg_lambda=10, subsample=.85, colsample_bytree=.85,
                      tree_method="hist", device="cpu", n_jobs=2, random_state=42, verbosity=0)
        return XGBClassifier(objective="binary:logistic", **kwargs), XGBRegressor(objective="reg:absoluteerror", **kwargs)
    if family == "rbf_svm":
        return SVC(C=[.3, 3.][s], gamma="scale", probability=True, random_state=42), SVR(C=[1., 10.][s], epsilon=.15)
    if family == "nearest_neighbors":
        kwargs = dict(n_neighbors=[15, 35][s], weights="distance", p=2, n_jobs=2)
        return KNeighborsClassifier(**kwargs), KNeighborsRegressor(**kwargs)
    if family == "neural_network":
        kwargs = dict(hidden_layer_sizes=[(16,), (32,)][s], alpha=[1., .1][s], solver="lbfgs", max_iter=300, max_fun=10000, random_state=42)
        return MLPClassifier(**kwargs), MLPRegressor(**kwargs)
    raise ValueError(family)


class ModelPair:
    def __init__(self, family, setting, features):
        self.family, self.setting, self.features = family, setting, features
        self.imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
        self.scaler = StandardScaler() if family in ("linear", "rbf_svm", "nearest_neighbors", "neural_network") else None
        self.log_target = family in ("linear", "rbf_svm", "nearest_neighbors", "neural_network")

    def fit(self, frame, weights):
        x = self.imputer.fit_transform(frame[self.features])
        if self.scaler is not None: x = self.scaler.fit_transform(x)
        y = frame.next_days.to_numpy(float)
        if self.family == "survival_forest":
            self.forest = RandomSurvivalForest(n_estimators=100, min_samples_leaf=[20, 10][self.setting], max_depth=[4, 8][self.setting], max_features=1., random_state=42, n_jobs=2)
            self.forest.fit(x, Surv.from_arrays(np.ones(len(y), bool), y), sample_weight=weights)
        else:
            self.classifier, self.regressor = estimators(self.family, self.setting)
            for model, target in [(self.classifier, (y <= 90).astype(int)),
                                  (self.regressor, np.log1p(y) if self.log_target else y)]:
                kwargs = {"sample_weight": weights} if "sample_weight" in inspect.signature(model.fit).parameters else {}
                model.fit(x, target, **kwargs)
        return self

    def predict(self, frame):
        x = self.imputer.transform(frame[self.features])
        if self.scaler is not None: x = self.scaler.transform(x)
        if self.family == "survival_forest":
            funcs = self.forest.predict_survival_function(x)
            prob = np.array([1-f(min(90., f.x[-1])) if 90 >= f.x[0] else 0. for f in funcs])
            days = np.array([f.x[np.flatnonzero(f.y <= .5)[0]] if np.any(f.y <= .5) else f.x[-1] for f in funcs])
        else:
            prob = self.classifier.predict_proba(x)[:, 1]
            days = self.regressor.predict(x)
            if self.log_target: days = np.expm1(np.clip(days, 0, np.log1p(3650)))
        return np.clip(prob, 0, 1), np.clip(days, 1, 3650)
