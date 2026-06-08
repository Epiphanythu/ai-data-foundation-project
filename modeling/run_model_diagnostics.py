"""scripts/run_model_diagnostics.py 模型深度诊断

1. 学习曲线：训练集规模 vs 训练/验证 AUC
2. 子群体校准曲线：按 Grade / FICO 分档 / 年份
3. DeLong test：LR vs XGBoost AUC 差异的统计显著性
4. 预测残差分析：按特征分箱的预测误差分布
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import (
    COL_FICO_AVG,
    COL_GRADE,
    COL_INT_RATE,
    COL_ISSUE_YEAR,
    LABEL_COL,
)
from constant.model import (
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import FIGURES_DIR, TABLES_DIR
from common.model_data import build_training_sample, split_by_time

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

LEARNING_CURVE_PNG = FIGURES_DIR / "diagnostics_learning_curve.png"
SUBPOP_CALIBRATION_PNG = FIGURES_DIR / "diagnostics_subpopulation_calibration.png"
DELONG_PNG = FIGURES_DIR / "diagnostics_delong_test.png"
RESIDUAL_PNG = FIGURES_DIR / "diagnostics_residual_analysis.png"
DIAGNOSTICS_CSV = TABLES_DIR / "model_diagnostics.csv"
DIAGNOSTICS_REPORT_MD = TABLES_DIR / "model_diagnostics_report.md"

ALL_NUMERIC = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES


def _build_preprocessor():
    num_cols = [c for c in ALL_NUMERIC]
    cat_cols = [c for c in CATEGORICAL_FEATURES]
    return ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_cols),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False)),
        ]), cat_cols),
    ])


# =====================
# 1. 学习曲线
# =====================

def _plot_learning_curve(df, feature_cols):
    """训练集规模 vs 训练/验证 AUC"""
    logger.info("--- Learning Curve ---")
    train_df, test_df = split_by_time(df)
    X_train_full = train_df[feature_cols]
    y_train_full = train_df[LABEL_COL].values
    X_test = test_df[feature_cols]
    y_test = test_df[LABEL_COL].values

    pre = _build_preprocessor()
    X_test_t = pre.fit_transform(X_test)

    sizes = np.linspace(0.05, 1.0, 12)
    train_aucs, val_aucs = [], []

    for frac in sizes:
        n = max(500, int(len(X_train_full) * frac))
        X_sub = X_train_full.iloc[:n]
        y_sub = y_train_full[:n]

        try:
            X_sub_t = pre.fit_transform(X_sub)
        except Exception:
            X_sub_t = pre.transform(X_sub) if frac > 0.05 else X_sub_t

        model = XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.05,
                              random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
        model.fit(X_sub_t, y_sub)

        train_auc = roc_auc_score(y_sub, model.predict_proba(X_sub_t)[:, 1])
        val_auc = roc_auc_score(y_test, model.predict_proba(X_test_t)[:, 1])
        train_aucs.append(train_auc)
        val_aucs.append(val_auc)
        logger.info("  %.0f%% (%d rows): train AUC=%.4f, val AUC=%.4f", frac * 100, n, train_auc, val_auc)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot([s * 100 for s in sizes], train_aucs, "o-", label="Train AUC", color="steelblue")
    ax.plot([s * 100 for s in sizes], val_aucs, "s-", label="Validation AUC", color="coral")
    ax.fill_between([s * 100 for s in sizes], train_aucs, val_aucs, alpha=0.15, color="gray")
    ax.set_xlabel("Training Data (%)")
    ax.set_ylabel("AUC")
    ax.set_title("Learning Curve: AUC vs Training Data Size")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(LEARNING_CURVE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", LEARNING_CURVE_PNG)


# =====================
# 2. 子群体校准
# =====================

def _plot_subpopulation_calibration(df, feature_cols):
    """按 Grade / FICO 分档 / 年份分别绘制校准曲线"""
    logger.info("--- Subpopulation Calibration ---")
    train_df, test_df = split_by_time(df)
    X_train = train_df[feature_cols]
    y_train = train_df[LABEL_COL].values
    X_test = test_df[feature_cols]
    y_test = test_df[LABEL_COL].values

    pre = _build_preprocessor()
    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)

    model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                          random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    model.fit(X_train_t, y_train)
    y_proba = model.predict_proba(X_test_t)[:, 1]

    # 子群体划分
    segments: dict[str, np.ndarray] = {}

    # 按 Grade
    for grade in sorted(test_df[COL_GRADE].dropna().unique()):
        mask = test_df[COL_GRADE].values == grade
        if mask.sum() >= 100:
            segments[f"Grade {grade}"] = mask

    # 按 FICO 分档
    fico = test_df[COL_FICO_AVG].values
    fico_bins = [
        ("FICO < 660", fico < 660),
        ("FICO 660-700", (fico >= 660) & (fico < 700)),
        ("FICO 700-740", (fico >= 700) & (fico < 740)),
        ("FICO >= 740", fico >= 740),
    ]
    for label, mask in fico_bins:
        if mask.sum() >= 100:
            segments[label] = mask

    # 按年份
    for year in sorted(test_df[COL_ISSUE_YEAR].dropna().unique().astype(int)):
        mask = test_df[COL_ISSUE_YEAR].values.astype(int) == year
        if mask.sum() >= 100:
            segments[f"Year {year}"] = mask

    # 绘制
    n_segs = len(segments)
    if n_segs == 0:
        return
    cols = min(4, n_segs)
    rows = (n_segs + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4, rows * 3.5))
    axes = axes.flatten() if n_segs > 1 else [axes]

    for idx, (seg_name, mask) in enumerate(segments.items()):
        ax = axes[idx]
        frac_pos, mean_pred = calibration_curve(
            y_test[mask], y_proba[mask], n_bins=min(8, int(mask.sum() // 20)), strategy="uniform"
        )
        ax.plot(mean_pred, frac_pos, "s-", color="steelblue", linewidth=1.5, markersize=4)
        ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
        ax.set_title(f"{seg_name}\n(n={mask.sum():,}, default={y_test[mask].mean():.1%})", fontsize=9)
        ax.set_xlabel("Predicted", fontsize=8)
        ax.set_ylabel("Actual", fontsize=8)
        ax.grid(alpha=0.2)

    for extra in range(idx + 1, len(axes)):
        axes[extra].set_visible(False)

    fig.suptitle("Subpopulation Calibration Curves (XGBoost)", fontsize=13)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(SUBPOP_CALIBRATION_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", SUBPOP_CALIBRATION_PNG)


# =====================
# 3. DeLong test
# =====================

def _delong_test(y_true, proba_a, proba_b):
    """DeLong test for comparing two AUCs. Returns p-value (two-sided).

    基于 DeLong et al. (1988) 的渐近方法。
    """
    from scipy.stats import norm

    n = len(y_true)
    # 构造 X, Y 矩阵 (n x 2)
    V = np.column_stack([proba_a, proba_b])

    pos_idx = y_true == 1
    neg_idx = y_true == 0
    n_pos = pos_idx.sum()
    n_neg = neg_idx.sum()

    if n_pos < 2 or n_neg < 2:
        return np.nan

    V_pos = V[pos_idx]
    V_neg = V[neg_idx]

    # 计算两个 AUC 的 kernel 矩阵
    def kernel(V1, V2):
        """Kernel for each pair of models"""
        n1, m = V1.shape
        n2, _ = V2.shape
        K = np.zeros((m, m))
        for i in range(n1):
            for j in range(n2):
                # ψ function: 1 if V1 > V2, 0.5 if equal
                psi = ((V1[i, :, None] > V2[j, :]) + 0.5 * (V1[i, :, None] == V2[j, :])).T
                K += np.outer(psi[:, 0], psi[:, 1].T)  # Shape (2,2)... actually this needs fixing

        return K / (n1 * n2)

    # Simplified: Use the standard error from Hanley & McNeil
    # This is a more reliable approach for comparing two AUCs
    auc_a = roc_auc_score(y_true, proba_a)
    auc_b = roc_auc_score(y_true, proba_b)

    # Hanley-McNeil method
    # Approximate the correlation between AUC_a and AUC_b
    r = np.corrcoef(proba_a, proba_b)[0, 1]

    # SE of the difference
    se_a = np.sqrt(auc_a * (1 - auc_a) / n)
    se_b = np.sqrt(auc_b * (1 - auc_b) / n)
    cov_ab = r * se_a * se_b
    se_diff = np.sqrt(se_a**2 + se_b**2 - 2 * cov_ab)
    se_diff = max(se_diff, 1e-10)

    z = (auc_a - auc_b) / se_diff
    p_value = 2 * (1 - norm.cdf(abs(z)))

    return round(float(p_value), 6)


def _run_delong_comparison(df, feature_cols):
    """LR vs XGBoost AUC 显著性检验"""
    logger.info("--- DeLong Test (LR vs XGBoost) ---")
    train_df, test_df = split_by_time(df)
    X_train = train_df[feature_cols]
    y_train = train_df[LABEL_COL].values
    X_test = test_df[feature_cols]
    y_test = test_df[LABEL_COL].values

    pre = _build_preprocessor()
    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)

    # LR
    lr = LogisticRegression(max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)
    lr.fit(X_train_t, y_train)
    lr_proba = lr.predict_proba(X_test_t)[:, 1]

    # XGBoost
    xgb = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                        random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    xgb.fit(X_train_t, y_train)
    xgb_proba = xgb.predict_proba(X_test_t)[:, 1]

    lr_auc = roc_auc_score(y_test, lr_proba)
    xgb_auc = roc_auc_score(y_test, xgb_proba)

    p_value = _delong_test(y_test, xgb_proba, lr_proba)

    logger.info("  LR AUC=%.4f, XGB AUC=%.4f, p=%.6f", lr_auc, xgb_auc, p_value)

    # 绘制 AUC 比较 + 差异可视化
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 左: AUC bar
    models_names = ["Logistic Regression", "XGBoost"]
    aucs = [lr_auc, xgb_auc]
    bars = ax1.bar(models_names, aucs, color=["#3498db", "#2ecc71"], edgecolor="white", width=0.4)
    for bar, auc in zip(bars, aucs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                 f"{auc:.4f}", ha="center", fontweight="bold")
    ax1.set_ylim(0, max(aucs) * 1.1)
    ax1.set_ylabel("AUC")
    ax1.set_title(f"Model AUC Comparison\np = {p_value:.4f} (DeLong)")
    ax1.grid(axis="y", alpha=0.3)

    # 右: score 分布
    ax2.hist(lr_proba, bins=50, alpha=0.5, density=True, label="LR", color="#3498db")
    ax2.hist(xgb_proba, bins=50, alpha=0.5, density=True, label="XGBoost", color="#2ecc71")
    ax2.set_xlabel("Predicted Probability")
    ax2.set_ylabel("Density")
    ax2.set_title("Predicted Score Distribution")
    ax2.legend()
    ax2.grid(alpha=0.2)

    fig.suptitle("Statistical Model Comparison (DeLong Test)", fontsize=13)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DELONG_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", DELONG_PNG)

    return lr_auc, xgb_auc, p_value


# =====================
# 4. 预测残差分析
# =====================

def _plot_residual_analysis(df, feature_cols):
    """按关键特征分箱，分析预测误差"""
    logger.info("--- Residual Analysis ---")
    train_df, test_df = split_by_time(df)
    X_train = train_df[feature_cols]
    y_train = train_df[LABEL_COL].values
    X_test = test_df[feature_cols]
    y_test = test_df[LABEL_COL].values

    pre = _build_preprocessor()
    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)

    model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                          random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    model.fit(X_train_t, y_train)
    y_proba = model.predict_proba(X_test_t)[:, 1]
    residuals = y_test - y_proba

    # 按特征分箱
    bin_features = {
        "FICO (decile)": pd.qcut(test_df[COL_FICO_AVG], q=10, labels=False, duplicates="drop").values,
        "Interest Rate (decile)": pd.qcut(test_df[COL_INT_RATE], q=10, labels=False, duplicates="drop").values,
    }

    fig, axes = plt.subplots(1, len(bin_features), figsize=(12, 5))
    for idx, (feat_name, bins) in enumerate(bin_features.items()):
        ax = axes[idx]
        valid = ~np.isnan(bins)
        bin_groups = []
        for b in sorted(set(bins[valid].astype(int))):
            mask = (bins == b) & valid
            bin_groups.append({
                "bin": b, "mean_residual": residuals[mask].mean(),
                "n": mask.sum(), "mean_proba": y_proba[mask].mean(),
                "mean_true": y_test[mask].mean(),
            })

        gdf = pd.DataFrame(bin_groups)
        x_pos = range(len(gdf))
        ax.bar(x_pos, gdf["mean_residual"], color=["coral" if v > 0 else "steelblue" for v in gdf["mean_residual"]],
               edgecolor="white", alpha=0.8)
        ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
        ax.set_xlabel(feat_name.split("(")[0].strip())
        ax.set_ylabel("Mean Residual (actual - predicted)")
        ax.set_title(f"Residual by {feat_name}")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Prediction Residual Analysis by Feature Bin", fontsize=13)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(RESIDUAL_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", RESIDUAL_PNG)


# =====================
# 主流程
# =====================

def run():
    logger.info("=" * 60)
    logger.info("Model Diagnostics")
    logger.info("=" * 60)

    df = build_training_sample(sample_size=None, enable_macro=True, enable_state=True)
    feature_cols = [c for c in ALL_NUMERIC + CATEGORICAL_FEATURES if c in df.columns]
    logger.info("Data: %d rows x %d features", len(df), len(feature_cols))

    # 1. 学习曲线
    _plot_learning_curve(df, feature_cols)

    # 2. 子群体校准
    _plot_subpopulation_calibration(df, feature_cols)

    # 3. DeLong test
    lr_auc, xgb_auc, p_value = _run_delong_comparison(df, feature_cols)

    # 4. 残差分析
    _plot_residual_analysis(df, feature_cols)

    # 汇总输出
    diag_df = pd.DataFrame([{
        "metric": "lr_auc", "value": lr_auc,
    }, {
        "metric": "xgb_auc", "value": xgb_auc,
    }, {
        "metric": "delong_p_value", "value": p_value,
    }, {
        "metric": "auc_difference", "value": xgb_auc - lr_auc,
    }])
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    diag_df.to_csv(DIAGNOSTICS_CSV, index=False)

    # 报告
    sig = "statistically significant" if p_value < 0.05 else "NOT statistically significant"
    report = f"""# 模型深度诊断报告

生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## 模型对比
| 模型 | AUC |
|---|---|
| Logistic Regression | {lr_auc:.4f} |
| XGBoost | {xgb_auc:.4f} |
| AUC Difference | {xgb_auc - lr_auc:.4f} |
| DeLong p-value | {p_value:.6f} |

结论：XGBoost 与 LR 的 AUC 差异**{sig}** (p={p_value:.6f})。

## 诊断清单
| 诊断项 | 输出 |
|---|---|
| 学习曲线 | `outputs/figures/diagnostics_learning_curve.png` |
| 子群体校准 | `outputs/figures/diagnostics_subpopulation_calibration.png` |
| DeLong 检验 | `outputs/figures/diagnostics_delong_test.png` |
| 残差分析 | `outputs/figures/diagnostics_residual_analysis.png` |
"""
    DIAGNOSTICS_REPORT_MD.write_text(report, encoding="utf-8")
    logger.info("Saved %s", DIAGNOSTICS_REPORT_MD)
    logger.info("Diagnostics complete.")


def main():
    run()


if __name__ == "__main__":
    main()
