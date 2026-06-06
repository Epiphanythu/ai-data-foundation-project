"""build_beautiful_visualizations.py 专业级可视化美化模块"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from constant.columns import LABEL_COL
from constant.model import NUMERIC_FEATURES
from constant.paths import FIGURES_DIR
from scripts._model_data import build_training_sample

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

COLOR_SCHEMES = {
    "primary": "#3B82F6", "secondary": "#10B981", "accent": "#F59E0B",
    "danger": "#EF4444", "warning": "#F97316", "success": "#10B981",
    "neutral": "#6B7280", "dark": "#1F2937", "light": "#F3F4F6",
}

GRADIENTS = {
    "blue": ["#60A5FA", "#3B82F6", "#2563EB", "#1D4ED8"],
    "green": ["#34D399", "#10B981", "#059669", "#047857"],
    "orange": ["#FDBA74", "#F59E0B", "#D97706", "#B45309"],
}

def set_plot_style():
    plt.rcParams.update({
        "font.family": ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"],
        "font.size": 12, "axes.titlesize": 14, "axes.labelsize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 11,
        "lines.linewidth": 2, "axes.linewidth": 1,
        "axes.edgecolor": COLOR_SCHEMES["neutral"], "axes.facecolor": "white",
        "grid.color": COLOR_SCHEMES["light"], "grid.linewidth": 1,
        "figure.facecolor": "white", "savefig.facecolor": "white",
        "figure.autolayout": True, "figure.dpi": 120,
    })

class BeautifulVisualizer:
    def __init__(self):
        set_plot_style()
    
    def plot_default_rate(self, df, feature, title, output_path):
        plt.figure(figsize=(10, 5))
        agg_df = df.groupby(feature)[LABEL_COL].mean().sort_values(ascending=False)
        bars = plt.bar(agg_df.index, agg_df.values, color=GRADIENTS["orange"], edgecolor=COLOR_SCHEMES["dark"], linewidth=1)
        
        for bar in bars:
            plt.text(bar.get_x() + bar.get_width()/2., bar.get_height(), f"{bar.get_height():.1%}", ha="center", va="bottom")
        
        plt.title(title, fontsize=14, fontweight="bold", color=COLOR_SCHEMES["dark"])
        plt.xlabel(feature.replace("_", " ").title())
        plt.ylabel("违约率")
        plt.xticks(rotation=45, ha="right")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()
    
    def plot_correlation(self, df, output_path):
        plt.figure(figsize=(12, 10))
        corr = df[NUMERIC_FEATURES].corr()
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, cmap="coolwarm", vmin=-1, vmax=1, annot=True, fmt=".2f", square=True)
        plt.title("特征相关性热力图", fontsize=14, fontweight="bold", color=COLOR_SCHEMES["dark"])
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()
    
    def plot_distribution(self, df, feature, output_path):
        plt.figure(figsize=(10, 5))
        if feature in NUMERIC_FEATURES:
            sns.histplot(df[feature], color=COLOR_SCHEMES["primary"], kde=True, bins=30, edgecolor=COLOR_SCHEMES["dark"])
        else:
            counts = df[feature].value_counts()
            plt.bar(counts.index, counts.values, color=GRADIENTS["blue"], edgecolor=COLOR_SCHEMES["dark"])
        plt.title(f"{feature} 分布", fontsize=14, fontweight="bold", color=COLOR_SCHEMES["dark"])
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()

def run():
    logger.info("Generating beautiful visualizations...")
    df = build_training_sample(sample_size=10000)
    viz = BeautifulVisualizer()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    viz.plot_default_rate(df, "grade", "不同信用等级的违约率", FIGURES_DIR / "beautiful_default_rate_by_grade.png")
    viz.plot_default_rate(df, "purpose", "不同贷款用途的违约率", FIGURES_DIR / "beautiful_default_rate_by_purpose.png")
    viz.plot_correlation(df, FIGURES_DIR / "beautiful_correlation_heatmap.png")
    viz.plot_distribution(df, "fico_avg", FIGURES_DIR / "beautiful_fico_distribution.png")
    viz.plot_distribution(df, "dti", FIGURES_DIR / "beautiful_dti_distribution.png")
    
    logger.info("✅ 美化可视化完成")

if __name__ == "__main__":
    run()
