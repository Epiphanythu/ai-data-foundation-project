"""modeling/run_model_monitoring.py 模型衰减监控（MLOps）

将概念漂移检测、AUC 衰减整合为可操作的运维建议：
1. 模拟不同重训频率下的模型性能变化
2. 计算"不重训"的机会成本（利润损失）
3. 输出清晰的可执行建议："每 X 个月重训一次"

消费模块：
- 引用 analyze_concept_drift.py 的 PSI 数据
- 引用 train_baseline_model.py 的 baseline AUC
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_ISSUE_YEAR  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
    ASSUMED_INTEREST_MARGIN,
    ASSUMED_LGD,
)
from constant.paths import FIGURES_DIR, TABLES_DIR, MODEL_METRICS_CSV  # noqa: E402
from common.model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

MONITORING_REPORT_CSV = TABLES_DIR / "model_monitoring_report.csv"
MONITORING_RETRAIN_PNG = FIGURES_DIR / "monitoring_retrain_simulation.png"
MONITORING_DASHBOARD_PNG = FIGURES_DIR / "monitoring_health_dashboard.png"


def _simulate_retraining_frequency(
    df: pd.DataFrame,
    frequencies_months: list[int] = [1, 3, 6, 12, 24],
) -> pd.DataFrame:
    """模拟不同重训频率下的性能变化。

    思路：按年份切分，假设模型在初始训练后不再重训，
    逐年评估 AUC / KS 衰减，计算累积利润损失。
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer

    feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES
                    if c in df.columns and df[c].dtype in ("float64", "int64")]

    years = sorted(df[COL_ISSUE_YEAR].dropna().unique().astype(int))
    if len(years) < 4:
        logger.warning("Not enough years for retraining simulation")
        return pd.DataFrame()

    results = []
    train_start_year = years[0]
    train_end_year = years[len(years) // 2]  # 前半段训练
    test_years = years[len(years) // 2:]  # 后半段测试

    # 基线：在训练期数据上训练
    train_mask = df[COL_ISSUE_YEAR].between(train_start_year, train_end_year)
    X_train = df.loc[train_mask, feature_cols].fillna(0)
    y_train = df.loc[train_mask, LABEL_COL]

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_train_t = scaler.fit_transform(imputer.fit_transform(X_train))

    base_model = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)
    base_model.fit(X_train_t, y_train)

    # 逐年评估（不重训）
    yearly_metrics = []
    for year in test_years:
        test_mask = df[COL_ISSUE_YEAR] == year
        X_test = df.loc[test_mask, feature_cols].fillna(0)
        y_test = df.loc[test_mask, LABEL_COL]
        if len(y_test) < 100:
            continue

        X_test_t = scaler.transform(imputer.transform(X_test))
        auc = roc_auc_score(y_test, base_model.predict_proba(X_test_t)[:, 1])

        # 利润估算：假设通过阈值 0.5
        y_proba = base_model.predict_proba(X_test_t)[:, 1]
        y_pred = (y_proba >= 0.5).astype(int)
        accepted = y_pred == 0
        loan_amnt = df.loc[test_mask, "loan_amnt"].mean() if "loan_amnt" in df.columns else 10000
        profit = (accepted.sum() * ASSUMED_INTEREST_MARGIN * loan_amnt -
                  y_test[accepted].sum() * ASSUMED_LGD * loan_amnt)

        yearly_metrics.append({
            "year": int(year),
            "auc": round(auc, 4),
            "pass_rate": round(float(accepted.mean()), 4),
            "profit": round(float(profit), 2),
        })

    # 不同重训频率的模拟
    for freq in frequencies_months:
        freq_years = max(1, freq // 12)
        cum_profit = 0
        cum_auc = 0
        n_eval = 0

        model = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)
        train_data = df[df[COL_ISSUE_YEAR].between(train_start_year, train_end_year)]
        X_t = scaler.fit_transform(imputer.fit_transform(train_data[feature_cols].fillna(0)))
        model.fit(X_t, train_data[LABEL_COL])

        last_retrain = train_end_year
        for year in test_years:
            if year - last_retrain >= freq_years:
                # 重训
                retrain_mask = df[COL_ISSUE_YEAR].between(train_start_year, year - 1)
                X_t = scaler.fit_transform(imputer.fit_transform(
                    df.loc[retrain_mask, feature_cols].fillna(0)))
                model.fit(X_t, df.loc[retrain_mask, LABEL_COL])
                last_retrain = year

            test_mask = df[COL_ISSUE_YEAR] == year
            X_test = df.loc[test_mask, feature_cols].fillna(0)
            y_test = df.loc[test_mask, LABEL_COL]
            if len(y_test) < 100:
                continue
            X_test_t = scaler.transform(imputer.transform(X_test))
            y_proba = model.predict_proba(X_test_t)[:, 1]
            auc = roc_auc_score(y_test, y_proba)
            y_pred = (y_proba >= 0.5).astype(int)
            accepted = y_pred == 0
            loan_amnt = df.loc[test_mask, "loan_amnt"].mean() if "loan_amnt" in df.columns else 10000
            profit = (accepted.sum() * ASSUMED_INTEREST_MARGIN * loan_amnt -
                      y_test[accepted].sum() * ASSUMED_LGD * loan_amnt)
            cum_profit += profit
            cum_auc += auc
            n_eval += 1

        avg_auc = cum_auc / max(n_eval, 1)
        baseline_no_retrain_auc = yearly_metrics[-1]["auc"] if yearly_metrics else 0
        auc_loss = baseline_no_retrain_auc - avg_auc

        results.append({
            "retrain_frequency_months": freq,
            "n_retrains": (test_years[-1] - test_years[0]) // max(freq_years, 1),
            "avg_auc": round(avg_auc, 4),
            "cumulative_profit": round(float(cum_profit), 2),
            "auc_gain_vs_no_retrain": round(float(auc_loss), 4),
        })

    return pd.DataFrame(results)


def _load_concept_drift_summary() -> dict:
    """从概念漂移数据中提取关键摘要，用于监控面板。"""
    psi_path = TABLES_DIR / "concept_drift_psi.csv"
    if not psi_path.exists():
        return {"status": "no_data", "max_psi": None, "high_drift_features": []}

    psi_df = pd.read_csv(psi_path)
    psi_vals = pd.to_numeric(psi_df["psi"], errors="coerce").dropna()
    high_drift = psi_df[pd.to_numeric(psi_df["psi"], errors="coerce") > 0.25]

    return {
        "status": "warning" if len(high_drift) > 0 else "healthy",
        "max_psi": round(float(psi_vals.max()), 4) if len(psi_vals) > 0 else 0,
        "avg_psi": round(float(psi_vals.mean()), 4) if len(psi_vals) > 0 else 0,
        "n_high_drift": len(high_drift),
    }


def _load_baseline_auc() -> float:
    """加载基线 AUC"""
    if MODEL_METRICS_CSV.exists():
        metrics = pd.read_csv(MODEL_METRICS_CSV)
        auc_rows = metrics[metrics["model"].str.contains("xgb", case=False)]
        if len(auc_rows) > 0:
            return float(auc_rows["auc"].iloc[0])
    return 0.75  # 默认缺省值


def _plot_retrain_simulation(sim_df: pd.DataFrame):
    if sim_df.empty:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    freqs = sim_df["retrain_frequency_months"].tolist()
    ax1.plot(freqs, sim_df["avg_auc"].values, "o-", color="steelblue", linewidth=2, markersize=8)
    ax1.axhline(sim_df["avg_auc"].values[-1], color="gray", linestyle="--", alpha=0.3)
    ax1.set_xlabel("Retraining Interval (months)")
    ax1.set_ylabel("Average AUC")
    ax1.set_title("Model Performance vs Retraining Frequency")
    ax1.grid(alpha=0.3)

    ax2.bar(range(len(freqs)), sim_df["cumulative_profit"].values, color="steelblue", alpha=0.8)
    ax2.set_xticks(range(len(freqs)))
    ax2.set_xticklabels([f"{f}mo" for f in freqs])
    ax2.set_ylabel("Cumulative Profit ($)")
    ax2.set_title("Profit Impact of Retraining Frequency")
    ax2.grid(axis="y", alpha=0.3)

    best_idx = sim_df["cumulative_profit"].values.argmax()
    fig.text(0.5, 0.01,
             f"Recommendation: retrain every {int(sim_df['retrain_frequency_months'].iloc[best_idx])} months "
             f"(profit=${sim_df['cumulative_profit'].iloc[best_idx]:,.0f})",
             ha="center", fontsize=11, fontweight="bold", color="darkgreen")

    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(MONITORING_RETRAIN_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", MONITORING_RETRAIN_PNG)


def _plot_health_dashboard(drift_info: dict, baseline_auc: float):
    """模型健康仪表盘 — 单图汇总所有监控指标"""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis("off")

    status_color = "green" if drift_info["status"] == "healthy" else ("orange" if drift_info["status"] == "warning" else "red")

    metrics = [
        ("Drift Status", drift_info["status"].upper(), status_color),
        ("Max PSI", f"{drift_info.get('max_psi', 'N/A')}", "red" if drift_info.get("max_psi", 0) > 0.25 else "green"),
        ("Avg PSI", f"{drift_info.get('avg_psi', 'N/A')}", "black"),
        ("High-Drift Features", f"{drift_info.get('n_high_drift', 'N/A')}", "red" if drift_info.get("n_high_drift", 0) > 0 else "green"),
        ("Baseline AUC", f"{baseline_auc:.4f}", "green" if baseline_auc > 0.7 else "orange"),
    ]

    for i, (label, value, color) in enumerate(metrics):
        y_pos = 1 - i * 0.15
        ax.text(0.1, y_pos, f"{label}:", fontsize=12, fontweight="bold")
        ax.text(0.5, y_pos, value, fontsize=12, fontweight="bold", color=color,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.3))

    ax.text(0.5, 0.1, "Model Health Dashboard — regenerated on each monitoring cycle",
            ha="center", fontsize=9, fontstyle="italic", color="gray")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(MONITORING_DASHBOARD_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", MONITORING_DASHBOARD_PNG)


def run():
    logger.info("=" * 60)
    logger.info("Model Monitoring (MLOps) — Retrain Simulation & Health Check")
    logger.info("=" * 60)

    # 1. 加载数据
    df = build_training_sample(sample_size=80000, enable_macro=True, enable_state=True)

    # 2. 概念漂移摘要
    drift_info = _load_concept_drift_summary()
    logger.info("Drift summary: status=%s, max_psi=%s", drift_info["status"], drift_info["max_psi"])

    # 3. 基线 AUC
    baseline_auc = _load_baseline_auc()
    logger.info("Baseline AUC: %.4f", baseline_auc)

    # 4. 重训频率模拟
    sim_df = _simulate_retraining_frequency(df)
    if not sim_df.empty:
        logger.info("Retrain simulation:\n%s", sim_df.to_string(index=False))
        sim_df.to_csv(MONITORING_REPORT_CSV, index=False)
        _plot_retrain_simulation(sim_df)
        best = sim_df.iloc[sim_df["cumulative_profit"].values.argmax()]
        logger.info("Optimal retraining interval: %d months, avg AUC=%.4f, profit=$%.0f",
                    int(best["retrain_frequency_months"]), best["avg_auc"], best["cumulative_profit"])

    # 5. 健康仪表盘
    _plot_health_dashboard(drift_info, baseline_auc)

    logger.info("Model monitoring complete.")


def main():
    run()


if __name__ == "__main__":
    main()
