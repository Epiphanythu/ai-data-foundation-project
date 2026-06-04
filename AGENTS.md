# AGENTS.md

> 本文件给 Coding Agent / 协作者使用，记录"环境、约束、关键路径、运行方式"。
> 改代码前请通读，避免与既有约定冲突。

---

## 1. 环境管理（必读）

**统一使用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境与依赖**，禁止直接用 `python3 -m pip install` 污染全局解释器。

```bash
# 1. 安装 uv（已安装可跳过）
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. 创建并激活虚拟环境
uv venv
source .venv/bin/activate

# 3. 安装依赖
uv pip install -r requirements.txt
```

**macOS 额外依赖**：XGBoost 需要 OpenMP，安装一次即可：
```bash
brew install libomp
```

**LLM 凭证**（GLM 适配 OpenAI 协议）—— **使用 `.env` 文件**：

```bash
# 1. 复制模板并填入真实 key（.env 已在 .gitignore，不会提交）
cp .env.example .env
# 2. 编辑 .env：
#    OPENAI_API_KEY=<你的 GLM key>
#    OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
#    OPENAI_MODEL=glm-4-plus
```

[constant/llm.py](file:///Users/bytedance/Desktop/DB/constant/llm.py) 会在 `resolve_*` 时自动加载 `.env`，无需手动 export。

---

## 2. 项目结构

```
DB/
├── constant/                  # 所有常量集中管理（路径/列名/模型/LLM）
├── scripts/                   # 数据分析、建模、SHAP、策略、LLM 脚本
│   ├── analyze_lending_club.py
│   ├── build_*.py             # 各类多源融合脚本
│   ├── train_baseline_model.py
│   ├── run_shap_analysis.py
│   ├── run_risk_strategy_simulation.py
│   ├── llm_auto_report.py
│   ├── llm_qa_system.py
│   ├── _model_data.py         # 模型数据共享构造（不落盘缓存）
│   ├── _llm_client.py         # LLM 客户端封装
│   └── run_all_analysis.py    # 一键串联脚本
├── dashboard/app.py           # Streamlit 5-Tab Dashboard
├── data/
│   ├── raw/lending_club/      # 226 万行 Lending Club CSV（手动下载）
│   ├── raw/home_credit/       # Home Credit Default Risk 数据
│   └── external/              # FRED / ERS 数据
└── outputs/
    ├── tables/                # 分析 CSV 与 markdown 发现
    ├── figures/               # 单变量、组合、SHAP、PDP、风控策略图
    ├── models/                # 训练模型 + metrics + 测试预测
    └── reports/               # LLM 自动生成的 markdown 报告
```

**关键约束**：
- ❌ 不在 `data/processed/` 落盘临时缓存，避免临时数据堆积。每次脚本读原始 CSV。
- ❌ 业务实现文件不写魔法值，所有常量放在 `constant/` 包。
- ✅ 函数注释采用 `# 函数名 简述` 风格；方法体内用 `1.` `2.` `3.` 段落注释组织逻辑。
- ✅ 修改函数签名时，必须同步更新所有调用点。

---

## 3. 一键运行

```bash
source .venv/bin/activate
python scripts/run_all_analysis.py
```

会依次执行：
1. Lending Club 单变量分析；
2. FRED 年度宏观融合；
3. ERS 州级融合；
4. 组合风险分层；
5. 州级控制变量分析；
6. 季度宏观融合；
7. **基准模型**（LR + XGBoost）；
8. **SHAP / PDP**；
9. **风控策略模拟**。

---

## 4. 启动 Dashboard

```bash
source .venv/bin/activate
streamlit run dashboard/app.py
# http://localhost:8501
```

5 个 Tab：
1. 数据概览
2. 模型表现（指标表 + 特征重要性）
3. 可解释性（SHAP summary/bar + PDP）
4. 风控策略（图、表、阈值滑块、4 个 Metric）
5. AI 助手（自动报告 + 自然语言问答，需配置 LLM 环境变量）

---

## 5. LLM 能力

```bash
# 自动生成分析报告（落盘 outputs/reports/llm_auto_report.md）
python scripts/llm_auto_report.py

# 自然语言问答（Text-to-Pandas）
python scripts/llm_qa_system.py "违约率最高的 5 个州是哪些？"
```

LLM 调用统一走 [scripts/_llm_client.py](file:///Users/bytedance/Desktop/DB/scripts/_llm_client.py)，参数从 `OPENAI_*` 环境变量解析。问答系统通过黑名单沙箱执行 LLM 生成的 pandas 代码。

---

## 6. 数据规模与参考指标

- 全量 Lending Club：**2,260,701 行**，可用标签 **1,367,578 行**，整体违约率 **21.27%**。
- 当前基准模型（在 1.37M 行上训练）：
  - Logistic Regression：AUC **0.7073** / KS **0.3011**
  - XGBoost：AUC **0.7186** / KS **0.3178**
- 风控策略：阈值 0.15 时通过率 38%、坏账率 8.94%、利润最高 0.0090。

---

## 7. 常见问题

| 现象 | 解决 |
|---|---|
| `libxgboost.dylib could not be loaded` | `brew install libomp` |
| `KeyError: 'default_flag'` | 确认未在 groupby.apply 后失去分组列；新版 pandas 改用按 group 抽样 |
| Dashboard 中文乱码 | matplotlib 已注册 `PingFang SC`，仍乱码可换字体 |
| LLM 调用 401 | 检查 `.env` 中 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 是否填写 |
| `model_train_sample.csv` 又出现 | 已废弃，[scripts/_model_data.py](file:///Users/bytedance/Desktop/DB/scripts/_model_data.py) 不再写缓存 |
