"""
RAGの精度を数字で測る評価ランナー。

やること:
  1) 評価用コーパス(eval/corpus/*.md)をDBに取り込む（再実行しても重複しない）
  2) ゴールデンセット(eval/dataset.json)の各質問で検索を実行
  3) Recall@k / MRR を計算して表で出す（検索の精度）
  4) --judge を付けると、生成された回答の正確さ・忠実性も測る（API呼び出し増）

実行（プロジェクトルートで）:
  .venv/bin/python -m eval.run_eval                 # 検索の評価だけ（安い・埋め込みのみ）
  .venv/bin/python -m eval.run_eval --judge         # 生成の評価も（回答生成＝LLM呼び出し）
  .venv/bin/python -m eval.run_eval --judge --faithfulness  # 忠実性判定も（LLM呼び出し倍増）
  .venv/bin/python -m eval.run_eval --reset         # コーパスを入れ直してから評価

前提: pgvectorが起動済み・.envにGEMINI_API_KEYがある。
注意: 生成(gemini-2.5-flash)は無料枠の1日上限が小さい。--judge は枠を使うので
      日に何度も回せない。検索評価(埋め込み)は枠が別で気軽に回せる。
"""

import argparse
import json
import time
from pathlib import Path

from google.genai import errors

from app import gemini_client, ingest, retrieval
from app.database import SessionLocal
from app.models import Document

from . import metrics

EVAL_DIR = Path(__file__).resolve().parent
CORPUS_DIR = EVAL_DIR / "corpus"
DATASET_PATH = EVAL_DIR / "dataset.json"

# 検索で取る最大件数。Recall@1/@3/@5 を見るので 5。
TOP_K = 5
# 生成評価で1問ごとに空ける待ち時間（秒）。無料枠の毎分上限(RPM)超過を防ぐ。
THROTTLE_SEC = 5


def ingest_corpus(db, reset: bool = False) -> None:
    """corpus/ の各ファイルを取り込む。
    既に全ファイルが入っていれば埋め込みを無駄打ちせずスキップする。
    reset=True のときは消して入れ直す（チャンク設定を変えた後などに使う）。"""
    files = sorted(CORPUS_DIR.glob("*.md"))
    present = {s for (s,) in db.query(Document.source).all()}
    all_loaded = all(path.name in present for path in files)
    if all_loaded and not reset:
        print(f"[1/3] コーパス: {len(files)}ファイルは取り込み済み（スキップ）\n")
        return

    print(f"[1/3] コーパス取り込み: {len(files)}ファイル{'（--reset）' if reset else ''}")
    for path in files:
        source = path.name
        for doc in db.query(Document).filter(Document.source == source).all():
            db.delete(doc)  # cascade で chunks も消える
        db.commit()
        text = path.read_text(encoding="utf-8")
        ingest.ingest_text(db, source=source, text=text)
    print("      取り込み完了\n")


def source_map(db) -> dict[int, str]:
    """document_id → source（出どころ）の対応表。"""
    return {doc.id: doc.source for doc in db.query(Document).all()}


def evaluate_retrieval(db, items: list[dict]) -> list[dict]:
    """各質問で検索し、ランク付き出どころと指標を集める。"""
    id2src = source_map(db)
    rows = []
    print("[2/3] 検索の評価（質問ごとに上位を取得）")
    for item in items:
        contexts = retrieval.search(db, item["question"], top_k=TOP_K)
        ranked = [id2src.get(c["document_id"], "?") for c in contexts]
        relevant = item["relevant_source"]
        rows.append(
            {
                "id": item["id"],
                "relevant": relevant,
                "ranked": ranked,
                "r@1": metrics.recall_at_k(ranked, relevant, 1),
                "r@3": metrics.recall_at_k(ranked, relevant, 3),
                "r@5": metrics.recall_at_k(ranked, relevant, 5),
                "rr": metrics.reciprocal_rank(ranked, relevant),
            }
        )
    return rows


def judge_faithfulness(answer: str, contexts: list[dict]) -> float:
    """回答が「渡した資料だけ」に忠実か（作り話をしていないか）をLLMに判定させる。
    Ragasの faithfulness の素朴版。1.0=忠実 / 0.0=資料に無いことを言っている。"""
    context_text = "\n\n".join(c["content"] for c in contexts)
    prompt = (
        "次の【回答】が【資料】だけで裏付けられるか判定してください。"
        "資料に書かれていない情報を回答が含むなら faithful=0、"
        "すべて資料で裏付けられるなら faithful=1。"
        '出力はJSONのみ: {"faithful": 0 または 1}\n\n'
        f"=== 資料 ===\n{context_text}\n\n"
        f"=== 回答 ===\n{answer}\n"
    )
    raw = gemini_client.generate(prompt)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        verdict = json.loads(raw[start : end + 1])
        return float(verdict.get("faithful", 0))
    except (ValueError, KeyError):
        return 0.0  # 判定不能は安全側（0）に倒す


