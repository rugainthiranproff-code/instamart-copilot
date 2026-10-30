import os
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from lapse_data import build_dataset, get_split

os.makedirs("outputs", exist_ok=True)

df = build_dataset()
X_train, X_test, y_train, y_test = get_split()

NUM = ["recency", "frequency", "monetary", "avg_discount", "cancel_rate",
       "avg_delivery", "age", "tenure"]
CAT = ["fav_category", "city", "gender"]


def make_pre():
    return ColumnTransformer([
        ("num", StandardScaler(), NUM),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CAT),
    ])


def metrics(model):
    pred = model.predict(X_test)
    return {
        "cm": confusion_matrix(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
    }


def show(name, m):
    print(f"\n{name}")
    print("confusion matrix (rows = actual [stayed, lapsed], cols = predicted):")
    print(m["cm"])
    print(f"precision {m['precision']:.3f} | recall {m['recall']:.3f} | F1 {m['f1']:.3f}")


# ---------------- Task 5: preprocessing without leakage ----------------
print("=== TASK 5: PREPROCESSING ===")
assert X_train.isna().sum().sum() == 0 and X_test.isna().sum().sum() == 0
print("missing values in features: 0 (asserted)")
demo = make_pre().fit(X_train)
scaler_mean = demo.named_transformers_["num"].mean_[NUM.index("frequency")]
print("scaler mean of frequency (train rows only):", round(scaler_mean, 3))
print("full-cohort mean of frequency:", round(df["frequency"].mean(), 3))

# ---------------- Task 6: tune and evaluate ----------------
print("\n=== TASK 6: TUNING ===")
lr_pipe = Pipeline([("pre", make_pre()), ("clf", LogisticRegression(max_iter=1000))])
lr_grid = GridSearchCV(lr_pipe, {"clf__C": [0.01, 0.1, 1, 10, 100]}, cv=5, scoring="f1")
lr_grid.fit(X_train, y_train)
print("LR best params:", lr_grid.best_params_, "| best CV F1:", round(lr_grid.best_score_, 3))

rf_pipe = Pipeline([("pre", make_pre()),
                    ("clf", RandomForestClassifier(n_estimators=100, random_state=42))])
rf_grid = GridSearchCV(rf_pipe, {"clf__max_depth": [3, 5, 8],
                                 "clf__min_samples_leaf": [5, 10, 20]},
                       cv=5, scoring="f1", n_jobs=-1)
rf_grid.fit(X_train, y_train)
print("RF best params:", rf_grid.best_params_, "| best CV F1:", round(rf_grid.best_score_, 3))

print("\n=== TEST SET (used only now, after tuning) ===")
print("baseline: accuracy 61.6%, lapsed F1 0.0")
lr_m = metrics(lr_grid.best_estimator_)
rf_m = metrics(rf_grid.best_estimator_)
show("Logistic Regression", lr_m)
show("Random Forest", rf_m)

if rf_grid.best_score_ >= lr_grid.best_score_:
    selected, sel_name, sel_m = rf_grid.best_estimator_, "Random Forest", rf_m
else:
    selected, sel_name, sel_m = lr_grid.best_estimator_, "Logistic Regression", lr_m
print("\nSELECTED (higher cross-validated F1):", sel_name, "| test F1:", round(sel_m["f1"], 3))
print("(expected: LR C=1 F1 about 0.62; RF depth 8 leaf 10 F1 about 0.65; selected F1 >= 0.55)")

# ---------------- Task 7: class-balance experiment ----------------
print("\n=== TASK 7: OVERSAMPLING (training rows only) ===")
n_add = int((y_train == 0).sum() - (y_train == 1).sum())
extra = X_train[y_train == 1].sample(n=n_add, replace=True, random_state=42)
X_bal = pd.concat([X_train, extra])
y_bal = pd.concat([y_train, pd.Series(1, index=extra.index)])
print("balanced train counts:", y_bal.value_counts().to_dict(), "(expected 570 each)")
bal_lr = clone(lr_grid.best_estimator_).fit(X_bal, y_bal)
bal_m = metrics(bal_lr)
show("LR (unbalanced)", lr_m)
show("LR (oversampled)", bal_m)
print("changes: precision %+.3f | recall %+.3f | F1 %+.3f" % (
    bal_m["precision"] - lr_m["precision"],
    bal_m["recall"] - lr_m["recall"],
    bal_m["f1"] - lr_m["f1"]))
print("(expected: recall about 0.64 -> 0.85, precision stays near 0.6)")

# ---------------- Task 8: interpret, persist, use ----------------
print("\n=== TASK 8: INTERPRETATION ===")
names = rf_grid.best_estimator_.named_steps["pre"].get_feature_names_out()
imp = rf_grid.best_estimator_.named_steps["clf"].feature_importances_
top5 = pd.Series(imp, index=names).sort_values(ascending=False).head(5)
print("top 5 random forest features:")
print(top5.round(3).to_string())

lr_names = lr_grid.best_estimator_.named_steps["pre"].get_feature_names_out()
coef = pd.Series(lr_grid.best_estimator_.named_steps["clf"].coef_[0], index=lr_names)
print("\nlogistic regression coefficients (+ = more likely to lapse):")
for f in ["num__recency", "num__frequency", "num__cancel_rate"]:
    print(f, round(coef[f], 3), "->", "positive" if coef[f] > 0 else "negative")

joblib.dump(selected, "outputs/lapse_model.joblib")
reloaded = joblib.load("outputs/lapse_model.joblib")
same = np.array_equal(selected.predict(X_test), reloaded.predict(X_test))
print("\nreloaded model reproduces test predictions exactly:", same)
assert same

seg = pd.read_csv("outputs/customer_segments.csv")
premium_ids = set(seg.loc[seg["is_premium"].astype(str) == "True", "customer_id"])
proba = selected.predict_proba(X_test)[:, 1]
res = pd.DataFrame({"customer_id": X_test.index,
                    "lapse_probability": proba.round(4),
                    "actually_lapsed": y_test.values})
res = res[res["customer_id"].isin(premium_ids)]
print("premium customers in test set:", len(res))
res = res.sort_values("lapse_probability", ascending=False).head(10)
res.to_csv("outputs/retention_list.csv", index=False)
print("retention list rows:", len(res), "| truly lapsed:", int(res["actually_lapsed"].sum()))
print("saved outputs/lapse_model.joblib and outputs/retention_list.csv")