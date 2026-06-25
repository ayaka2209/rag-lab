"""
RAGのデータ構造（ORM）。

- Document : 取り込んだ元文書1件（どこから来たか）
- Chunk    : 文書を分割した断片。検索の最小単位。
             embedding 列に「意味を表すベクトル」を pgvector で保存する。

検索のしくみ：
  質問もベクトルにして、Chunk.embedding と「距離が近い」ものを上位から取る。
  距離が近い ＝ 意味が近い。
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from .config import settings
from .database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    # 出どころ（ファイル名やURLなど）。あとで「どの文書からの回答か」を示すのに使う。
    source = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # 文書内での順番（0始まり）。前後関係をたどれるようにしておく。
    chunk_index = Column(Integer, nullable=False)
    # チャンクの本文
    content = Column(Text, nullable=False)
    # 本文を埋め込みモデルで変換したベクトル（768次元）。
    # この列に対して「近いもの検索」をかける。
    embedding = Column(Vector(settings.embedding_dim))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
