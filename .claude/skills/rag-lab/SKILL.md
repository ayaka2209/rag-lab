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
  生成は `gemini-2.5-flash` を使う。勝手に他モデルへ変えない。
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

## Phaseロードマップ

- **Phase1（完了）**：動く最小RAG。取り込み→検索→根拠付き回答。
- **フロント追加（完了）**：React+TS+Vite のチャット画面。
- Phase2：評価（Recall@k / Ragas）— 精度を数字で測る
- Phase3：チャンク戦略の実験
- Phase4：ハイブリッド検索＋リランキング
- Phase5：応用（マルチクエリ、HyDE など）

## 作業時の心得

- ユーザーはRAG/TypeScriptを学習中。専門用語は噛み砕いて説明し、なぜそうするかを添える。
- backend を変えずに済む方法（proxyなど）を優先し、既存環境（keihi-kanri / Node16）に影響を出さない。
