"""
評価・デモ用のサンプルPDFを生成する（架空・社内規程集）。

わざと「似た用語（申請・承認・上限・精算・日数）が大量に出る」構成にして、
ベクトル検索が紛れやすい"難しめ"のデータにしている。表も入れて、PDF抽出時に
レイアウトがどう崩れるか（実データの洗礼）を観察できるようにする。

実行: .venv/bin/python scripts/make_sample_pdf.py
出力: data/pdf/kitei.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent.parent / "data" / "pdf" / "kitei.pdf"

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
BODY = ParagraphStyle("body", fontName="HeiseiKakuGo-W5", fontSize=10.5, leading=17)
H2 = ParagraphStyle("h2", fontName="HeiseiKakuGo-W5", fontSize=13, leading=20, spaceBefore=10, spaceAfter=4)
TITLE = ParagraphStyle("title", fontName="HeiseiKakuGo-W5", fontSize=18, leading=24, spaceAfter=10)

# わざと似た言い回しを多用した規程セクション（検索が紛れやすいように）
SECTIONS = [
    ("第1条 出張の事前申請", [
        "従業員が出張する場合は、出発日の3営業日前までに出張申請書を上長へ提出し、承認を得なければならない。",
        "緊急の出張については、口頭で上長の承認を得たうえで、事後3営業日以内に申請書を提出するものとする。",
    ]),
    ("第2条 出張日当", [
        "国内出張の日当は、一般社員は1日あたり3000円、管理職は1日あたり4500円とする。",
        "海外出張の日当は別表に定めるところによる。日当は宿泊費および交通費とは別に支給する。",
    ]),
    ("第3条 宿泊費の上限", [
        "国内出張の宿泊費は、1泊あたり10000円を上限として実費を精算する。",
        "都市部（東京23区・大阪市・名古屋市）への出張については、1泊あたり13000円を上限とする。",
    ]),
    ("第4条 出張経費の精算", [
        "出張終了後は、7営業日以内に経費精算書を提出しなければならない。",
        "領収書は電子データで添付するものとし、原本の提出は不要とする。",
    ]),
    ("第5条 交通費の取扱い", [
        "交通費は最も経済的な経路により実費を精算する。通勤定期区間が含まれる場合は当該区間を控除する。",
        "新幹線のグリーン車利用は、片道4時間以上の移動に限り、上長の承認を得て認める。",
    ]),
    ("第6条 接待交際費の申請", [
        "接待交際費は、1件あたり10000円を超える場合、事前に申請し承認を得なければならない。",
        "接待の相手方・目的・人数を精算時に明記するものとする。",
    ]),
    ("第7条 備品購入の申請", [
        "業務に必要な備品の購入は、1万円を超える場合は事前申請を要し、総務部の承認を得る。",
        "1万円以下の消耗品は、部署長の承認により購入できる。",
    ]),
    ("第8条 書籍購入補助", [
        "業務に関連する書籍の購入費は、1人あたり月5000円を上限として会社が補助する。",
        "電子書籍も補助の対象に含める。購入後に領収書を提出するものとする。",
    ]),
    ("第9条 研修費用の補助", [
        "外部研修・セミナーの受講費用は、1人あたり年間50000円を上限として補助する。",
        "受講後は、7営業日以内に受講レポートを提出しなければならない。",
    ]),
    ("第10条 時間外勤務の申請", [
        "時間外勤務は事前申請を原則とし、月の上限は45時間とする。",
        "22時から翌5時までの深夜勤務については、25パーセントの割増賃金を支給する。",
    ]),
    ("第11条 リモートワークの申請", [
        "リモートワークは原則として週3日を上限とする。週4日以上を希望する場合は上長の事前承認を要する。",
        "リモートワーク中も、勤務時間内は連絡が取れる状態を保つものとする。",
    ]),
    ("第12条 有給休暇の申請", [
        "有給休暇は、原則として取得日の前日までに申請する。急病の場合は当日連絡でも認める。",
        "有給休暇は入社6か月後に10日付与し、未消化分は翌年度まで、最大20日を上限に繰り越せる。",
    ]),
]

# わざと表を入れる（PDF抽出で崩れやすい＝実データの洗礼）
TABLE_TITLE = "別表1 役職別・国内出張日当および宿泊費上限"
TABLE_DATA = [
    ["役職", "日当（円/日）", "宿泊費上限（円/泊）", "都市部上限（円/泊）"],
    ["一般社員", "3000", "10000", "13000"],
    ["主任", "3500", "10000", "13000"],
    ["管理職", "4500", "12000", "15000"],
    ["役員", "6000", "15000", "18000"],
]


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
        title="架空・社内経費規程集",
    )
    story = [Paragraph("架空・社内経費規程集", TITLE),
             Paragraph("本規程は出張・経費・各種手当の申請と精算について定める。（架空の内容です）", BODY),
             Spacer(1, 8)]
    for heading, paras in SECTIONS:
        story.append(Paragraph(heading, H2))
        for p in paras:
            story.append(Paragraph(p, BODY))

    story.append(Spacer(1, 12))
    story.append(Paragraph(TABLE_TITLE, H2))
    table = Table(TABLE_DATA, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
    ]))
    story.append(table)

    doc.build(story)
    print(f"生成しました: {OUT}")


if __name__ == "__main__":
    build()
