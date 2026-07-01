---
name: rag-lab
description: >
  rag-lab（RAG学習ラボ）プロジェクトの使い方・起動手順・構成・ハマりどころをまとめた案内。
  rag-lab のコード（app/ 配下のFastAPI/RAG実装、frontend/ のReact画面、pgvector）を
  読む・動かす・直す・機能追加するときは、まずこのスキルを読んでから作業すること。
  「サーバを起動して」「フロントを動かして」「RAGを直して」「取り込みたい」「質問が返らない」
  「次のPhaseを進めたい」など rag-lab に関する依頼では、説明なしに着手せず必ずこのスキルを参照する。
---

# rag-lab（RAG学習ラボ）

RAG（検索拡張生成）の最小実装を学ぶ個人プロジェクト。AIエンジニア/FDE案件応募で
「RAG実装経験」を示すために作成。経費アプリ keihi-kanri とは**完全に独立**したアプリ。

全体の流れ：
```
質問 → 質問をベクトル化 → pgvectorで意味が近いチャンクを検索
     → 取得チャンク＋質問でプロンプト → Geminiが根拠付きで回答
```

## 技術スタック（全部ローカル・無料）

| 層 | 採用 | ポート |
|---|---|---|
| フロント | React + TypeScript + Vite | 5173 |
| API | FastAPI（RAG本体） | 8770 |
| ベクトルDB | pgvector（専用Postgres・docker compose） | 5433 |
| 埋め込み | Gemini `gemini-embedding-001`（768次元） | - |
| 生成 | Gemini `gemini-2.5-flash` | - |

- Python: `.venv`（3.10/3.11）。Node: フロントは **nvm の v18** を使う。
- Gemカード: `.env` の `GEMINI_API_KEY`（`.gitignore`済み・コミットしない）。
- DB認証: user=`raglab` / password=`raglab_dev_password` / db=`raglab`。

## 起動手順（毎回これ）

3つのサーバが要る。順番に立てる。

**① ベクトルDB（pgvector）**
```bash
cd /Users/ayaka/rag-lab
docker compose up -d
```

**② バックエンド（FastAPI :8770）**
```bash
cd /Users/ayaka/rag-lab
.venv/bin/uvicorn app.main:app --port 8770
```

**③ フロントエンド（Vite :5173）**
```bash
cd /Users/ayaka/rag-lab/frontend
nvm use 18        # ★必須。システムのNode16ではViteが動かない
npm run dev
```

→ ブラウザで **http://localhost:5173**（チャット画面）。
開発者向けにAPIを直接叩くなら **http://localhost:8770/docs**。

起動済みか確認するワンライナー：
```bash
curl -s localhost:8770/health   # backend → {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}" localhost:5173   # frontend → 200
docker compose ps               # pgvector が Up(healthy) か
```

## ファイル構成

```
rag-lab/
  docker-compose.yml      pgvector入りPostgres（5433）
  app/
    config.py             設定（モデル名・チャンク500/overlap100・top_k=4）
    database.py           DB接続（経費アプリとは別DB）
    models.py             Document / Chunk（embeddingはVector(768)）
    chunking.py           チャンク分割（固定長＋オーバーラップ）
    gemini_client.py      Gemini埋め込み・生成。非対称embedding＋503リトライ
    ingest.py             取り込み（分割→埋め込み→保存）
    retrieval.py          検索（cosine距離）＋プロンプト組立＋生成＝RAG本体
    db_init.py            CREATE EXTENSION vector＋テーブル作成
    main.py               FastAPI（/health, /ingest_sample, /ingest, /ask）
  data/sample.md          デモ用の架空・社内文書
  eval/                    Phase2 評価の土台（精度を数字で測る）
    corpus/               評価用コーパス（別トピックの小文書10件）
    dataset.json          ゴールデンQ&A（質問→正解source＋含むべき事実）
    metrics.py            Recall@k / MRR / 事実カバー率（純Python）
    run_eval.py           取り込み→検索→採点ランナー
    corpus_long/handbook.md  Phase3用の長文コーパス（分割の差を出すため）
    compare_chunking.py   Phase3 チャンク戦略の比較実験
    corpus_codes/         Phase4用（型番付き＋言い換え。検索方式の差を出す）
    dataset_codes.json    Phase4用ゴールデン
    compare_search.py     Phase4 vector/keyword/hybrid の比較実験
  frontend/
    src/api.ts            ★APIの型定義（AskResponse / Chunk）＝TS学習の核
    src/App.tsx           チャット画面本体（useState、根拠チャンク開閉表示）
    src/main.tsx          入口
    src/index.css         配色（Air Seoul風：白背景＋ミントグリーン #1ec8a5）
    vite.config.ts        proxy設定（/ask を backend に転送）
```

