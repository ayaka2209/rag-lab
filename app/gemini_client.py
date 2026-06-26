"""
Gemini（無料）への薄いラッパー。

ここだけが外部API（Google Gemini）に触れる層。
- embed_documents / embed_query : 文章 → ベクトル（埋め込み）
- generate                      : 文脈＋質問 → 回答（生成）

【埋め込みの task_type について】
RAGでは「文書を入れるとき」と「質問で検索するとき」で、
わざと少し違う埋め込み方をすると精度が上がる。
  - 文書側 : RETRIEVAL_DOCUMENT
  - 質問側 : RETRIEVAL_QUERY
これを「非対称な埋め込み」と呼ぶ。同じモデルでも役割で使い分ける。
"""

import time
from functools import lru_cache

from google import genai
from google.genai import errors, types

from .config import settings


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    """Geminiクライアントを1個だけ作って使い回す。"""
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY が未設定です。rag-lab/.env に貼り付けてください。"
            "（取得: https://aistudio.google.com/apikey）"
        )
    return genai.Client(api_key=settings.gemini_api_key)


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    resp = _client().models.embed_content(
        model=settings.embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            # 出力次元を 768 に固定（DBの Vector(768) と一致させる）
            output_dimensionality=settings.embedding_dim,
        ),
    )
    return [e.values for e in resp.embeddings]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """文書チャンクをまとめてベクトル化（保存用）。"""
    return _embed(texts, task_type="RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """質問1件をベクトル化（検索用）。"""
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]


class QuotaExhausted(Exception):
    """生成モデルが全て無料枠の上限(429)に達して回答できないとき。"""


def generate(prompt: str, max_retries: int = 3) -> str:
    """組み立てたプロンプトをLLMに渡し、回答テキストを得る。

    - 503（モデルの一時的な混雑）は、少し待って数回リトライする。
    - 429（無料枠の上限）は、settings.generation_models の次のモデルへフォールバックする。
      モデルごとに無料枠が別なので、flashが枠切れでも flash-lite で回答を続けられる。
    - 全モデルが枠切れなら QuotaExhausted を投げる（呼び出し側で優しく扱う）。
    """
    for model in settings.generation_models:
        for attempt in range(max_retries):
            try:
                resp = _client().models.generate_content(model=model, contents=prompt)
                return resp.text or ""
            except errors.ServerError:
                if attempt == max_retries - 1:
                    break  # このモデルは諦めて次のモデルへ
                time.sleep(2 * (attempt + 1))
            except errors.ClientError as e:
                if e.code == 429:
                    break  # 無料枠切れ。次のモデルにフォールバック
                raise  # それ以外のクライアントエラーはそのまま投げる
    raise QuotaExhausted(
        "生成モデルが全て無料枠の上限に達しました。時間をおく（枠は日次でリセット）と回復します。"
    )
