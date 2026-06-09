"""llm/llm_rag.py 项目产物 RAG 检索与引用式问答

1. 扫描 outputs/tables 下的 markdown 发现文档；
2. 切分成段落，构建轻量 TF-IDF 向量索引（不依赖大模型）；
3. 检索 Top-K 证据片段，拼装为 LLM Prompt；
4. 调用 LLM 生成带 [编号] 引用的回答。
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import (  # noqa: E402
    LLM_RAG_CHUNK_OVERLAP,
    LLM_RAG_CHUNK_SIZE,
    LLM_RAG_DOC_SUFFIXES,
    LLM_RAG_TOP_K,
    SYSTEM_PROMPT_RAG,
)
from constant.paths import (  # noqa: E402
    LLM_RAG_DOCS_JSON,
    LLM_RAG_INDEX_DIR,
    OUTPUTS_DIR,
    REPORTS_DIR,
    TABLES_DIR,
)
from common.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 1. 默认扫描的文档根目录
RAG_SOURCE_ROOTS: tuple[Path, ...] = (TABLES_DIR, REPORTS_DIR, OUTPUTS_DIR.parent / "AGENTS.md")


@dataclass
class RagDoc:
    """RagDoc RAG 文档片段元数据"""
    doc_id: int
    source: str
    chunk_index: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        """to_dict 序列化为字典，用于持久化"""
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "text": self.text,
        }


def _split_markdown(text: str, size: int, overlap: int) -> list[str]:
    """_split_markdown 按段落切分 markdown，再按字符数滑窗，避免切碎句子"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 1 <= size:
            buffer = f"{buffer}\n{paragraph}".strip()
            continue
        if buffer:
            chunks.append(buffer)
        if len(paragraph) <= size:
            buffer = paragraph
        else:
            # 1. 单段过长时按字符滑窗切片
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + size])
                start += max(size - overlap, 1)
            buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def _iter_source_files(roots: tuple[Path, ...]) -> list[Path]:
    """_iter_source_files 收集所有候选文档文件"""
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in LLM_RAG_DOC_SUFFIXES:
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in LLM_RAG_DOC_SUFFIXES:
                files.append(path)
    return sorted(set(files))


def build_index(roots: tuple[Path, ...] = RAG_SOURCE_ROOTS) -> list[RagDoc]:
    """build_index 扫描指定目录下的 markdown 文档，切片并构建索引文件"""
    # 1. 扫描原始文档并切片
    docs: list[RagDoc] = []
    doc_id = 0
    for path in _iter_source_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not text.strip():
            continue
        chunks = _split_markdown(text, LLM_RAG_CHUNK_SIZE, LLM_RAG_CHUNK_OVERLAP)
        rel = str(path.relative_to(OUTPUTS_DIR.parent))
        for index, chunk in enumerate(chunks):
            docs.append(RagDoc(doc_id=doc_id, source=rel, chunk_index=index, text=chunk))
            doc_id += 1
    # 2. 持久化（仅文本，不缓存向量，避免依赖 sklearn 序列化）
    LLM_RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    LLM_RAG_DOCS_JSON.write_text(
        json.dumps([doc.to_dict() for doc in docs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("RAG index built: %d chunks from %d roots → %s", len(docs), len(roots), LLM_RAG_DOCS_JSON)
    return docs


def load_docs() -> list[RagDoc]:
    """load_docs 加载已持久化的索引；不存在时实时构建"""
    if not LLM_RAG_DOCS_JSON.exists():
        return build_index()
    raw = json.loads(LLM_RAG_DOCS_JSON.read_text(encoding="utf-8"))
    return [RagDoc(**item) for item in raw]


def _build_vectorizer(docs: list[RagDoc]):
    """_build_vectorizer 用 sklearn 构建 TF-IDF 向量化器"""
    from sklearn.feature_extraction.text import TfidfVectorizer

    # 1. 中文按字符 1-2gram，英文按 word，混合时使用 char_wb 平衡
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 3),
        max_features=20000,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([doc.text for doc in docs])
    return vectorizer, matrix


def search(question: str, top_k: int = LLM_RAG_TOP_K) -> list[tuple[RagDoc, float]]:
    """search 检索与问题最相关的 Top-K 文档片段"""
    docs = load_docs()
    if not docs:
        return []
    vectorizer, matrix = _build_vectorizer(docs)
    query_vec = vectorizer.transform([question])
    # 1. 余弦相似度（TF-IDF 已 L2 归一化，dot = cosine）
    scores = (matrix @ query_vec.T).toarray().ravel()
    if not scores.size:
        return []
    order = scores.argsort()[::-1][:top_k]
    return [(docs[idx], float(scores[idx])) for idx in order if scores[idx] > 0]


def _format_context(matches: list[tuple[RagDoc, float]]) -> str:
    """_format_context 拼装可被 LLM 引用的证据上下文"""
    if not matches:
        return "（未检索到相关证据）"
    lines = []
    for index, (doc, score) in enumerate(matches, start=1):
        snippet = doc.text.replace("\n", " ").strip()
        if len(snippet) > 600:
            snippet = snippet[:600] + "..."
        lines.append(f"[{index}] 来源：{doc.source}（相关度 {score:.3f}）\n{snippet}")
    return "\n\n".join(lines)


def answer(question: str, top_k: int = LLM_RAG_TOP_K) -> dict[str, Any]:
    """answer 检索 + LLM 生成带引用的最终答复"""
    # 1. 检索证据
    matches = search(question, top_k=top_k)
    context = _format_context(matches)
    # 2. 构造 prompt 并调用 LLM
    user_prompt = (
        f"用户问题：{question}\n\n"
        f"以下是已检索到的项目证据片段，请只基于这些证据作答，并在结论后用 [编号] 标注引用：\n\n"
        f"{context}"
    )
    client = LLMClient()
    text = client.chat(SYSTEM_PROMPT_RAG, user_prompt, temperature=0.1, max_tokens=900)
    # 3. 返回结构化结果，便于 Dashboard 复用
    return {
        "question": question,
        "answer": text.strip(),
        "evidence": [
            {
                "index": index,
                "source": doc.source,
                "chunk_index": doc.chunk_index,
                "score": score,
                "snippet": doc.text,
            }
            for index, (doc, score) in enumerate(matches, start=1)
        ],
    }


def main():
    """main CLI 入口：构建索引或执行一次检索式问答"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="构建/刷新 RAG 索引")
    parser.add_argument("--question", type=str, default="", help="自然语言问题")
    parser.add_argument("--top-k", type=int, default=LLM_RAG_TOP_K)
    args = parser.parse_args()

    if args.build:
        build_index()
        return
    if not args.question:
        parser.error("--question 不能为空（或使用 --build 仅构建索引）")
    result = answer(args.question, top_k=args.top_k)
    print("Q:", result["question"])
    print("A:", result["answer"])
    print("\n证据：")
    for item in result["evidence"]:
        print(f"  [{item['index']}] {item['source']} (score={item['score']:.3f})")


if __name__ == "__main__":
    main()
