"""modeling/run_bayesian_modeling.py 贝叶斯风控建模

用贝叶斯逻辑回归替代频率学派 LR，给出预测的完整后验分布而非点估计。
三个核心产出：
1. 系数后验分布（每个特征的重要性 + 可信区间）
2. 预测不确定性带（靠近决策边界的贷款 → 高不确定性 → 建议人工审核）
3. 与频率学派 LR 的对比（谁更稳定？谁更保守？）

不确定性估计直接嵌入监控链路：高不确定性的预测应触发复审。
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
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_ISSUE_YEAR  # noqa: E402
from constant.model import NUMERIC_FEATURES, CROSS_SOURCE_NUMERIC_FEATURES, RANDOM_SEED  # noqa: E402
from constant.paths import FIGURES_DIR, TABLES_DIR  # noqa: E402
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BAYES_COEF_CSV = TABLES_DIR / "bayesian_coefficients.csv"
BAYES_UNCERTAINTY_CSV = TABLES_DIR / "bayesian_uncertainty_flags.csv"
BAYES_COEF_PNG = FIGURES_DIR / "bayesian_coefficient_posterior.png"
BAYES_UNCERTAINTY_PNG = FIGURES_DIR / "bayesian_uncertainty_band.png"
BAYES_COMPARISON_PNG = FIGURES_DIR / "bayesian_vs_frequentist.png"


class BayesianLogisticRegression:
    """拉普拉斯近似的贝叶斯逻辑回归。

    用 LR 的 MAP 估计作为后验均值，用 Hessian 的逆作为后验协方差矩阵。
    这是贝叶斯 LR 最常用的近似方法（也是 R 中 bayesglm 的做法）。
    """

    def __init__(self, prior_scale: float = 1.0, random_state: int = RANDOM_SEED):
        self.prior_scale = prior_scale  # 先验标准差（越大 → 先验越弱 → 越接近频率学派）
        self.random_state = random_state
        self.coef_mean_: np.ndarray | None = None
        self.coef_cov_: np.ndarray | None = None
        self.scaler_: StandardScaler | None = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        n, p = X.shape

        # 标准化
        self.scaler_ = StandardScaler()
        X_scaled = self.scaler_.fit_transform(X)

        # MAP 估计 = L2 正则 LogisticRegression
        # 先验: β ~ N(0, prior_scale²)
        # 对应 C = prior_scale² / 2（sklearn 约定）
        C = self.prior_scale ** 2 / 2.0
        lr = LogisticRegression(C=max(C, 0.001), max_iter=2000,
                                random_state=self.random_state, penalty="l2", solver="lbfgs")
        lr.fit(X_scaled, y)
        self.coef_mean_ = np.concatenate([lr.intercept_, lr.coef_[0]])

        # Hessian 的逆 = 后验协方差矩阵
        proba = lr.predict_proba(X_scaled)[:, 1]
        W = np.diag(proba * (1 - proba))
        X_aug = np.column_stack([np.ones(n), X_scaled])
        # 先验精度矩阵
        prior_precision = np.eye(p + 1) / (self.prior_scale ** 2)
        # 后验精度 = X^T W X + prior_precision
        posterior_precision = X_aug.T @ W @ X_aug + prior_precision
        try:
            self.coef_cov_ = np.linalg.inv(posterior_precision)
        except np.linalg.LinAlgError:
            self.coef_cov_ = np.linalg.inv(posterior_precision + np.eye(p + 1) * 1e-6)

        self.feature_names_ = ["intercept"] + list(range(p))
        return self

    def predict_proba(self, X: np.ndarray, n_samples: int = 500) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """返回 (mean_proba, lower_ci, upper_ci)"""
        if self.coef_mean_ is None or self.coef_cov_ is None:
            raise RuntimeError("Model not fitted.")

        X_scaled = self.scaler_.transform(X)
        X_aug = np.column_stack([np.ones(X_scaled.shape[0]), X_scaled])

        # 从后验分布采样
        rng = np.random.default_rng(self.random_state)
        coef_samples = rng.multivariate_normal(self.coef_mean_, self.coef_cov_, size=n_samples)

        # 计算 proba 分布
        logits = X_aug @ coef_samples.T  # (n_samples, n_obs)
        probas = 1 / (1 + np.exp(-logits))  # sigmoid

        mean_proba = probas.mean(axis=1)
        lower_ci = np.percentile(probas, 5, axis=1)
        upper_ci = np.percentile(probas, 95, axis=1)

        return mean_proba, lower_ci, upper_ci

    def get_coefficient_posterior(self, feature_names: list[str]) -> pd.DataFrame:
        """返回系数的后验均值和 90% 可信区间"""
        if self.coef_mean_ is None or self.coef_cov_ is None:
            raise RuntimeError("Model not fitted.")
        stds = np.sqrt(np.diag(self.coef_cov_))
        names = ["intercept"] + feature_names
        rows = []
        for i, name in enumerate(names):
            rows.append({
                "feature": name,
                "mean": round(float(self.coef_mean_[i]), 6),
                "std": round(float(stds[i]), 6),
                "ci_lower": round(float(self.coef_mean_[i] - 1.645 * stds[i]), 6),
                "ci_upper": round(float(self.coef_mean_[i] + 1.645 * stds[i]), 6),
                "significant": "Yes" if self.coef_mean_[i] * self.coef_mean_[i] > 1.645 * 1.645 * stds[i] * stds[i] else "No",
            })
        return pd.DataFrame(rows)


def _plot_coefficient_posterior(coef_df: pd.DataFrame):
    """系数后验分布森林图"""
    sig_df = coef_df[coef_df["feature"] != "intercept"].copy()
    sig_df = sig_df.reindex(sig_df["mean"].abs().sort_values(ascending=True).index).tail(20)

    fig, ax = plt.subplots(figsize=(10, 6))
    y = range(len(sig_df))
    errors = [sig_df["mean"] - sig_df["ci_lower"], sig_df["ci_upper"] - sig_df["mean"]]
    colors = ["#e74c3c" if row["significant"] == "Yes" else "#95a5a6" for _, row in sig_df.iterrows()]
    ax.errorbar(sig_df["mean"].values, y, xerr=errors, fmt="o", color="steelblue",
                ecolor=colors, capsize=2, markersize=5)
    ax.axvline(0, color="black", linestyle="--", alpha=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(sig_df["feature"].values, fontsize=8)
    ax.set_xlabel("Coefficient (90% credible interval)")
    ax.set_title("Bayesian Logistic Regression: Posterior Coefficient Estimates\nRed CI = significant, Gray CI = not significant")
    ax.grid(axis="x", alpha=0.2)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(BAYES_COEF_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", BAYES_COEF_PNG)


def _plot_uncertainty_band(y_test: np.ndarray, mean_proba: np.ndarray,
                           lower_ci: np.ndarray, upper_ci: np.ndarray):
    """预测不确定性带 — 不确定性 vs 预测概率"""
    uncertainty = upper_ci - lower_ci
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 不确定性带（前 200 个样本）
    n_show = min(200, len(mean_proba))
    idx = np.arange(n_show)
    order = np.argsort(mean_proba[:n_show])
    ax1.fill_between(idx, lower_ci[:n_show][order], upper_ci[:n_show][order],
                     alpha=0.3, color="steelblue", label="90% credible interval")
    ax1.plot(idx, mean_proba[:n_show][order], "b-", linewidth=0.5, label="Posterior mean")
    ax1.axhline(0.5, color="red", linestyle="--", alpha=0.5, label="Decision threshold")
    ax1.set_xlabel("Sample (ordered by probability)")
    ax1.set_ylabel("Default probability")
    ax1.set_title("Prediction Uncertainty Band\n(sorted by mean probability)")
    ax1.legend(fontsize=7)

    # 不确定性 vs 违约概率散点图
    ax2.scatter(mean_proba[::10], uncertainty[::10], c=mean_proba[::10],
                cmap="RdYlGn_r", alpha=0.3, s=2)
    ax2.axhline(uncertainty.mean(), color="blue", linestyle="--", alpha=0.5,
                label=f"Mean uncertainty = {uncertainty.mean():.4f}")
    ax2.axvline(0.5, color="red", linestyle="--", alpha=0.5, label="Threshold = 0.5")
    ax2.set_xlabel("Predicted probability (mean)")
    ax2.set_ylabel("Uncertainty (90% CI width)")
    ax2.set_title("Uncertainty vs Predicted Probability\n(wide CI near 0.5 = high uncertainty)")
    ax2.legend(fontsize=7)

    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(BAYES_UNCERTAINTY_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", BAYES_UNCERTAINTY_PNG)


def _plot_comparison(y_test: np.ndarray, bayes_proba: np.ndarray, freq_proba: np.ndarray):
    """贝叶斯 vs 频率学派对比"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 散点对比
    ax1.scatter(freq_proba, bayes_proba, alpha=0.15, s=2, c="steelblue")
    ax1.plot([0, 1], [0, 1], "r--", alpha=0.5)
    ax1.set_xlabel("Frequentist LR probability")
    ax1.set_ylabel("Bayesian LR probability (posterior mean)")
    ax1.set_title(f"Bayesian vs Frequentist Probability\n(r={np.corrcoef(freq_proba, bayes_proba)[0,1]:.4f})")

    # 分歧最大的样本（Top 50）
    diff = np.abs(bayes_proba - freq_proba)
    top_divergent = np.argsort(-diff)[:50]
    ax2.scatter(freq_proba[top_divergent], bayes_proba[top_divergent],
                alpha=0.6, s=10, c="coral", edgecolors="darkred")
    ax2.plot([0, 1], [0, 1], "r--", alpha=0.5)
    ax2.set_xlabel("Frequentist LR")
    ax2.set_ylabel("Bayesian LR")
    ax2.set_title("Top 50 Most Divergent Predictions")

    brier_bayes = brier_score_loss(y_test, bayes_proba)
    brier_freq = brier_score_loss(y_test, freq_proba)
    auc_bayes = roc_auc_score(y_test, bayes_proba)
    auc_freq = roc_auc_score(y_test, freq_proba)

    fig.text(0.5, 0.01,
             f"Bayesian: Brier={brier_bayes:.4f}, AUC={auc_bayes:.4f}  |  "
             f"Frequentist: Brier={brier_freq:.4f}, AUC={auc_freq:.4f}",
             ha="center", fontsize=10, fontstyle="italic")

    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(BAYES_COMPARISON_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", BAYES_COMPARISON_PNG)


def run():
    logger.info("=" * 60)
    logger.info("Bayesian Risk Modeling (Laplace Approximation)")
    logger.info("=" * 60)

    df = build_training_sample(sample_size=60000)
    train_df, test_df = split_by_time(df)

    feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES
                    if c in df.columns and df[c].dtype in ("float64", "int64")]

    X_train = train_df[feature_cols].fillna(0).values
    X_test = test_df[feature_cols].fillna(0).values
    y_train = train_df[LABEL_COL].values
    y_test = test_df[LABEL_COL].values

    # 1. 贝叶斯 LR
    bayes_lr = BayesianLogisticRegression(prior_scale=1.0, random_state=RANDOM_SEED)
    bayes_lr.fit(X_train, y_train)
    mean_proba, lower_ci, upper_ci = bayes_lr.predict_proba(X_test)

    # 2. 频率学派 LR（对照）
    freq_lr = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED, C=1.0)
    scaler = StandardScaler()
    freq_lr.fit(scaler.fit_transform(X_train), y_train)
    freq_proba = freq_lr.predict_proba(scaler.transform(X_test))[:, 1]

    # 3. 系数后验
    coef_df = bayes_lr.get_coefficient_posterior(feature_cols)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    coef_df.to_csv(BAYES_COEF_CSV, index=False)
    _plot_coefficient_posterior(coef_df)

    # 4. 不确定性分析
    uncertainty = upper_ci - lower_ci
    uncertainty_flags = pd.DataFrame({
        "mean_proba": mean_proba,
        "lower_ci": lower_ci,
        "upper_ci": upper_ci,
        "uncertainty": uncertainty,
        "high_uncertainty": uncertainty > np.percentile(uncertainty, 90),
        "true_label": y_test,
    })
    uncertainty_flags.to_csv(BAYES_UNCERTAINTY_CSV, index=False)
    _plot_uncertainty_band(y_test, mean_proba, lower_ci, upper_ci)

    # 5. 对比
    _plot_comparison(y_test, mean_proba, freq_proba)

    high_uncertain = uncertainty_flags["high_uncertainty"].sum()
    logger.info("High-uncertainty predictions (top 10%%): %d / %d (%.1f%%)",
                high_uncertain, len(uncertainty_flags), high_uncertain / len(uncertainty_flags) * 100)
    logger.info("Bayesian LR complete.")


def main():
    run()


if __name__ == "__main__":
    main()
