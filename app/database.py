"""
RAGラボ専用のDB接続（SQLAlchemy）。

経費アプリ本体とは別のDB（ポート5433の raglab）に繋ぐ。
本体のデータには一切触れない。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(settings.rag_database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """1リクエスト = 1セッション。終わったら必ず閉じる。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
