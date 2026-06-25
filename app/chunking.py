"""
チャンク分割（Phase1：いちばん素朴な固定長＋オーバーラップ）。

長い文書をそのまま埋め込むと「意味がぼやけて」検索精度が落ちる。
そこで適度な長さに区切る。これが「チャンク分割」。

Phase1は文字数ベースの固定長で割るだけ。
Phase3で「文・段落単位」「セマンティック分割」などに発展させ、
そのたびに精度がどう変わるかを評価で測る予定。
"""

from .config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    text = text.strip()
    if not text:
        return []
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
