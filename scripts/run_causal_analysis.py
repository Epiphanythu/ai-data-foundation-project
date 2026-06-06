"""run_causal_analysis.py 因果推断与反事实解释模块
提供双重差分法(DID)、工具变量法、反事实预测等因果分析功能。
"""
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
from scipy import stats
from sklearn.linear_model import LinearRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODEL_XGB_PATH,
    TABLES_DIR,
)
from scripts._model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class CausalAnalyzer:
    """因果分析器类，提供多种因果推断方法"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.results = {}
    
    def did_analysis(
        self,
        treatment_col: str,
        outcome_col: str = LABEL_COL,
        time_col: str = "issue_year",
        control_vars: Optional[list[str]] = None,
    ) -> dict:
        """双重差分法(DID)分析"""
        logger.info(f"Performing DID analysis: treatment={treatment_col}, outcome={outcome_col}")
        
        df = self.df.copy()
        if control_vars is None:
            control_vars = []
        
        time_values = sorted(df[time_col].unique())
        mid_point = len(time_values) // 2
        pre_period = time_values[:mid_point]
        post_period = time_values[mid_point:]
        
        df["post_treatment"] = df[time_col].isin(post_period).astype(int)
        df["did_term"] = df[treatment_col] * df["post_treatment"]
        
        features = [treatment_col, "post_treatment", "did_term"] + control_vars
        X = df[features].fillna(0)
        y = df[outcome_col]
        
        model = LinearRegression()
        model.fit(X, y)
        
        coefs = pd.Series(model.coef_, index=features)
        did_effect = coefs["did_term"]
        did_pvalue = self._calculate_pvalue(model, X, y, "did_term", features)
        
        result = {
            "method": "DID",
            "treatment_col": treatment_col,
            "outcome_col": outcome_col,
            "did_effect": float(did_effect),
            "did_pvalue": float(did_pvalue),
            "coefficients": coefs.to_dict(),
            "pre_period": pre_period,
            "post_period": post_period,
            "sample_size": len(df),
        }
        
        self.results["did"] = result
        logger.info(f"DID effect: {did_effect:.4f}, p-value: {did_pvalue:.4f}")
        return result
    
    def instrumental_variable(
        self,
        iv_col: str,
        treatment_col: str,
        outcome_col: str = LABEL_COL,
        control_vars: Optional[list[str]] = None,
    ) -> dict:
        """工具变量法(IV)分析"""
        logger.info(f"Performing IV analysis: iv={iv_col}, treatment={treatment_col}")
        
        df = self.df.copy()
        if control_vars is None:
            control_vars = []
        
        # 第一阶段
        stage1_features = [iv_col] + control_vars
        X1 = df[stage1_features].fillna(0)
        y1 = df[treatment_col].fillna(0)
        
        stage1_model = LinearRegression()
        stage1_model.fit(X1, y1)
        df["treatment_pred"] = stage1_model.predict(X1)
        
        # 第二阶段
        stage2_features = ["treatment_pred"] + control_vars
        X2 = df[stage2_features].fillna(0)
        y2 = df[outcome_col]
        
        stage2_model = LinearRegression()
        stage2_model.fit(X2, y2)
        
        iv_effect = stage2_model.coef_[0]
        iv_pvalue = self._calculate_pvalue(stage2_model, X2, y2, "treatment_pred", stage2_features)
        
        y1_pred = stage1_model.predict(X1)
        ss_tot = ((y1 - y1.mean()) ** 2).sum()
        ss_res = ((y1 - y1_pred) ** 2).sum()
        r_squared = 1 - ss_res / ss_tot
        n = len(df)
        k = len(stage1_features)
        f_stat = (r_squared / (1 - r_squared)) * ((n - k - 1) / k)
        
        result = {
            "method": "IV",
            "iv_col": iv_col,
            "treatment_col": treatment_col,
            "outcome_col": outcome_col,
            "iv_effect": float(iv_effect),
            "iv_pvalue": float(iv_pvalue),
            "first_stage_r2": float(r_squared),
            "first_stage_f_stat": float(f_stat),
            "sample_size": len(df),
        }
        
        self.results["iv"] = result
        logger.info(f"IV effect: {iv_effect:.4f}, p-value: {iv_pvalue:.4f}, F-stat: {f_stat:.2f}")
        return result
    
    def _calculate_pvalue(self, model, X, y, target_feature, features):
        """计算回归系数的 p 值"""
        n = len(y)
        k = len(features)
        y_pred = model.predict(X)
        residuals = y - y_pred
        mse = (residuals ** 2).sum() / (n - k - 1)
        X_with_intercept = np.column_stack([np.ones(n), X])
        cov_matrix = mse * np.linalg.inv(X_with_intercept.T @ X_with_intercept)
        target_idx = features.index(target_feature) + 1
        se = np.sqrt(cov_matrix[target_idx, target_idx])
        coef = model.coef_[features.index(target_feature)]
        t_stat = coef / se
        pvalue = 2 * (1 - stats.t.cdf(np.abs(t_stat), df=n - k - 1))
        return pvalue
    
    def mediation_analysis(
        self,
        treatment_col: str,
        mediator_col: str,
        outcome_col: str = LABEL_COL,
        control_vars: Optional[list[str]] = None,
    ) -> dict:
        """中介分析"""
        logger.info(f"Performing mediation analysis: treatment={treatment_col}, mediator={mediator_col}")
        
        df = self.df.copy()
        if control_vars is None:
            control_vars = []
        
        total_features = [treatment_col] + control_vars
        X_total = df[total_features].fillna(0)
        y = df[outcome_col]
        total_model = LinearRegression()
        total_model.fit(X_total, y)
        total_effect = total_model.coef_[0]
        
        direct_features = [treatment_col, mediator_col] + control_vars
        X_direct = df[direct_features].fillna(0)
        direct_model = LinearRegression()
        direct_model.fit(X_direct, y)
        direct_effect = direct_model.coef_[0]
        
        indirect_effect = total_effect - direct_effect
        mediation_ratio = indirect_effect / total_effect if total_effect != 0 else 0
        
        result = {
            "method": "mediation",
            "treatment_col": treatment_col,
            "mediator_col": mediator_col,
            "outcome_col": outcome_col,
            "total_effect": float(total_effect),
            "direct_effect": float(direct_effect),
            "indirect_effect": float(indirect_effect),
            "mediation_ratio": float(mediation_ratio),
            "sample_size": len(df),
        }
        
        self.results["mediation"] = result
        logger.info(f"Mediation: total={total_effect:.4f}, direct={direct_effect:.4f}, indirect={indirect_effect:.4f}, ratio={mediation_ratio:.2%}")
        return result


class CounterfactualExplainer:
    """反事实解释器"""
    
    def __init__(self, model_path: Path):
        self.model = joblib.load(model_path)
        self.df = None
        logger.info(f"Loaded model from {model_path}")
    
    def generate_counterfactual(
        self,
        X: pd.DataFrame,
        target_feature: str,
        target_values: list,
    ) -> pd.DataFrame:
        """生成反事实预测"""
        results = []
        original_value = X[target_feature].values[0] if len(X) == 1 else None
        original_pred = self.model.predict_proba(X)[:, 1][0] if len(X) == 1 else None
        
        for value in target_values:
            X_counterfactual = X.copy()
            X_counterfactual[target_feature] = value
            pred = self.model.predict_proba(X_counterfactual)[:, 1][0]
            pred_class = 1 if pred >= 0.5 else 0
            
            results.append({
                "feature": target_feature,
                "original_value": original_value,
                "counterfactual_value": value,
                "original_prediction": original_pred,
                "counterfactual_prediction": float(pred),
                "predicted_class": pred_class,
                "probability_change": float(pred - original_pred) if original_pred else None,
            })
        
        return pd.DataFrame(results)
    
    def find_minimal_change(
        self,
        X: pd.DataFrame,
        target_feature: str,
        desired_outcome: int = 0,
        step_size: float = 0.01,
        max_iter: int = 100,
    ) -> dict:
        """寻找使预测结果改变的最小特征变化量"""
        original_pred = self.model.predict_proba(X)[:, 1][0]
        original_value = X[target_feature].values[0]
        current_value = original_value
        current_class = 1 if original_pred >= 0.5 else 0
        
        if current_class == desired_outcome:
            return {
                "feature": target_feature,
                "original_value": original_value,
                "original_prediction": float(original_pred),
                "desired_outcome": desired_outcome,
                "message": "当前预测已满足期望结果",
                "minimal_change": 0.0,
                "new_value": original_value,
                "new_prediction": float(original_pred),
            }
        
        feature_range = (self.df[target_feature].min(), self.df[target_feature].max()) if hasattr(self, 'df') else (original_value - 100, original_value + 100)
        
        for _ in range(max_iter):
            if desired_outcome == 0:
                current_value -= step_size * (feature_range[1] - feature_range[0])
            else:
                current_value += step_size * (feature_range[1] - feature_range[0])
            
            current_value = max(feature_range[0], min(feature_range[1], current_value))
            
            X_counterfactual = X.copy()
            X_counterfactual[target_feature] = current_value
            new_pred = self.model.predict_proba(X_counterfactual)[:, 1][0]
            new_class = 1 if new_pred >= 0.5 else 0
            
            if new_class == desired_outcome:
                return {
                    "feature": target_feature,
                    "original_value": original_value,
                    "original_prediction": float(original_pred),
                    "desired_outcome": desired_outcome,
                    "minimal_change": float(current_value - original_value),
                    "new_value": float(current_value),
                    "new_prediction": float(new_pred),
                    "message": f"通过将 {target_feature} 从 {original_value:.2f} 调整为 {current_value:.2f}，预测结果从 {current_class} 变为 {desired_outcome}",
                }
        
        return {
            "feature": target_feature,
            "original_value": original_value,
            "original_prediction": float(original_pred),
            "desired_outcome": desired_outcome,
            "message": f"在 {max_iter} 次迭代内未找到使预测结果改变的特征值",
            "minimal_change": None,
            "new_value": None,
            "new_prediction": None,
        }


def run_causal_analysis():
    """运行因果分析主流程"""
    logger.info("Starting causal analysis...")
    
    df = build_training_sample(sample_size=50000)
    logger.info(f"Loaded data: {df.shape}")
    
    analyzer = CausalAnalyzer(df)
    
    df["high_rate_treatment"] = (df["int_rate"] > df["int_rate"].median()).astype(int)
    analyzer.df = df
    
    did_result = analyzer.did_analysis(
        treatment_col="high_rate_treatment",
        outcome_col=LABEL_COL,
        control_vars=["fico_avg", "dti", "annual_inc"]
    )
    
    iv_result = analyzer.instrumental_variable(
        iv_col="fico_avg",
        treatment_col="int_rate",
        outcome_col=LABEL_COL,
        control_vars=["dti", "annual_inc"]
    )
    
    mediation_result = analyzer.mediation_analysis(
        treatment_col="int_rate",
        mediator_col="dti",
        outcome_col=LABEL_COL,
        control_vars=["fico_avg", "annual_inc"]
    )
    
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([did_result]).to_csv(TABLES_DIR / "causal_did_result.csv", index=False)
    pd.DataFrame([iv_result]).to_csv(TABLES_DIR / "causal_iv_result.csv", index=False)
    pd.DataFrame([mediation_result]).to_csv(TABLES_DIR / "causal_mediation_result.csv", index=False)
    
    logger.info("Causal analysis completed. Results saved.")
    return analyzer.results


def run_counterfactual_examples():
    """运行反事实解释示例"""
    logger.info("Starting counterfactual explanation...")
    
    if not MODEL_XGB_PATH.exists():
        logger.warning(f"Model not found: {MODEL_XGB_PATH}")
        return None
    
    df = build_training_sample(sample_size=1000)
    explainer = CounterfactualExplainer(MODEL_XGB_PATH)
    explainer.df = df
    
    sample_idx = 0
    X_sample = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].iloc[[sample_idx]]
    
    key_features = ["fico_avg", "int_rate", "dti", "annual_inc"]
    cf_report = pd.DataFrame()
    
    for feature in key_features:
        if feature not in X_sample.columns:
            continue
        min_val = df[feature].min()
        max_val = df[feature].max()
        target_values = np.linspace(min_val, max_val, 5).tolist()
        
        cf_results = explainer.generate_counterfactual(X_sample, feature, target_values)
        cf_report = pd.concat([cf_report, cf_results], ignore_index=True)
    
    min_change_results = []
    for feature in ["fico_avg", "int_rate"]:
        result = explainer.find_minimal_change(X_sample, feature, desired_outcome=0)
        min_change_results.append(result)
    
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    cf_report.to_csv(TABLES_DIR / "counterfactual_report.csv", index=False)
    pd.DataFrame(min_change_results).to_csv(TABLES_DIR / "counterfactual_min_change.csv", index=False)
    
    logger.info("\n=== 反事实解释示例 ===")
    logger.info(f"原始违约概率: {cf_report['original_prediction'].iloc[0]:.4f}")
    
    fico_results = cf_report[cf_report["feature"] == "fico_avg"]
    logger.info("\nFICO 分数变化的影响:")
    for _, row in fico_results.iterrows():
        logger.info(f"  FICO={row['counterfactual_value']:.0f} -> 违约概率={row['counterfactual_prediction']:.4f} (变化={row['probability_change']:+.4f})")
    
    rate_results = cf_report[cf_report["feature"] == "int_rate"]
    logger.info("\n利率变化的影响:")
    for _, row in rate_results.iterrows():
        logger.info(f"  利率={row['counterfactual_value']:.2f}% -> 违约概率={row['counterfactual_prediction']:.4f} (变化={row['probability_change']:+.4f})")
    
    logger.info("Counterfactual explanation completed. Results saved.")
    return cf_report


def plot_causal_results():
    """绘制因果分析结果可视化"""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    did_path = TABLES_DIR / "causal_did_result.csv"
    if did_path.exists():
        did_df = pd.read_csv(did_path)
        
        plt.figure(figsize=(8, 5))
        coefs = pd.Series(did_df["coefficients"].iloc[0]).drop("did_term")
        coefs["DID效应"] = did_df["did_effect"].iloc[0]
        coefs.plot(kind="bar", color=["#5599cc", "#5599cc", "#5599cc", "#e74c3c"])
        plt.axhline(0, color="gray", linestyle="--")
        plt.title("DID 分析系数估计")
        plt.ylabel("系数值")
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / "causal_did_plot.png", dpi=120)
        plt.close()
        logger.info("Saved DID plot")
    
    mediation_path = TABLES_DIR / "causal_mediation_result.csv"
    if mediation_path.exists():
        mediation_df = pd.read_csv(mediation_path)
        
        plt.figure(figsize=(10, 4))
        effects = [
            ("总效应", mediation_df["total_effect"].iloc[0]),
            ("直接效应", mediation_df["direct_effect"].iloc[0]),
            ("间接效应", mediation_df["indirect_effect"].iloc[0]),
        ]
        labels, values = zip(*effects)
        colors = ["#3498db", "#2ecc71", "#f39c12"]
        plt.bar(labels, values, color=colors)
        plt.axhline(0, color="gray", linestyle="--")
        plt.title("中介分析效应分解")
        plt.ylabel("效应值")
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / "causal_mediation_plot.png", dpi=120)
        plt.close()
        logger.info("Saved mediation plot")


def main():
    causal_results = run_causal_analysis()
    cf_results = run_counterfactual_examples()
    plot_causal_results()
    
    logger.info("\n=== 分析完成 ===")
    if causal_results.get("did"):
        logger.info(f"DID 效应: {causal_results['did']['did_effect']:.4f} (p={causal_results['did']['did_pvalue']:.4f})")
    if causal_results.get("iv"):
        logger.info(f"IV 效应: {causal_results['iv']['iv_effect']:.4f} (p={causal_results['iv']['iv_pvalue']:.4f})")
    if causal_results.get("mediation"):
        logger.info(f"中介效应比例: {causal_results['mediation']['mediation_ratio']:.2%}")


if __name__ == "__main__":
    main()