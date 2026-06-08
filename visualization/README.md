# visualization 独立可视化模块

`visualization/` 是独立大模块，和 `dashboard/`、`llm/` 并列。它负责批量生成高质量图表，不承担交互页面职责。

## 职责边界

- 负责：图表生产、统一风格、美化输出、汇报用图片生成。
- 不负责：Streamlit 页面交互，这属于 `dashboard/`。
- 不负责：自然语言解释，这属于 `llm/`。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `build_advanced_visualizations.py` | 生成 ROC、PR、KS、Calibration、热力图、SHAP 高级图 | `outputs/figures/advanced/` |
| `build_beautiful_visualizations.py` | 生成统一风格的展示型图表 | `outputs/figures/` |

## 与 Dashboard 的关系

```text
visualization/ 生成图表 → outputs/figures/ → dashboard/ 读取并展示
```

Dashboard 是展示层，Visualization 是图表生产层，两者不是包含关系。
