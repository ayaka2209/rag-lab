# rag-lab — Claude 向けガイド

RAG（検索拡張生成）の最小実装を学ぶ個人プロジェクト。
構成: React+TS+Vite（:5173）→ FastAPI（:8770・RAG本体）→ pgvector（:5433）。
埋め込み/生成は Gemini。経費アプリ keihi-kanri とは独立。

## 重要：作業前に rag-lab スキルを読む

起動手順・ファイル構成・ハマりどころ・Phaseの進め方など、このプロジェクトの
詳しい使い方は **`rag-lab` スキル**（`.claude/skills/rag-lab/SKILL.md`）にまとめてある。

rag-lab を**動かす・直す・機能追加する前に、必ず `rag-lab` スキルを参照**してから
判断・着手すること。ここ（CLAUDE.md）には要点だけ置き、詳細はスキル側を正とする。

## 最小限の注意点（詳細はスキル参照）

- フロントは **Node 18 必須**（`cd frontend && nvm use 18 && npm run dev`）。
- Gemini は `gemini-embedding-001`（埋め込み）/ `gemini-2.5-flash`（生成）を使う。
  他モデルは無料枠0や404で動かない。
- `.env` の `GEMINI_API_KEY` はコミットしない。
