"""
リランキング（Phase4）— クロスエンコーダで候補を精査して並べ直す。

検索（ベクトル/ハイブリッド）は「質問」と「文書」を別々にベクトル化して距離を測る
＝速いが大ざっぱ。ここでは違うタイプのモデル「クロスエンコーダ」を使う。

クロスエンコーダは、質問と文書を"一緒に"読んで関連度を1つの点数で返す採点専門の
小さなモデル（生成LLMではない＝Geminiの無料枠を使わない・ローカルで無制限）。
遅いので全チャンクには使えず、検索で絞った候補（数十件）だけを再採点する。

  検索で候補20件 → クロスエンコーダで1件ずつ採点 → 点数順に並べ直して上位k件
"""

from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def _model():
    """クロスエンコーダを1回だけ読み込んで使い回す。
    重い import はここに閉じ込め、リランクを使わないときは torch を読み込まない。
    初回はモデルをダウンロードする（数百MB・ネット接続が必要）。"""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.reranker_model)


def rerank(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    """候補（検索で絞ったチャンクの dict リスト）を、質問との関連度で再採点して
    上位 top_k 件を返す。similarity にはクロスエンコーダの点数を入れる。"""
    if not candidates:
        return []

    pairs = [(question, c["content"]) for c in candidates]
    scores = _model().predict(pairs)

    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    results = []
    for chunk, score in ranked[:top_k]:
        results.append({**chunk, "similarity": round(float(score), 4)})
    return results
