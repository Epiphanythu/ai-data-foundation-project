"""run_explainability_enhancement.py 决策追溯与可解释性增强模块"""
from __future__ import annotations
import logging
import sys
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from constant.columns import LABEL_COL
from constant.model import CATEGORICAL_FEATURES, NUMERIC_FEATURES, RANDOM_SEED
from constant.paths import FIGURES_DIR, MODEL_XGB_PATH, TABLES_DIR
from scripts._model_data import build_training_sample

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


class DecisionTracker:
    """决策追溯器"""
    def __init__(self):
        self.decision_logs = []
    
    def log_decision(self, application_id, features, probability, threshold, decision, rules=None):
        self.decision_logs.append({
            "timestamp": datetime.now().isoformat(),
            "application_id": application_id,
            "features": features.to_dict(),
            "probability": float(probability),
            "threshold": float(threshold),
            "decision": decision,
            "rules": rules or [],
        })
    
    def export_logs(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.decision_logs, f, ensure_ascii=False, indent=2)
    
    def generate_audit_report(self, filepath):
        df = pd.DataFrame(self.decision_logs)
        report = f"""# 决策审计报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 概览
- 总决策数: {len(df)}
- 通过数: {len(df[df['decision'] == 'accept'])}
- 拒绝数: {len(df[df['decision'] == 'reject'])}
- 通过率: {len(df[df['decision'] == 'accept']) / len(df) * 100:.2f}%
"""
        filepath.write_text(report, encoding="utf-8")


class MultiMethodExplainer:
    """多方法可解释性分析器"""
    def __init__(self, model_path):
        self.model = joblib.load(model_path)
    
    def calculate_importance(self, X, y):
        """计算特征重要性"""
        # 基于模型内置重要性
        if hasattr(self.model, 'feature_importances_'):
            importance = pd.DataFrame({
                "feature": X.columns,
                "importance": self.model.feature_importances_,
            }).sort_values("importance", ascending=False)
            return importance
        return None
    
    def generate_explanation(self, X, sample_idx):
        """生成单个样本的解释"""
        prob = self.model.predict_proba(X.iloc[[sample_idx]])[0, 1]
        pred = self.model.predict(X.iloc[[sample_idx]])[0]
        
        return {
            "probability": float(prob),
            "prediction": int(pred),
            "label": "违约" if pred == 1 else "正常",
            "features": X.iloc[sample_idx].to_dict(),
        }


def run():
    logger.info("Starting explainability enhancement analysis...")
    
    if not MODEL_XGB_PATH.exists():
        logger.error("Model not found")
        return
    
    df = build_training_sample(sample_size=5000)
    X, y = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES], df[LABEL_COL]
    
    # 初始化组件
    tracker = DecisionTracker()
    explainer = MultiMethodExplainer(MODEL_XGB_PATH)
    
    # 记录决策
    for i in range(min(200, len(X))):
        prob = explainer.model.predict_proba(X.iloc[[i]])[0, 1]
        decision = "reject" if prob >= 0.5 else "accept"
        tracker.log_decision(f"APP_{i:06d}", X.iloc[i], prob, 0.5, decision)
    
    # 计算重要性
    importance = explainer.calculate_importance(X, y)
    
    # 保存结果
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tracker.export_logs(TABLES_DIR / "decision_logs.json")
    tracker.generate_audit_report(TABLES_DIR / "decision_audit_report.md")
    if importance is not None:
        importance.to_csv(TABLES_DIR / "feature_importance.csv", index=False)
    
    logger.info("\n=== ✅ 可解释性分析完成 ===")
    logger.info(f"记录决策数: {len(tracker.decision_logs)}")
    logger.info(f"审计报告: outputs/tables/decision_audit_report.md")


if __name__ == "__main__":
    run()
