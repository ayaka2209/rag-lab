"""
RAG学習ラボの API（FastAPI）。

エンドポイント:
  GET  /health         動作確認
  POST /ingest_sample  data/sample.md を取り込む（デモ用・ボディ不要）
  POST /ingest         任意テキストを取り込む {source, text}
  POST /ask            質問する {question, top_k?} → 回答＋根拠チャンク

起動:
  cd rag-lab && uvicorn app.main:app --reload --port 8770
  ドキュメント画面: http://localhost:8770/docs
"""

from pathlib import Path

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import ingest, retrieval
from .database import get_db
from .db_init import init_db

app = FastAPI(title="RAG学習ラボ", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    # 起動時に拡張とテーブルを用意する
    init_db()


# --- リクエスト/レスポンスの型 ---
class IngestRequest(BaseModel):
    source: str
    text: str


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


# --- エンドポイント ---
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest_sample")
def ingest_sample(db: Session = Depends(get_db)) -> dict:
    sample_path = Path(__file__).resolve().parent.parent / "data" / "sample.md"
    text = sample_path.read_text(encoding="utf-8")
    return ingest.ingest_text(db, source=sample_path.name, text=text)


@app.post("/ingest")
def ingest_endpoint(req: IngestRequest, db: Session = Depends(get_db)) -> dict:
    return ingest.ingest_text(db, source=req.source, text=req.text)


@app.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)) -> dict:
    return retrieval.answer(db, question=req.question, top_k=req.top_k)
