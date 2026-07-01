"""
検索方式の比較（Phase 4・ハイブリッド検索）。

同じ質問セットに対して、
  - vector : 意味のベクトル検索だけ（従来）
  - hybrid : ベクトル＋キーワード(pg_trgm)を RRF で融合
を実行し、Recall@k と MRR を並べて、ハイブリッドで精度が上がるかを数字で見る。

題材は eval/corpus_codes/（型番付きの似た書類）。意味が薄い型番(F-204等)が
答えのカギなので、ベクトルだけだと似た書類で混同しやすく、キーワードが効く想定。

実行（プロジェクトルートで・pgvector起動済み）:
  .venv/bin/python -m eval.compare_search

検索のみ（埋め込み）で動くので、生成の無料枠は使わない。
コーパスは既存DBに追加する（取り込み済みならスキップ）。
"""

import json
from pathlib import Path

from app import ingest, retrieval
from app.database import SessionLocal
from app.db_init import init_db
from app.models import Document

from . import metrics

EVAL_DIR = Path(__file__).resolve().parent
CODES_CORPUS_DIR = EVAL_DIR / "corpus_codes"
DATASET_PATH = EVAL_DIR / "dataset_codes.json"

METHODS = ["vector", "keyword", "hybrid", "rerank"]


def ensure_corpus(db) -> None:
    """corpus_codes/ を取り込む。内容を更新しても反映されるよう、毎回入れ直す。"""
    files = sorted(CODES_CORPUS_DIR.glob("*.md"))
    print(f"コーパス取り込み: {len(files)}件")
    for path in files:
        for doc in db.query(Document).filter(Document.source == path.name).all():
            db.delete(doc)  # cascade で chunks も消える
        db.commit()
        ingest.ingest_text(db, source=path.name, text=path.read_text(encoding="utf-8"))
    print("取り込み完了\n")


def source_map(db) -> dict[int, str]:
    return {doc.id: doc.source for doc in db.query(Document).all()}


def evaluate_method(db, items: list[dict], id2src: dict[int, str], method: str) -> dict:
    """1つの検索方式で全質問を採点し、集計指標を返す。"""
    r1, r3, rr = [], [], []
    per_q = []
    for item in items:
        contexts = retrieval.search(db, item["question"], top_k=3, method=method)
        ranked = [id2src.get(c["document_id"], "?") for c in contexts]
        relevant = item["relevant_source"]
        r1.append(metrics.recall_at_k(ranked, relevant, 1))
        r3.append(metrics.recall_at_k(ranked, relevant, 3))
        rr.append(metrics.reciprocal_rank(ranked, relevant))
        per_q.append({"id": item["id"], "top1": ranked[0] if ranked else "-", "hit": ranked[:1] == [relevant]})
    return {
        "r1": metrics.mean(r1),
        "r3": metrics.mean(r3),
        "mrr": metrics.mean(rr),
        "per_q": per_q,
    }


def main() -> None:
    init_db()  # pg_trgm 拡張を確実に有効化
    items = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["items"]
    db = SessionLocal()
    try:
        ensure_corpus(db)
        id2src = source_map(db)
        results = {m: evaluate_method(db, items, id2src, m) for m in METHODS}

        print("--- 質問ごとに正解を1位で取れたか（○=取れた ×=外した）---")
        print(f"{'Q':>2} {'種類':<6} {'正解source':<16} " + "".join(f"{m:>9}" for m in METHODS))
        for i, item in enumerate(items):
            kind = "型番" if i < 6 else "言い換え"
            marks = "".join(
                f"{'○' if results[m]['per_q'][i]['hit'] else '×':>9}" for m in METHODS
            )
            print(f"{item['id']:>2} {kind:<6} {item['relevant_source']:<16} {marks}")

        print("\n--- 集計（各方式の平均）---")
        print(f"{'指標':<10}" + "".join(f"{m:>9}" for m in METHODS))
        for key, label in [("r1", "Recall@1"), ("r3", "Recall@3"), ("mrr", "MRR")]:
            print(f"{label:<10}" + "".join(f"{results[m][key]:>9.3f}" for m in METHODS))
        print(
            "\n読み方:"
            "\n  - keyword(キーワードのみ): 型番(F-204等)は得意だが、言い換え(ゲスト⇔来客)は苦手。"
            "\n  - vector(意味のみ): 言い換えは得意。型番も最新モデルは強い。"
            "\n  - hybrid(融合): 両者の良いとこ取りで、どちらの質問にも強い＝一番取りこぼしが少ない。"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
