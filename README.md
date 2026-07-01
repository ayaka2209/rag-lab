# RAG学習ラボ（rag-lab）

経費アプリ本体とは**完全に独立**した、RAG（検索拡張生成）を学ぶための練習場。
Phase1 として「**文書を取り込んで、質問に根拠付きで答える**」最小構成を作る。

- 埋め込み・生成：**Gemini（無料）** … APIキー1つだけ
- ベクトルDB：**pgvector**（専用Postgres・ポート5433・本体に触れない）
- API：**FastAPI** の `/ask`

```
質問 → 質問をベクトル化 → pgvectorで意味が近いチャンクを検索
     → 取得した文章＋質問でプロンプト → Geminiが根拠付きで回答
```

## ディレクトリ構成

```
rag-lab/
  docker-compose.yml   pgvector入りPostgres（ポート5433）
  requirements.txt
  .env.example         GEMINI_API_KEY と接続先
  data/sample.md       デモ用の架空・社内文書
  app/
    config.py          設定（モデル名・チャンクサイズ等）
    database.py        DB接続
    models.py          Document / Chunk（embeddingはVector型）
    chunking.py        チャンク分割（Phase1: 固定長＋オーバーラップ）
    gemini_client.py   Geminiの埋め込み・生成ラッパー
    ingest.py          取り込み（分割→埋め込み→保存）
    retrieval.py       検索＋回答生成（RAG本体）
    db_init.py         pgvector拡張の有効化＋テーブル作成
    main.py            FastAPI（/health, /ingest_sample, /ingest, /ask）
```

## セットアップ手順

```bash
cd rag-lab

# 1) Gemini APIキーを用意（https://aistudio.google.com/apikey で無料取得）
cp .env.example .env
#   → .env を開いて GEMINI_API_KEY を貼り付ける

# 2) pgvector入りPostgresを起動（本体の5432とは別の5433）
docker compose up -d

# 3) Python環境（本体の .venv311 を使うか、専用に作る）
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4) APIサーバ起動（本体8765とぶつからないよう8770）
uvicorn app.main:app --reload --port 8770
```

## 動かしてみる

```bash
# 動作確認
curl http://localhost:8770/health

# サンプル文書を取り込む（チャンク分割→埋め込み→保存）
curl -X POST http://localhost:8770/ingest_sample

# 質問する
curl -X POST http://localhost:8770/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "リモートワークは週何日まで？"}'
```

ブラウザで http://localhost:8770/docs を開くと、画面から各APIを試せる。

## フロントエンド（チャット画面）

`frontend/` に React + TypeScript + Vite 製のチャット画面がある。
普通のユーザーが質問を打って、根拠付きの回答を見られる。

### 起動手順（毎回これ）

**ターミナル①：バックエンド**
```bash
cd rag-lab
docker compose up -d                          # pgvector（まだなら）
.venv/bin/uvicorn app.main:app --port 8770    # API（:8770）
```

**ターミナル②：フロントエンド**
```bash
cd rag-lab/frontend
nvm use 18        # ★必須。システムのNode16ではViteが動かない
npm run dev       # → http://localhost:5173
```

ブラウザで **http://localhost:5173** を開く。

### 初回だけ
```bash
cd rag-lab/frontend
nvm use 18
npm install
```

### 仕組み・ハマりどころ
- フロントの `/ask` 呼び出しは Vite の proxy（`vite.config.ts`）が裏で
  `127.0.0.1:8770` に転送する。だから CORS 設定は不要で backend は無改造。
- proxy先は `localhost` ではなく **`127.0.0.1`**。Node18 は localhost を
  IPv6(::1) に解決し、IPv4で待つ uvicorn に繋がらず 500 になるため。
- 型定義は `src/api.ts`（`AskResponse` / `Chunk`）、画面は `src/App.tsx`。

## Phase の進め方

- **Phase1（完了）**：動く最小RAG（このディレクトリ）
- **フロント（完了）**：`frontend/` のチャット画面（React+TS+Vite）
- **Phase2（完了）**：評価の土台 — `eval/`（Recall@k / MRR / 事実カバー率 / 忠実性）。
  詳細は [`eval/README.md`](eval/README.md)
- **Phase3（完了）**：チャンク戦略の実験 — `eval/compare_chunking.py`。
  分割の戦略・サイズを変えて精度を比較（`chunking.py` に fixed/sentence 戦略）
- **Phase4（完了）**：ハイブリッド検索（ベクトル＋キーワード(pg_trgm)をRRF融合）＋
  リランキング（クロスエンコーダ・ローカル）。`retrieval.search(method="vector"|
  "keyword"|"hybrid"|"rerank")` ／ `eval/compare_search.py`
- Phase5：応用（マルチクエリ、HyDE など）
- Phase4：ハイブリッド検索＋リランキング
- Phase5：応用（マルチクエリ、HyDE など）