def evaluate_generation(db, items: list[dict], faithfulness: bool) -> list[dict]:
    """回答を生成し、事実カバー率（と任意で忠実性）を測る。

    回答生成だけで1問1回のLLM呼び出し、--faithfulness を付けるとさらに1回増える。
    無料枠(429)に当たったら、その時点までの結果を返して優雅に止まる。"""
    rows = []
    judge_note = "＋忠実性判定" if faithfulness else ""
    print(f"\n[3/3] 生成の評価（回答生成{judge_note}。1問ごとに{THROTTLE_SEC}秒待機）")
    for item in items:
        try:
            result = retrieval.answer(db, item["question"], top_k=TOP_K)
            coverage = metrics.fact_coverage(result["answer"], item["answer_facts"])
            faithful = (
                judge_faithfulness(result["answer"], result["contexts"])
                if faithfulness
                else None
            )
        except errors.ClientError as e:
            if e.code == 429:
                print(f"      Q{item['id']:>2}: ⚠ Gemini無料枠の上限に到達。ここまでで集計します。")
                break
            raise
        rows.append(
            {
                "id": item["id"],
                "coverage": coverage,
                "faithful": faithful,
                "answer": result["answer"],
            }
        )
        f_str = f" 忠実{faithful:.0f}" if faithful is not None else ""
        print(f"      Q{item['id']:>2}: 事実{coverage:.0%}{f_str} | {result['answer'][:36]}")
        time.sleep(THROTTLE_SEC)
    return rows


def print_retrieval_table(rows: list[dict]) -> None:
    print("\n--- 検索の結果（質問ごと）---")
    print(f"{'Q':>3} {'正解source':<22} {'R@1':>4} {'R@3':>4} {'R@5':>4} {'RR':>5}  上位の出どころ")
    for r in rows:
        top3 = " > ".join(r["ranked"][:3])
        print(
            f"{r['id']:>3} {r['relevant']:<22} "
            f"{r['r@1']:>4.0f} {r['r@3']:>4.0f} {r['r@5']:>4.0f} {r['rr']:>5.2f}  {top3}"
        )


def print_summary(ret_rows: list[dict], gen_rows: list[dict] | None) -> None:
    print("\n========== 集計（平均）==========")
    print(f"  Recall@1 : {metrics.mean([r['r@1'] for r in ret_rows]):.3f}  （正解を1位で当てた割合）")
    print(f"  Recall@3 : {metrics.mean([r['r@3'] for r in ret_rows]):.3f}  （上位3件に正解が入った割合）")
    print(f"  Recall@5 : {metrics.mean([r['r@5'] for r in ret_rows]):.3f}  （上位5件に正解が入った割合）")
    print(f"  MRR      : {metrics.mean([r['rr'] for r in ret_rows]):.3f}  （正解の順位の良さ・1に近いほど上位）")
    if gen_rows:
        n = len(gen_rows)
        print(f"  事実カバー率: {metrics.mean([r['coverage'] for r in gen_rows]):.3f}  （回答が必要な事実を含む割合・{n}問）")
        faiths = [r["faithful"] for r in gen_rows if r["faithful"] is not None]
        if faiths:
            print(f"  忠実性     : {metrics.mean(faiths):.3f}  （資料だけに基づく割合・{len(faiths)}問）")
    print("=================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG評価ランナー")
    parser.add_argument(
        "--judge", action="store_true", help="生成の評価も行う（回答生成＝LLM呼び出し）"
    )
    parser.add_argument(
        "--faithfulness", action="store_true", help="忠実性のLLM判定も行う（--judge前提・呼び出し倍増）"
    )
    parser.add_argument(
        "--reset", action="store_true", help="コーパスを消して入れ直してから評価する"
    )
    args = parser.parse_args()

    items = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["items"]
    db = SessionLocal()
    try:
        ingest_corpus(db, reset=args.reset)
        ret_rows = evaluate_retrieval(db, items)
        print_retrieval_table(ret_rows)
        gen_rows = (
            evaluate_generation(db, items, faithfulness=args.faithfulness)
            if args.judge
            else None
        )
        print_summary(ret_rows, gen_rows)
    finally:
        db.close()


if __name__ == "__main__":
    main()
