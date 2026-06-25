"""
DB初期化。

1) pgvector拡張を有効化（CREATE EXTENSION vector）
   → これで Vector 型やベクトル検索が使えるようになる。
2) テーブル（documents / chunks）を作成。

Phase1では Alembic を使わず、起動時にこの関数で作る簡易方式。
（本体の経費アプリは Alembic 管理だが、ラボは学習優先で軽量にしている）
"""

from sqlalchemy import text

from . import models  # noqa: F401  Base にテーブルを登録するため必要
from .database import Base, engine


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
