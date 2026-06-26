"""
チャンク分割。

長い文書をそのまま埋め込むと「意味がぼやけて」検索精度が落ちる。
そこで適度な長さに区切る。これが「チャンク分割」。

戦略（strategy）を切り替えられる：
  - "fixed"    : 文字数ベースの固定長＋オーバーラップ（Phase1の素朴な方法）。
                 速くて単純だが、文の途中でブツ切りになりうる。
  - "sentence" : 文（句点・改行）で区切ってから、上限サイズまで詰める。
                 文の途中で切れないので、意味のまとまりが保たれやすい。

Phase3では戦略やサイズを変え、Phase2の評価で精度の差を数字で見る。
"""

import re

from .config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    strategy: str | None = None,
) -> list[str]:
    """文書を戦略に応じてチャンクに分割する。"""
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    strategy = strategy or settings.chunk_strategy

    text = text.strip()
    if not text:
        return []

    if strategy == "fixed":
        return _chunk_fixed(text, chunk_size, overlap)
    if strategy == "sentence":
        return _chunk_sentence(text, chunk_size)
    raise ValueError(f"未知のチャンク戦略: {strategy}")


def _chunk_fixed(text: str, chunk_size: int, overlap: int) -> list[str]:
    """文字数で機械的に区切る。境界で文脈が切れないよう overlap 分だけ重ねる。"""
    if overlap >= chunk_size:
        raise ValueError("overlap は chunk_size より小さくしてください。")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        # 次の開始位置を overlap 分だけ戻す＝境界で文脈が切れないようにする
        start = end - overlap
    return chunks


def _split_sentences(text: str) -> list[str]:
    """日本語の文に分割する。句点「。」の後ろと改行で区切り、区切り文字は残す。"""
    parts = re.split(r"(?<=。)|\n", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_sentence(text: str, chunk_size: int) -> list[str]:
    """文単位で区切ってから、上限サイズを超えない範囲で貪欲に詰める。
    文の途中では切らないので、意味のまとまりが壊れにくい。"""
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > chunk_size:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        chunks.append(current)
    return chunks
