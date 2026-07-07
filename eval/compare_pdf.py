"""
実データ（PDF）での検索方式の比較（レベルアップ編）。

これまでの評価コーパスは自作の"きれいな"Markdownで、ベクトル検索だけで満点だった。
ここでは PDF(kitei.pdf) から抽出した、似た用語（申請・承認・上限・精算・円）が
大量に出る"難しめ"のデータで、vector/keyword/hybrid/rerank を比べる。

指標（passage寄り・precisionを見る）:
  正解@1 … 検索1位のチャンクが「正解の事実（トピック語＋数値）」を全部含む割合
  正解@3 … 上位3件のどれかが全部含む割合

検索のみ（埋め込み＋ローカルのリランカー）なので生成の無料枠は使わない。
実験のため一度DBを空にし、終了時に通常コーパスへ復元する。

実行: .venv/bin/python -m eval.compare_pdf
"""

import json
import re
from pathlib import Path

from app import ingest, retrieval
from app.database import SessionLocal
from app.db_init import init_db
from app.models import Document

from . import metrics

EVAL_DIR = Path(__file__).resolve().parent
PDF_PATH = EVAL_DIR.parent / "data" / "pdf" / "kitei.pdf"
DATASET_PATH = EVAL_DIR / "dataset_pdf.json"
SAMPLE_PATH = EVAL_DIR.parent / "data" / "sample.md"
STD_CORPUS_DIR = EVAL_DIR / "corpus"

METHODS = ["vector", "keyword", "hybrid", "rerank"]
TOP_K = 3


def _norm(s: str) -> str:
    return re.sub(r"[\s,]", "", s)


def wipe_all(db) -> None:
    for doc in db.query(Document).all():
        db.delete(doc)
    db.commit()


def ingest_pdf_clean(db) -> int:
    """PDFを取り込む。抽出テキストは改行や空行が多いので空白を除去し、
    文（句点）単位の小さめチャンクにして条文ごとに分かれやすくする。"""
    text = ingest.pdf_to_text(PDF_PATH)
    cleaned = re.sub(r"\s+", "", text)  # 改行・空行・空白を除去（日本語なので語間の空白は不要）
    result = ingest.ingest_text(
        db, source=PDF_PATH.name, text=cleaned, strategy="sentence", chunk_size=60
    )
    return result["chunks"]


def chunk_covers(content: str, facts: list[str]) -> bool:
    """そのチャンク単体が、質問の全factsを含むか（トピック語＋数値の両方）。"""
    c = _norm(content)
    return all(_norm(f) in c for f in facts)


def evaluate(db, items: list[dict], method: str) -> dict:
    hit1, hit3 = [], []
    per_q = []
    for item in items:
        contexts = retrieval.search(db, item["question"], top_k=TOP_K, method=method)
        covers = [chunk_covers(c["content"], item["answer_facts"]) for c in contexts]
        h1 = 1.0 if covers[:1] == [True] else 0.0
        h3 = 1.0 if any(covers) else 0.0
        hit1.append(h1)
        hit3.append(h3)
        top1 = contexts[0]["content"] if contexts else ""
        per_q.append({"id": item["id"], "hit1": bool(h1), "top1": top1})
    return {"hit1": metrics.mean(hit1), "hit3": metrics.mean(hit3), "per_q": per_q}


def restore_standard_corpus(db) -> None:
    wipe_all(db)
    ingest.ingest_text(db, source=SAMPLE_PATH.name, text=SAMPLE_PATH.read_text(encoding="utf-8"))
    for path in sorted(STD_CORPUS_DIR.glob("*.md")):
        ingest.ingest_text(db, source=path.name, text=path.read_text(encoding="utf-8"))


def main() -> None:
    init_db()
    items = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["items"]
    db = SessionLocal()
    try:
        wipe_all(db)
        n = ingest_pdf_clean(db)
        print(f"PDF取り込み: {PDF_PATH.name} → {n}チャンク / 質問{len(items)}問 / top_k={TOP_K}\n")

        results = {m: evaluate(db, items, m) for m in METHODS}

        print("--- 質問ごとに1位で正解を取れたか（○=取れた）---")
        print(f"{'Q':>2}  " + "".join(f"{m:>9}" for m in METHODS))
        for i, item in enumerate(items):
            marks = "".join(f"{'○' if results[m]['per_q'][i]['hit1'] else '×':>9}" for m in METHODS)
            print(f"{item['id']:>2}  {marks}")

        print("\n--- 集計（各方式の平均）---")
        print(f"{'指標':<8}" + "".join(f"{m:>9}" for m in METHODS))
        for key, label in [("hit1", "正解@1"), ("hit3", "正解@3")]:
            print(f"{label:<8}" + "".join(f"{results[m][key]:>9.3f}" for m in METHODS))
        base = results["vector"]["hit1"]
        print(f"\nvector@1 を基準にした改善: "
              + " / ".join(f"{m} {results[m]['hit1'] - base:+.3f}" for m in METHODS if m != "vector"))

        # 方式間で1位が割れた質問の、各方式の1位チャンクを表示（ブログの具体例用）
        print("\n--- 方式で結果が割れた質問の『1位チャンク』---")
        for i, item in enumerate(items):
            hits = {m: results[m]["per_q"][i]["hit1"] for m in METHODS}
            if len(set(hits.values())) > 1:
                print(f"\n[Q{item['id']}] {item['question']}  正解の手がかり={item['answer_facts']}")
                for m in METHODS:
                    mark = "○" if hits[m] else "×"
                    print(f"  {mark} {m:<8}: {results[m]['per_q'][i]['top1'][:46]}")
    finally:
        print("\n通常コーパスに復元中…")
        restore_standard_corpus(db)
        db.close()
        print("復元完了。")


if __name__ == "__main__":
    main()
