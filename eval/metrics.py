"""
検索（Retrieval）の精度を測る指標。

ここでは「正解の出どころ(source)が1つ」という前提で、純Pythonで素朴に実装する。
ライブラリに頼らず自分で書くことで、各指標が"何を数えているか"がはっきりわかる。

用語：
  ranked_sources … 検索が返したチャンクの出どころを、近い順に並べたリスト
                    例: ["zangyo.md", "shucchou.md", "kenshu.md", ...]
  relevant       … その質問の正解の出どころ（例: "zangyo.md"）
"""


def recall_at_k(ranked_sources: list[str], relevant: str, k: int) -> float:
    """上位k件の中に正解の出どころが含まれていれば 1.0、なければ 0.0。

    正解が1つなので、ここでの Recall@k は実質「上位kで当てられたか（Hit@k）」。
    検索が正解を"取りこぼさなかったか"を見る指標。
    """
    return 1.0 if relevant in ranked_sources[:k] else 0.0


def reciprocal_rank(ranked_sources: list[str], relevant: str) -> float:
    """正解が何番目に出たかの逆数。1位なら1.0、2位なら0.5、3位なら0.33…。

    「正解をどれだけ上位に持ってこられたか（順位の良さ）」を見る。
    見つからなければ 0.0。これの平均が MRR（平均逆順位）。
    """
    for i, source in enumerate(ranked_sources):
        if source == relevant:
            return 1.0 / (i + 1)
    return 0.0


def fact_coverage(answer: str, facts: list[str]) -> float:
    """生成された回答が、含むべき事実をどれだけ網羅したか（0.0〜1.0）。

    数字のカンマ表記ゆれ（3,000 と 3000）を吸収するため、比較時に
    カンマと空白を除いて部分一致を見る。生成評価の素朴な"正確さ"の代理指標。
    """
    if not facts:
        return 1.0
    norm_answer = answer.replace(",", "").replace(" ", "")
    hit = sum(1 for f in facts if f.replace(",", "").replace(" ", "") in norm_answer)
    return hit / len(facts)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
