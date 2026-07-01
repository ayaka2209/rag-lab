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
    # 回答生成モデル。先頭から順に試し、無料枠切れ(429)なら次へフォールバックする。
    # モデルごとに無料枠が別なので、flashが枠切れでも flash-lite で回答を続けられる。
    generation_models: list[str] = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

    # --- チャンク分割のパラメータ（Phase3で実験する対象）---
    # 分割戦略: "fixed"（文字数固定長）/ "sentence"（文単位で詰める）
    chunk_strategy: str = "fixed"
    # 1チャンクの文字数。大きすぎると検索が雑になり、小さすぎると文脈が切れる。
    chunk_size: int = 500
    # 隣り合うチャンクで重ねる文字数。境界で文脈が切れるのを防ぐ。
    chunk_overlap: int = 100

    # --- 検索 ---
    # 質問に近い上位何件のチャンクをLLMに渡すか
    top_k: int = 4

    # --- リランキング（Phase4）---
    # クロスエンコーダ（ローカルの採点モデル）。日本語対応・小型でCPUでも動く。
    # 生成LLMではないので、Geminiの無料枠は使わない。初回だけモデルをDLする。
    reranker_model: str = "hotchpotch/japanese-reranker-cross-encoder-small-v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
