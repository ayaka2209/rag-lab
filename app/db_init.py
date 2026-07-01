"""
DB初期化。

1) pgvector拡張を有効化（CREATE EXTENSION vector）
   → これで Vector 型やベクトル検索が使えるようになる。
2) pg_trgm拡張を有効化（CREATE EXTENSION pg_trgm）
   → Phase4のキーワード検索（トライグラム類似）で使う。日本語でも形態素解析なしで
     固有名詞や型番のドンピシャ一致を拾える。
3) テーブル（documents / chunks）を作成。

Phase1では Alembic を使わず、起動時にこの関数で作る簡易方式。
（本体の経費アプリは Alembic 管理だが、ラボは学習優先で軽量にしている）
"""

from sqlalchemy import text

from . import models  # noqa: F401  Base にテーブルを登録するため必要
from .database import Base, engine


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)