## ハマりどころ（重要）

- **Geminiのモデル選定**：このGoogleプロジェクトでは `text-embedding-004` は404、
  `gemini-2.0-flash`系は無料枠0(429)。→ 埋め込みは `gemini-embedding-001`、
  生成は `gemini-2.5-flash`。勝手に他モデルへ変えない。
- **無料枠は2系統**：生成=**1日約20回**/モデル（モデルごとに別枠。flash枯れたら
  flash-lite へ自動フォールバック）。埋め込み=**毎分約100回**。どちらも429は待って
  自動再試行する（generate=モデル切替, _embed=55秒待ち）。デモや--judgeで生成枠が枯れがち。
- **Viteのproxy先は `127.0.0.1`**（`localhost`にしない）。Node18は localhost を
  IPv6(::1) に解決し、IPv4で待つ uvicorn に繋がらず 500 になる。
- **フロントは Node 18 必須**。`nvm use 18` を忘れると Node16 でViteが動かない。
- **CORSは不要**：フロント→backend は Vite proxy 経由なので backend は無改造でよい。

## データの取り込み

検索対象は pgvector の `chunks` テーブルに入れた文書だけ。Web全体は検索しない。
```bash
# デモ用 sample.md を取り込む
curl -X POST localhost:8770/ingest_sample
# 任意テキストを取り込む
curl -X POST localhost:8770/ingest -H "Content-Type: application/json" \
  -d '{"source":"メモ","text":"取り込みたい本文"}'
```
資料に無いことを聞くと「資料からは分かりません」と幻覚せず答えるのが正しい挙動。

## 評価（Phase2）の回し方

精度を数字で測る土台。詳細は `eval/README.md`。
```bash
.venv/bin/python -m eval.run_eval                # 検索のみ(Recall@k/MRR)。埋め込みのみで安い
.venv/bin/python -m eval.run_eval --judge        # 生成も(事実カバー率)。LLM呼び出し
.venv/bin/python -m eval.run_eval --judge --faithfulness  # 忠実性判定も
.venv/bin/python -m eval.run_eval --reset        # コーパス入れ直してから
```
- ゴールデンの正解は「出どころ(source)」で持つ＝設定を変えて入れ直しても評価が再現できる。
- **生成(gemini-2.5-flash)は無料枠の1日上限が小さい(20前後)**。--judge は枠を食うので
  日に何度も回せない。429は途中集計して優雅に停止する作り。検索評価は枠が別で気軽に回せる。
- 現状トピックが明確に分かれ Recall@1=1.000（満点）。物差しとしての価値はPhase3で変更の
  良し悪しを数字で判定するときに出る。難化（言い換え・distractor追加）も今後の課題。

## Phaseロードマップ

- **Phase1（完了）**：動く最小RAG。取り込み→検索→根拠付き回答。
- **フロント追加（完了）**：React+TS+Vite のチャット画面。
- **Phase2（完了）**：評価の土台。`eval/` に Recall@k/MRR/事実カバー率/忠実性。
- **Phase3（完了）**：チャンク戦略の実験。`eval/compare_chunking.py` で戦略×サイズを
  カバー@1/2/4 で比較。chunking.py に fixed/sentence 戦略。k=1で分割の差が出る。
- **Phase4（一部・ハイブリッド検索）**：`retrieval.search(method=...)` に keyword(pg_trgm)
  と hybrid(RRF融合) を追加。`eval/compare_search.py` で3方式比較。結果=このデータでは
  vectorが既に満点でhybridは上回らず、keywordは言い換えに弱い→hybridは最良に並ぶ（取り
  こぼし最小）。**リランキングは未実装**（次。Geminiを使う方式は生成枠に注意）。
- Phase4：ハイブリッド検索＋リランキング
- Phase5：応用（マルチクエリ、HyDE など）

## 作業時の心得

- ユーザーはRAG/TypeScriptを学習中。専門用語は噛み砕いて説明し、なぜそうするかを添える。
- backend を変えずに済む方法（proxyなど）を優先し、既存環境（keihi-kanri / Node16）に影響を出さない。
