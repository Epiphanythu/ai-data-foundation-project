# llm 智能分析模块

`llm/` 负责读取项目产物，提供自然语言问答和自动出图能力。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `llm_qa_system.py` | Text-to-Pandas 问答、受控代码执行、自动出图 | 回答文本、表格、临时图表 |

## 安全边界

- LLM 只能读取注册过的数据源。
- 自动代码执行使用 AST 白名单和黑名单限制。
- 禁止任意文件 IO、网络访问、`exec/eval` 等危险操作。
- 临时图表不进入 Git。

## 配置

LLM 配置来自 `.env` 或环境变量：

```env
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_MODEL=glm-4-plus
```
