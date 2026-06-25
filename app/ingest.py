"""
取り込み（Ingestion）パイプライン。

  元文書テキスト
    → チャンク分割
    → 各チャンクを埋め込み（ベクトル化）
    → Document / Chunk として保存

これで「検索できる状態」になる。RAGの準備フェーズ。
"""

from sqlalchemy.orm import Session

from . import gemini_client
from .chunking import chunk_text
from .models import Chunk, Document


def ingest_text(db: Session, source: str, text: str) -> dict:
    chunks = chunk_text(text)
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
