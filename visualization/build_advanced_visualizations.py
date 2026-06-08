"""visualization/build_advanced_visualizations.py 进阶可视化产物生成
1. 美国州级 Choropleth 违约率地图（基于 plotly 静态导出）；
2. Grade × Purpose、FICO × Interest 二维风险热力图；
3. LR vs XGBoost 多模型对比：ROC / PR / KS / Calibration / Lift-Gain；
4. 借款人画像雷达图（Grade A-G）。

依赖：modeling/train_baseline_model.py 已生成 test_predictions.csv，
      原始 Lending Club CSV 用于 5/6 维特征聚合。
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
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import (  # noqa: E402
    COL_ADDR_STATE,
    COL_FICO_AVG,
    COL_FICO_HIGH,
    COL_FICO_LOW,
    COL_GRADE,
    COL_INT_RATE,
    COL_LOAN_AMNT,
    COL_LOAN_STATUS,
    COL_PURPOSE,
    COL_ANNUAL_INC,
    COL_DTI,
    GOOD_STATUSES,
    BAD_STATUSES,
    LABEL_COL,
)
from constant.paths import (  # noqa: E402
    ADV_CALIBRATION_PNG,
    ADV_CONFUSION_MATRIX_PNG,
    ADV_FICO_INTEREST_HEATMAP_PNG,
    ADV_GRADE_PURPOSE_HEATMAP_PNG,
    ADV_GRADE_RADAR_PNG,
    ADV_KS_PNG,
    ADV_LIFT_GAIN_PNG,
    ADV_PR_PNG,
    ADV_ROC_PNG,
    ADV_STATE_CHOROPLETH_PNG,
    ADVANCED_FIGURES_DIR,
    MODEL_TEST_PREDICTIONS_CSV,
)
from common.model_data import find_lending_club_csv  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 全局风格：金融报表常用的 viridis 色系 + 中文字体兜底
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110

# 阈值扫描分箱
FICO_BINS = [600, 640, 670, 700, 730, 760, 800, 850]
INT_RATE_BINS = [0, 7, 10, 13, 16, 20, 25, 35]


# load_state_default 读取州级违约率
def load_state_default() -> pd.DataFrame:
    """load_state_default 直接从原始 CSV 聚合每州违约率。"""
    csv_path = find_lending_club_csv()
    df = pd.read_csv(csv_path, usecols=[COL_LOAN_STATUS, COL_ADDR_STATE], low_memory=False)
    df = df[df[COL_LOAN_STATUS].isin(GOOD_STATUSES | BAD_STATUSES)].copy()
    df[LABEL_COL] = df[COL_LOAN_STATUS].isin(BAD_STATUSES).astype(int)
    agg = (
        df.groupby(COL_ADDR_STATE)
        .agg(loan_count=(LABEL_COL, "size"), default_rate=(LABEL_COL, "mean"))
        .reset_index()
    )
    return agg[agg["loan_count"] >= 1000].copy()


# load_segment_data 读取热力图与雷达图所需的多维特征
def load_segment_data() -> pd.DataFrame:
    """load_segment_data 一次性读取热力图 / 雷达图共享列。"""
    csv_path = find_lending_club_csv()
    cols = [
        COL_LOAN_STATUS,
        COL_GRADE,
        COL_PURPOSE,
        COL_INT_RATE,
        COL_FICO_LOW,
        COL_FICO_HIGH,
        COL_LOAN_AMNT,
        COL_ANNUAL_INC,
        COL_DTI,
    ]
    df = pd.read_csv(csv_path, usecols=cols, low_memory=False)
    df = df[df[COL_LOAN_STATUS].isin(GOOD_STATUSES | BAD_STATUSES)].copy()
    df[LABEL_COL] = df[COL_LOAN_STATUS].isin(BAD_STATUSES).astype(int)
    df[COL_INT_RATE] = (
        df[COL_INT_RATE].astype(str).str.replace("%", "", regex=False).str.strip()
    )
    df[COL_INT_RATE] = pd.to_numeric(df[COL_INT_RATE], errors="coerce")
    df[COL_FICO_AVG] = (df[COL_FICO_LOW] + df[COL_FICO_HIGH]) / 2
    return df


# plot_state_choropleth 生成美国州级违约率地图
def plot_state_choropleth(out_path: Path) -> None:
    """plot_state_choropleth 用 plotly 静态导出 PNG。"""
    # 1. 数据准备
    state_df = load_state_default()
    # 2. 优先尝试 plotly + kaleido，失败则降级为 matplotlib
    try:
        import plotly.express as px  # type: ignore

        fig = px.choropleth(
            state_df,
            locations=COL_ADDR_STATE,
            locationmode="USA-states",
            color="default_rate",
            scope="usa",
            color_continuous_scale="YlOrRd",
            range_color=(state_df["default_rate"].min(), state_df["default_rate"].max()),
            labels={"default_rate": "违约率"},
            hover_data={"loan_count": True, "default_rate": ":.2%"},
        )
        fig.update_layout(
            title=dict(text="美国各州贷款违约率 Choropleth（loan_count ≥ 1000）", x=0.5),
            margin=dict(l=10, r=10, t=60, b=10),
            geo=dict(bgcolor="rgba(0,0,0,0)"),
        )
        fig.write_image(str(out_path), width=1200, height=720, scale=2)
        logger.info("Saved %s (plotly)", out_path)
    except Exception as exc:  # noqa: BLE001
        # 3. 降级：用 matplotlib 横向条形图替代地图（同样能展示 50 州差异）
        logger.warning("plotly choropleth 不可用（%s），降级为 matplotlib 排序柱状图", exc)
        fig, ax = plt.subplots(figsize=(10, 14))
        sorted_df = state_df.sort_values("default_rate")
        colors = plt.cm.YlOrRd(
            (sorted_df["default_rate"] - sorted_df["default_rate"].min())
            / (sorted_df["default_rate"].max() - sorted_df["default_rate"].min() + 1e-9)
        )
        ax.barh(sorted_df[COL_ADDR_STATE], sorted_df["default_rate"], color=colors)
        ax.set_xlabel("违约率")
        ax.set_title("美国各州贷款违约率（颜色越深风险越高）")
        for i, (rate, count) in enumerate(zip(sorted_df["default_rate"], sorted_df["loan_count"])):
            ax.text(rate + 0.001, i, f"{rate:.2%} (n={count:,})", va="center", fontsize=8)
        plt.tight_layout()
        plt.savefig(out_path, dpi=130)
        plt.close()
        logger.info("Saved %s (matplotlib fallback)", out_path)


# plot_heatmap_grade_purpose 绘制 Grade × Purpose 风险热力图
def plot_heatmap_grade_purpose(df: pd.DataFrame, out_path: Path) -> None:
    """plot_heatmap_grade_purpose Grade × Purpose 二维违约率矩阵。"""
    # 1. 透视违约率
    pivot = df.pivot_table(
        index=COL_GRADE,
        columns=COL_PURPOSE,
        values=LABEL_COL,
        aggfunc="mean",
    ).sort_index()
    counts = df.pivot_table(
        index=COL_GRADE,
        columns=COL_PURPOSE,
        values=LABEL_COL,
        aggfunc="size",
    ).reindex_like(pivot)
    # 2. 仅保留样本量足够的列
    keep_cols = counts.sum(axis=0).sort_values(ascending=False).head(10).index
    pivot = pivot[keep_cols]
    counts = counts[keep_cols]
    # 3. 绘制热力图
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            cnt = counts.values[i, j]
            if pd.notna(val):
                color = "white" if val > pivot.values[~np.isnan(pivot.values)].mean() else "black"
                ax.text(j, i, f"{val:.1%}\nn={int(cnt):,}", ha="center", va="center", color=color, fontsize=7)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("违约率")
    ax.set_title("Grade × Purpose 风险热力图（Top 10 用途，cell=违约率/样本数）")
    ax.set_xlabel("贷款用途")
    ax.set_ylabel("信用等级")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()
    logger.info("Saved %s", out_path)


# plot_heatmap_fico_interest FICO × Interest 二维热力图
def plot_heatmap_fico_interest(df: pd.DataFrame, out_path: Path) -> None:
    """plot_heatmap_fico_interest FICO × 利率 二维违约率矩阵。"""
    # 1. 离散化两维
    sub = df.dropna(subset=[COL_FICO_AVG, COL_INT_RATE]).copy()
    sub["fico_bin"] = pd.cut(sub[COL_FICO_AVG], bins=FICO_BINS, include_lowest=True)
    sub["int_bin"] = pd.cut(sub[COL_INT_RATE], bins=INT_RATE_BINS, include_lowest=True)
    pivot = sub.pivot_table(index="int_bin", columns="fico_bin", values=LABEL_COL, aggfunc="mean")
    counts = sub.pivot_table(index="int_bin", columns="fico_bin", values=LABEL_COL, aggfunc="size")
    # 2. 绘图：注意利率高在上方更直观，所以反转纵轴
    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto", origin="lower")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(c) for c in pivot.columns], rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(i) for i in pivot.index])
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            cnt = counts.values[i, j]
            if pd.notna(val):
                color = "white" if val > 0.25 else "black"
                ax.text(j, i, f"{val:.0%}\n{int(cnt):,}", ha="center", va="center", color=color, fontsize=7)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("违约率")
    ax.set_title("FICO × 利率 风险象限矩阵（高利率+低 FICO = 极端风险）")
    ax.set_xlabel("FICO 分箱")
    ax.set_ylabel("利率分箱（%）")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()
    logger.info("Saved %s", out_path)


# plot_model_comparison ROC / PR / KS / Calibration / Lift-Gain 多模型对比
def plot_model_comparison() -> None:
    """plot_model_comparison 四张行业级模型评估图。"""
    if not MODEL_TEST_PREDICTIONS_CSV.exists():
        logger.warning("缺失 %s，跳过模型对比图", MODEL_TEST_PREDICTIONS_CSV)
        return
    # 1. 加载预测结果
    pred = pd.read_csv(MODEL_TEST_PREDICTIONS_CSV)
    y = pred["y_true"].values
    models = {"Logistic Regression": pred["lr_proba"].values, "XGBoost": pred["xgb_proba"].values}
    palette = {"Logistic Regression": "#1f77b4", "XGBoost": "#d62728"}

    # 2. ROC 对比
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, proba in models.items():
        fpr, tpr, _ = roc_curve(y, proba)
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, label=f"{name} (AUC={roc_auc:.4f})", color=palette[name], lw=2)
        ax.fill_between(fpr, 0, tpr, color=palette[name], alpha=0.06)
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC 曲线对比：LR vs XGBoost")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ADV_ROC_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_ROC_PNG)

    # 3. PR 对比
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, proba in models.items():
        precision, recall, _ = precision_recall_curve(y, proba)
        ap = average_precision_score(y, proba)
        ax.plot(recall, precision, label=f"{name} (AP={ap:.4f})", color=palette[name], lw=2)
    ax.axhline(y.mean(), ls="--", color="gray", label=f"baseline (P={y.mean():.4f})")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall 曲线对比（不平衡数据更具参考性）")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ADV_PR_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_PR_PNG)

    # 4. KS 曲线
    fig, ax = plt.subplots(figsize=(8, 6))
    for name, proba in models.items():
        order = np.argsort(-proba)
        cum_pos = np.cumsum(y[order]) / max(y.sum(), 1)
        cum_neg = np.cumsum(1 - y[order]) / max((1 - y).sum(), 1)
        x = np.linspace(0, 1, len(order))
        ks_diff = cum_pos - cum_neg
        ks_idx = int(np.argmax(ks_diff))
        ks_val = ks_diff[ks_idx]
        ax.plot(x, cum_pos, color=palette[name], lw=2, label=f"{name} TPR")
        ax.plot(x, cum_neg, color=palette[name], lw=1, ls="--", alpha=0.6, label=f"{name} FPR")
        ax.vlines(x[ks_idx], cum_neg[ks_idx], cum_pos[ks_idx], color=palette[name], lw=2, alpha=0.7)
        ax.text(x[ks_idx] + 0.01, (cum_pos[ks_idx] + cum_neg[ks_idx]) / 2, f"KS={ks_val:.3f}", color=palette[name])
    ax.set_xlabel("样本累积比例（按预测概率降序）")
    ax.set_ylabel("累积正/负样本占比")
    ax.set_title("KS 曲线：累积 TPR-FPR 最大间距")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ADV_KS_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_KS_PNG)

    # 5. 校准曲线（reliability diagram）
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, proba in models.items():
        prob_true, prob_pred = calibration_curve(y, proba, n_bins=15, strategy="quantile")
        ax.plot(prob_pred, prob_true, marker="o", lw=2, label=name, color=palette[name])
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="完美校准")
    ax.set_xlabel("预测违约概率（分箱均值）")
    ax.set_ylabel("实际违约率")
    ax.set_title("Calibration / Reliability Diagram")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ADV_CALIBRATION_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_CALIBRATION_PNG)

    # 6. Lift / Gain Chart
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for name, proba in models.items():
        order = np.argsort(-proba)
        y_sorted = y[order]
        cum_pos = np.cumsum(y_sorted) / max(y.sum(), 1)
        sample_pct = np.arange(1, len(y_sorted) + 1) / len(y_sorted)
        axes[0].plot(sample_pct, cum_pos, lw=2, label=name, color=palette[name])
        # lift = 累积召回 / 累积样本占比
        with np.errstate(divide="ignore", invalid="ignore"):
            lift = np.where(sample_pct > 0, cum_pos / sample_pct, 1.0)
        axes[1].plot(sample_pct, lift, lw=2, label=name, color=palette[name])
    axes[0].plot([0, 1], [0, 1], "--", color="gray", label="随机基线")
    axes[0].set_xlabel("人群分位（按预测概率降序）")
    axes[0].set_ylabel("累积坏账拦截率（Recall）")
    axes[0].set_title("Gain Chart")
    axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].axhline(1, ls="--", color="gray", label="随机基线")
    axes[1].set_xlabel("人群分位")
    axes[1].set_ylabel("Lift（相对随机的提升倍数）")
    axes[1].set_title("Lift Chart")
    axes[1].legend(); axes[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ADV_LIFT_GAIN_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_LIFT_GAIN_PNG)

    # 7. 混淆矩阵热力图（取阈值 0.3，对应风控常用业务点）
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, (name, proba) in zip(axes, models.items()):
        y_pred = (proba >= 0.3).astype(int)
        cm = confusion_matrix(y, y_pred)
        im = ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=12)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["预测正常", "预测违约"])
        ax.set_yticks([0, 1]); ax.set_yticklabels(["实际正常", "实际违约"])
        ax.set_title(f"{name}（阈值=0.30）\nAUC={roc_auc_score(y, proba):.4f}")
    plt.tight_layout()
    plt.savefig(ADV_CONFUSION_MATRIX_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_CONFUSION_MATRIX_PNG)


# plot_grade_radar 借款人画像雷达图
def plot_grade_radar(df: pd.DataFrame, out_path: Path) -> None:
    """plot_grade_radar Grade A-G 在 6 个维度上的归一化对比。"""
    # 1. 6 维特征聚合
    metrics = {
        "违约率": (LABEL_COL, "mean"),
        "利率": (COL_INT_RATE, "mean"),
        "贷款金额": (COL_LOAN_AMNT, "mean"),
        "DTI": (COL_DTI, "mean"),
        "FICO（反向）": (COL_FICO_AVG, "mean"),
        "年收入（反向）": (COL_ANNUAL_INC, "mean"),
    }
    agg = pd.DataFrame({k: df.groupby(COL_GRADE)[v[0]].agg(v[1]) for k, v in metrics.items()})
    agg = agg.sort_index()
    # 2. FICO/年收入越高反而风险越低 → 反转
    agg["FICO（反向）"] = agg["FICO（反向）"].max() + agg["FICO（反向）"].min() - agg["FICO（反向）"]
    agg["年收入（反向）"] = agg["年收入（反向）"].max() + agg["年收入（反向）"].min() - agg["年收入（反向）"]
    # 3. 列归一化到 [0, 1]
    norm = (agg - agg.min()) / (agg.max() - agg.min() + 1e-9)
    # 4. 绘制极坐标雷达
    labels = list(norm.columns)
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    cmap = plt.cm.plasma
    for i, grade in enumerate(norm.index):
        values = norm.loc[grade].tolist()
        values += values[:1]
        color = cmap(i / max(len(norm.index) - 1, 1))
        ax.plot(angles, values, lw=2, label=f"Grade {grade}", color=color)
        ax.fill(angles, values, alpha=0.08, color=color)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_yticklabels([])
    ax.set_title("借款人风险画像雷达图：Grade A-G 多维对比", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05), fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()
    logger.info("Saved %s", out_path)


def main():
    """main 进阶可视化主流程
    1. 输出目录；
    2. 州地图；
    3. 二维热力图（共享 segment 数据）；
    4. 多模型对比；
    5. 雷达图。
    """
    # 1. 输出目录
    ADVANCED_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    # 2. 州级 Choropleth
    plot_state_choropleth(ADV_STATE_CHOROPLETH_PNG)
    # 3. 二维热力图（一次读取，两次复用）
    seg = load_segment_data()
    plot_heatmap_grade_purpose(seg, ADV_GRADE_PURPOSE_HEATMAP_PNG)
    plot_heatmap_fico_interest(seg, ADV_FICO_INTEREST_HEATMAP_PNG)
    # 4. 模型对比五图
    plot_model_comparison()
    # 5. 借款人画像雷达
    plot_grade_radar(seg, ADV_GRADE_RADAR_PNG)


if __name__ == "__main__":
    main()
