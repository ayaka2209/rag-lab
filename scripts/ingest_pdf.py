"""
好きなPDFを1つ取り込むCLIスクリプト。

  抽出（pypdf）→ 分割 → 埋め込み → pgvector に保存

使い方（プロジェクトルートで・pgvector起動済み）:
  .venv/bin/python scripts/ingest_pdf.py <PDFのパス>
  .venv/bin/python scripts/ingest_pdf.py ~/Downloads/manual.pdf

取り込むと、フロント( http://localhost:5173 )の質問対象に加わる。
※ 抽出テキストは改行や表崩れのゴミを含むので、空白・改行は軽く除去してから取り込む。
※ 埋め込みの無料枠（毎分約100回）を使う。巨大PDFは分けて入れるのが無難。
"""

import argparse
import re
import sys
from pathlib import Path

# scripts/ から実行しても app パッケージを見つけられるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ingest  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.db_init import init_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="PDFを1つ取り込む")
    parser.add_argument("pdf_path", help="取り込むPDFファイルのパス")
    parser.add_argument("--keep-source", help="保存名（source）を明示。省略時はファイル名")
    args = parser.parse_args()

    path = Path(args.pdf_path).expanduser()
    if not path.exists():
        sys.exit(f"ファイルが見つかりません: {path}")

    init_db()
    db = SessionLocal()
    try:
        text = ingest.pdf_to_text(path)
        cleaned = re.sub(r"\s+", "", text)  # 改行・空行・空白を除去（日本語は語間空白が不要）
        source = args.keep_source or path.name
        result = ingest.ingest_text(db, source=source, text=cleaned)
        print(f"取り込み完了: source='{result['source']}' / {result['chunks']}チャンク")
        print("→ http://localhost:5173 で、この内容について質問できます。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
