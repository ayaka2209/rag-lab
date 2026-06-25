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


def generate(prompt: str, max_retries: int = 3) -> str:
    """組み立てたプロンプトをLLMに渡し、回答テキストを得る。

    503（モデルの一時的な混雑）は、少し待って数回リトライする。
    無料枠でたまに起きるので、ここで吸収しておくと安定する。
    """
    for attempt in range(max_retries):
        try:
            resp = _client().models.generate_content(
                model=settings.generation_model,
                contents=prompt,
            )
            return resp.text or ""
        except errors.ServerError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return ""
