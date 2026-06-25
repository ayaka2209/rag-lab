"""
RAG学習ラボの設定。

経費アプリ本体の backend/app/config.py と同じ作法（pydantic-settings）。
秘密のキーや接続先はコードに直書きせず、.env から読み込む。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- 接続・認証 ---
    # Gemini の無料APIキー（https://aistudio.google.com/apikey）
    gemini_api_key: str = ""
    # RAGラボ専用DB（pgvector入りPostgres・ポート5433）への接続文字列
    rag_database_url: str = (
        "postgresql+psycopg2://raglab:raglab_dev_password@localhost:5433/raglab"
    )

    # --- モデル ---
    # 埋め込みモデル：文章をベクトルに変換する（無料）
    # gemini-embedding-001 はデフォルト3072次元だが、output_dimensionality で
    # 768に縮めて使う（DBの Vector(768) 列に合わせる）。
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    # 回答生成モデル（このプロジェクトでは 2.5-flash に無料枠あり）
    generation_model: str = "gemini-2.5-flash"

    # --- チャンク分割のパラメータ（Phase3で実験する対象）---
    # 1チャンクの文字数。大きすぎると検索が雑になり、小さすぎると文脈が切れる。
    chunk_size: int = 500
    # 隣り合うチャンクで重ねる文字数。境界で文脈が切れるのを防ぐ。
    chunk_overlap: int = 100

    # --- 検索 ---
    # 質問に近い上位何件のチャンクをLLMに渡すか
    top_k: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
