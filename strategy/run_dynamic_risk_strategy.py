"""run_dynamic_risk_strategy.py 动态阈值机制与组合风控策略模块"""
from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Optional
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from constant.columns import LABEL_COL
from constant.model import CATEGORICAL_FEATURES, NUMERIC_FEATURES, ASSUMED_LGD, ASSUMED_INTEREST_MARGIN
from constant.paths import FIGURES_DIR, MODEL_XGB_PATH, TABLES_DIR
from common.model_data import build_training_sample

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

class DynamicThresholdEngine:
    """动态阈值引擎，根据样本风险水平给出可调整的审批阈值。"""
    def __init__(self, model_path: Path):
        """初始化策略组件，加载模型或规则依赖，供后续策略评估复用。"""
        self.model = joblib.load(model_path)
    
    def calculate_macro_adjusted_threshold(self, macro_indicator, base_threshold=0.5, sensitivity=0.1):
        """根据宏观风险指标动态调整基础审批阈值。"""
        adjustment = -sensitivity * macro_indicator
        return max(0.05, min(0.95, base_threshold + adjustment))
    
    def calculate_segment_threshold(self, X, segment_type="fico", base_threshold=0.5):
        """根据用户分群特征生成差异化审批阈值。"""
        thresholds = pd.Series(base_threshold, index=X.index)
        if segment_type == "fico":
            thresholds = base_threshold - 0.0005 * (X["fico_avg"] - 700)
        elif segment_type == "grade":
            grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}
            thresholds = base_threshold - 0.05 * (3 - X["grade"].map(grade_order).fillna(3))
        return thresholds.clip(0.05, 0.95)
    
    def predict_with_dynamic_threshold(self, X, macro_indicator=None, segment_type="fico", base_threshold=0.5):
        """使用模型概率和动态阈值生成最终违约预测。"""
        proba = self.model.predict_proba(X)[:, 1]
        if macro_indicator is not None:
            base_threshold = self.calculate_macro_adjusted_threshold(macro_indicator, base_threshold)
        thresholds = self.calculate_segment_threshold(X, segment_type, base_threshold)
        return pd.DataFrame({"probability": proba, "threshold": thresholds, "prediction": (proba >= thresholds).astype(int)})

class RuleEngine:
    """规则引擎，封装可解释的人工风控规则。"""
    def __init__(self):
        """初始化策略组件，加载模型或规则依赖，供后续策略评估复用。"""
        self.rules = []
    
    def add_rule(self, name, condition, action="reject", priority=1):
        """向规则引擎添加一条带优先级的风控规则。"""
        self.rules.append({"name": name, "condition": condition, "action": action, "priority": priority})
        self.rules.sort(key=lambda x: x["priority"])
    
    def apply_rules(self, X):
        """逐行应用风控规则，输出规则决策和命中的规则名称。"""
        results = []
        for _, row in X.iterrows():
            decision, triggered_rule = "flag", None
            for rule in self.rules:
                if rule["condition"](row):
                    decision, triggered_rule = rule["action"], rule["name"]
                    break
            results.append({"rule_decision": decision, "triggered_rule": triggered_rule})
        return pd.DataFrame(results, index=X.index)
    
    def load_default_rules(self):
        """加载项目内置的示例风控规则集合。"""
        self.add_rule("high_dti", lambda row: row["dti"] > 43, "reject", 1)
        self.add_rule("low_fico", lambda row: row["fico_avg"] < 600, "reject", 2)
        self.add_rule("verified_high_income", lambda row: row["verification_status"] == "Verified" and row["annual_inc"] >= 150000, "accept", 3)
        self.add_rule("high_grade_low_debt", lambda row: row["grade"] in ["A", "B"] and row["dti"] < 15, "accept", 4)
        self.add_rule("recent_delinq", lambda row: row["delinq_2yrs"] > 2, "flag", 5)

class HybridRiskStrategy:
    """混合风控策略，将模型分数、动态阈值和人工规则组合成最终决策。"""
    def __init__(self, model_path):
        """初始化策略组件，加载模型或规则依赖，供后续策略评估复用。"""
        self.rule_engine = RuleEngine()
        self.rule_engine.load_default_rules()
        self.dynamic_threshold_engine = DynamicThresholdEngine(model_path)
    
    def evaluate_strategy(self, X, y, macro_indicator=None, segment_type="fico", base_threshold=0.5):
        """评估混合风控策略的通过率、坏账率、收益和召回率。"""
        rule_results = self.rule_engine.apply_rules(X)
        ml_mask = rule_results["rule_decision"] == "flag"
        y_pred = (rule_results["rule_decision"] == "reject").astype(int)
        
        if ml_mask.any():
            ml_preds = self.dynamic_threshold_engine.predict_with_dynamic_threshold(X[ml_mask], macro_indicator, segment_type, base_threshold)
            y_pred[ml_mask] = ml_preds["prediction"].values
        
        accepted = y_pred == 0
        profit = accepted.sum() * ASSUMED_INTEREST_MARGIN * X.loc[accepted, "loan_amnt"].mean() - y[accepted].sum() * ASSUMED_LGD * X.loc[accepted, "loan_amnt"].mean()
        
        return {
            "pass_rate": float(accepted.mean()),
            "bad_rate": float(y[accepted].mean()),
            "profit": float(profit),
            "accuracy": float((y_pred == y).mean()),
            "recall": float((y_pred & y).sum() / max(y.sum(), 1)),
        }

def run():
    """运行当前模块的主流程或子脚本，并把关键产物写入输出目录。"""
    if not MODEL_XGB_PATH.exists():
        logger.error("模型文件不存在，请先运行 train_baseline_model.py")
        return
    
    df = build_training_sample(sample_size=20000)
    X, y = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES], df[LABEL_COL]
    strategy = HybridRiskStrategy(MODEL_XGB_PATH)
    
    # 评估不同策略
    baseline = strategy.evaluate_strategy(X, y)
    dynamic = strategy.evaluate_strategy(X, y, macro_indicator=0.05)
    
    # 保存结果
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"strategy": "基准策略", **baseline}, {"strategy": "动态策略", **dynamic}]).to_csv(
        TABLES_DIR / "strategy_comparison.csv", index=False
    )
    
    # 输出结果
    logger.info("\n=== 📊 策略评估结果 ===")
    logger.info(f"基准策略: 通过率={baseline['pass_rate']:.2%}, 坏账率={baseline['bad_rate']:.2%}, 利润={baseline['profit']:,.0f}")
    logger.info(f"动态策略: 通过率={dynamic['pass_rate']:.2%}, 坏账率={dynamic['bad_rate']:.2%}, 利润={dynamic['profit']:,.0f}")

if __name__ == "__main__":
    run()
