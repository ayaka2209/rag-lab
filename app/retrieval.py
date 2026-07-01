"""
検索（Retrieval）＋回答生成（Generation）＝ RAG の本体。

  質問
    → 質問をベクトル化
    → pgvector で「意味が近い」チャンクを上位k件取得（Retrieval）
    → 取得チャンク＋質問でプロンプトを組み立てる
    → LLMに渡して回答を生成（Generation）
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import gemini_client
from .config import settings
from .models import Chunk

# ハイブリッド検索で、各検索方式から取る候補数。多めに取ってから融合する。
CANDIDATE_K = 20
# RRF（Reciprocal Rank Fusion）の定数。大きいほど順位差の影響がなだらかになる。定番は60。
RRF_K = 60


def _chunk_to_dict(chunk: Chunk, similarity: float | None = None) -> dict:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "similarity": similarity,
    }


def _vector_ranked(db: Session, query_vec, limit: int) -> list[tuple[Chunk, float]]:
    """ベクトル（意味）で近い順。cosine_distance が小さいほど近い。"""
    rows = (
        db.query(Chunk, Chunk.embedding.cosine_distance(query_vec).label("distance"))
        .order_by("distance")
        .limit(limit)
        .all()
    )
    return [(chunk, round(1 - distance, 4)) for chunk, distance in rows]


def _keyword_ranked(db: Session, question: str, limit: int) -> list[Chunk]:
    """キーワード（文字の一致）で近い順。pg_trgm の word_similarity を使う。
    質問の文字トライグラムが本文にどれだけ含まれるかを見る＝固有名詞や型番に強い。"""
    sim = func.word_similarity(question, Chunk.content)
    rows = db.query(Chunk).order_by(sim.desc()).limit(limit).all()
    return list(rows)


def search(
    db: Session,
    question: str,
    top_k: int | None = None,
    method: str = "vector",
) -> list[dict]:
    """質問に近いチャンクを上位 top_k 件返す。

    method="vector" : 意味のベクトル検索（従来・既定）。
    method="hybrid" : ベクトル検索とキーワード検索を RRF で融合（Phase4）。
                      お互いの弱点（言い換え／固有名詞）を補い合う。
    """
    top_k = top_k or settings.top_k

    if method == "vector":
        ranked = _vector_ranked(db, gemini_client.embed_query(question), top_k)
        return [_chunk_to_dict(c, sim) for c, sim in ranked]

    if method == "keyword":
        return [_chunk_to_dict(c) for c in _keyword_ranked(db, question, top_k)]

    if method == "hybrid":
        return _hybrid_search(db, question, top_k)

    raise ValueError(f"未知の検索方式: {method}")


def _hybrid_search(db: Session, question: str, top_k: int) -> list[dict]:
    """ベクトル検索とキーワード検索の結果を RRF で融合する。

    RRF: 各方式での順位 r（0始まり）に対し 1/(RRF_K + r + 1) を足し合わせる。
    スコアの大小をそろえる正規化が要らず、順位だけで素直に混ぜられるのが利点。
    """
    vec = _vector_ranked(db, gemini_client.embed_query(question), CANDIDATE_K)
    kw = _keyword_ranked(db, question, CANDIDATE_K)

    scores: dict[int, float] = {}
    chunks: dict[int, Chunk] = {}
    for rank, (chunk, _sim) in enumerate(vec):
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        chunks[chunk.id] = chunk
    for rank, chunk in enumerate(kw):
        scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        chunks[chunk.id] = chunk

    best_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]
    return [_chunk_to_dict(chunks[cid], round(scores[cid], 4)) for cid in best_ids]


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
    try:
        generated = gemini_client.generate(prompt)
    except gemini_client.QuotaExhausted:
        # 無料枠切れでも検索は動いているので、根拠資料は返して状況を伝える。
        generated = (
            "⚠️ いま Gemini の無料利用枠（1日の生成回数）を使い切っています。"
            "検索は動いているので、根拠になりそうな資料は下に表示しています。"
            "時間をおく（枠は日次でリセット）と回答が再開します。"
        )
    return {"answer": generated, "contexts": contexts}
