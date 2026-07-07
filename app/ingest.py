"""
取り込み（Ingestion）パイプライン。

  元文書テキスト
    → チャンク分割
    → 各チャンクを埋め込み（ベクトル化）
    → Document / Chunk として保存

これで「検索できる状態」になる。RAGの準備フェーズ。
"""

import re
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from . import gemini_client
from .chunking import chunk_text
from .models import Chunk, Document


def _reader_to_text(reader) -> str:
    """PdfReader の全ページからテキストを結合する。

    実データの洗礼ポイント：表はセルがバラバラの行になり、文の途中で改行が入る。
    （本格的なレイアウト解析は範囲外。まずは"生の抽出"を体感するのが目的）
    """
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def pdf_to_text(path: str | Path) -> str:
    """PDFファイル（パス）から素のテキストを抽出する。"""
    from pypdf import PdfReader

    return _reader_to_text(PdfReader(str(path)))


def pdf_bytes_to_text(data: bytes) -> str:
    """PDFのバイト列（アップロード等）から素のテキストを抽出する。"""
    from pypdf import PdfReader

    return _reader_to_text(PdfReader(BytesIO(data)))


def clean_extracted(text: str) -> str:
    """抽出テキストの改行・空行・空白を除去する（日本語は語間の空白が不要）。
    PDFの『文の途中改行』や『表の崩れ』のゴミをある程度ならす。"""
    return re.sub(r"\s+", "", text)


def ingest_pdf(db: Session, path: str | Path, clean: bool = True, **chunk_opts) -> dict:
    """PDFファイル（パス）を取り込む（抽出→掃除→分割→埋め込み→保存）。"""
    path = Path(path)
    text = pdf_to_text(path)
    if clean:
        text = clean_extracted(text)
    return ingest_text(db, source=path.name, text=text, **chunk_opts)


def ingest_pdf_bytes(
    db: Session, source: str, data: bytes, clean: bool = True, **chunk_opts
) -> dict:
    """PDFのバイト列（ブラウザからのアップロード）を取り込む。"""
    text = pdf_bytes_to_text(data)
    if clean:
        text = clean_extracted(text)
    return ingest_text(db, source=source, text=text, **chunk_opts)


def ingest_text(
    db: Session,
    source: str,
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    strategy: str | None = None,
) -> dict:
    # 省略時は settings の既定値。Phase3の実験では戦略やサイズを上書きして比較する。
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap, strategy=strategy)
    if not chunks:
        return {"source": source, "chunks": 0}

    # まとめて埋め込む（API呼び出し回数を減らす）
    vectors = gemini_client.embed_documents(chunks)

    document = Document(source=source)
    db.add(document)
    db.flush()  # document.id を採番させる

    for i, (content, vector) in enumerate(zip(chunks, vectors)):
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=i,
                content=content,
                embedding=vector,
            )
        )

    db.commit()
    return {"source": source, "document_id": document.id, "chunks": len(chunks)}
