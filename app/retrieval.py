"""
検索（Retrieval）＋回答生成（Generation）＝ RAG の本体。

  質問
    → 質問をベクトル化
    → pgvector で「意味が近い」チャンクを上位k件取得（Retrieval）
    → 取得チャンク＋質問でプロンプトを組み立てる
    → LLMに渡して回答を生成（Generation）
"""

from sqlalchemy.orm import Session

from . import gemini_client
from .config import settings
from .models import Chunk


def search(db: Session, question: str, top_k: int | None = None) -> list[dict]:
    """質問に意味が近いチャンクを上位 top_k 件返す。"""
    top_k = top_k or settings.top_k
    query_vec = gemini_client.embed_query(question)

    # cosine_distance が小さいほど「意味が近い」。昇順に並べて上位を取る。
    rows = (
        db.query(Chunk, Chunk.embedding.cosine_distance(query_vec).label("distance"))
        .order_by("distance")
        .limit(top_k)
        .all()
    )

    results = []
    for chunk, distance in rows:
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                # 類似度（1に近いほど近い）。distance(0〜2) を見やすく変換。
                "similarity": round(1 - distance, 4),
            }
        )
    return results


def build_prompt(question: str, contexts: list[dict]) -> str:
    """取得チャンクを文脈として埋め込んだプロンプトを作る。"""
    context_text = "\n\n".join(
        f"[資料{i + 1}]\n{c['content']}" for i, c in enumerate(contexts)
    )
    return (
        "あなたは社内文書アシスタントです。"
        "以下の資料だけを根拠に、日本語で簡潔に答えてください。"
        "資料に書かれていないことは推測せず、「資料からは分かりません」と答えてください。\n\n"
        f"=== 資料 ===\n{context_text}\n\n"
        f"=== 質問 ===\n{question}\n\n"
        "=== 回答 ==="
    )


def answer(db: Session, question: str, top_k: int | None = None) -> dict:
    """RAGの一連の流れを実行して、回答と根拠を返す。"""
    contexts = search(db, question, top_k)
    if not contexts:
        return {"answer": "まだ文書が取り込まれていません。", "contexts": []}

    prompt = build_prompt(question, contexts)
    generated = gemini_client.generate(prompt)
    return {"answer": generated, "contexts": contexts}
