"""
チャンク戦略の比較実験（Phase 3）。

同じ長い文書(handbook.md)を、いろいろな分割方法でチャンク化して取り込み、
「質問の答えが、検索で取れたチャンクの中に入っているか」を測って並べる。

測る指標（検索＝埋め込みのみなので生成の無料枠は使わない）:
  チャンク数   … その分割で何個のチャンクになったか
  平均文字数   … 1チャンクの平均の長さ
  文脈カバー率 … 取れたチャンク群に「含むべき事実」がどれだけ入っていたか（平均）
  全事実命中率 … 必要な事実が"全部"取れた質問の割合（厳しめのヒット率）

実行（プロジェクトルートで・pgvector起動済み）:
  .venv/bin/python -m eval.compare_chunking

注意: 実験のため一度DBを空にして handbook だけを入れる。
      終了時に sample.md と eval/corpus/* を入れ直して元の状態に戻す。
"""

import json
from pathlib import Path

from app import ingest, retrieval
from app.database import SessionLocal
from app.models import Chunk, Document

from . import metrics

EVAL_DIR = Path(__file__).resolve().parent
HANDBOOK = EVAL_DIR / "corpus_long" / "handbook.md"
DATASET_PATH = EVAL_DIR / "dataset.json"
SAMPLE_PATH = EVAL_DIR.parent / "data" / "sample.md"
STD_CORPUS_DIR = EVAL_DIR / "corpus"

# 何件取れたかを変えて見るための k のリスト。1回の検索結果を使い回すので
# 埋め込みは増えない。k を絞るほど分割の良し悪しが効いてくる。
KS = [1, 2, 4]

# 比べる分割設定。戦略 × サイズ を変えて精度の差を見る。
CONFIGS = [
    {"label": "fixed   200/40", "strategy": "fixed", "chunk_size": 200, "overlap": 40},
    {"label": "fixed   500/100", "strategy": "fixed", "chunk_size": 500, "overlap": 100},
    {"label": "fixed  1000/200", "strategy": "fixed", "chunk_size": 1000, "overlap": 200},
    {"label": "sentence 300", "strategy": "sentence", "chunk_size": 300, "overlap": 0},
]


def wipe_all(db) -> None:
    """全文書を削除してまっさらにする（実験の条件を揃えるため）。"""
    for doc in db.query(Document).all():
        db.delete(doc)
    db.commit()


def ingest_handbook(db, cfg: dict) -> list[int]:
    """handbook を指定の分割設定で取り込み、各チャンクの文字数リストを返す。"""
    text = HANDBOOK.read_text(encoding="utf-8")
    ingest.ingest_text(
        db,
        source=HANDBOOK.name,
        text=text,
        chunk_size=cfg["chunk_size"],
        overlap=cfg["overlap"],
        strategy=cfg["strategy"],
    )
    rows = (
        db.query(Chunk.content)
        .join(Document)
        .filter(Document.source == HANDBOOK.name)
        .all()
    )
    return [len(content) for (content,) in rows]


def evaluate(db, items: list[dict]) -> dict[int, float]:
    """各質問で検索し、上位k件のチャンクに答えの事実がどれだけ入るかを測る。
    1回の検索（top_k=max(KS)）の結果を、k=1/2/4 で切り出して使い回す。
    戻り値: {k: 文脈カバー率の平均}。"""
    per_k = {k: [] for k in KS}
    for item in items:
        contexts = retrieval.search(db, item["question"], top_k=max(KS))
        for k in KS:
            joined = "\n".join(c["content"] for c in contexts[:k])
            per_k[k].append(metrics.fact_coverage(joined, item["answer_facts"]))
    return {k: metrics.mean(per_k[k]) for k in KS}


def restore_standard_corpus(db) -> None:
    """実験で入れ替えたDBを、普段の状態（sample.md ＋ eval/corpus/*）に戻す。"""
    wipe_all(db)
    ingest.ingest_text(db, source=SAMPLE_PATH.name, text=SAMPLE_PATH.read_text(encoding="utf-8"))
    for path in sorted(STD_CORPUS_DIR.glob("*.md")):
        ingest.ingest_text(db, source=path.name, text=path.read_text(encoding="utf-8"))


def main() -> None:
    items = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["items"]
    db = SessionLocal()
    try:
        print(f"チャンク戦略の比較（handbook.md / 全{len(items)}問）\n")
        rows = []
        for cfg in CONFIGS:
            wipe_all(db)
            lengths = ingest_handbook(db, cfg)
            cov = evaluate(db, items)
            rows.append(
                {
                    "label": cfg["label"],
                    "n": len(lengths),
                    "avg_len": metrics.mean([float(x) for x in lengths]),
                    "cov": cov,
                }
            )
            print(f"  測定済み: {cfg['label']}")

        print("\n--- 比較結果（文脈カバー率：取れたチャンクに答えの事実が入った割合）---")
        kcols = "".join(f"{'カバー@' + str(k):>9}" for k in KS)
        print(f"{'分割設定':<16} {'チャンク数':>7} {'平均文字':>7}{kcols}")
        for r in rows:
            kvals = "".join(f"{r['cov'][k]:>9.3f}" for k in KS)
            print(f"{r['label']:<16} {r['n']:>7} {r['avg_len']:>7.0f}{kvals}")
        print(
            "\n読み方: カバー@k は『上位k件のチャンクに答えが入っていた割合』。"
            "\n  - k=1（1件だけ使う）で差が出やすい：小さいチャンクは事実が分かれて取りこぼし、"
            "\n    大きいチャンクは1件に情報が多く入るので有利になりがち。"
            "\n  - k=4 まで取ると差は縮む（多めに取れば結局カバーできる）。"
            "\n  実運用では精度とノイズ（無駄に長い文脈）の綱引きで最適サイズを選ぶ。"
        )
    finally:
        print("\n通常コーパスに復元中…")
        restore_standard_corpus(db)
        db.close()
        print("復元完了（sample.md ＋ eval/corpus/*）。")


if __name__ == "__main__":
    main()
