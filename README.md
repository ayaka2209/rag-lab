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

## Phase の進め方

- **Phase1（いまここ）**：動く最小RAG（このディレクトリ）
- Phase2：評価の土台（Recall@k / Ragas）— 「精度を数字で測る」
- Phase3：チャンク戦略の実験
- Phase4：ハイブリッド検索＋リランキング
- Phase5：応用（マルチクエリ、HyDE など）
