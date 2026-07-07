// バックエンド（FastAPI）とやり取りする部分。
//
// ここが TypeScript の「型」の威力が一番わかる場所。
// API が返すデータの「形」を先に type で宣言しておくと、
// 画面側で data.answer や c.content を書くとき、エディタが
// 補完してくれて、タイプミスは即赤線で教えてくれる。

// /ask が返す「根拠チャンク」1件の形。
// retrieval.py の search() が返す dict と対応している。
export type Chunk = {
  chunk_id: number;
  document_id: number;
  chunk_index: number;
  content: string;
  similarity: number; // 1に近いほど質問に意味が近い
};

// /ask 全体のレスポンスの形。
export type AskResponse = {
  answer: string;
  contexts: Chunk[];
};

// 質問を送って回答を受け取る関数。
// async/await: サーバの返事を「待つ」処理。
export async function ask(question: string, topK?: number): Promise<AskResponse> {
  const res = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK ?? null }),
  });

  if (!res.ok) {
    throw new Error(`サーバエラー (${res.status})。バックエンドは起動していますか？`);
  }

  // res.json() の戻り値が AskResponse 型だと宣言しておく。
  // 以降このデータは「answer と contexts を持つ」と TS が把握する。
  return (await res.json()) as AskResponse;
}

// PDF取り込みのレスポンスの形。
export type IngestResponse = {
  source: string;
  chunks: number;
};

// PDFファイルをアップロードして取り込む関数。
// FormData に file を詰めて /ingest_pdf に送る（Vite proxy 経由で backend へ）。
export async function ingestPdf(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch("/ingest_pdf", { method: "POST", body: form });
  if (!res.ok) {
    // backend は失敗時に {detail: "..."} を返すので、それを拾う。
    let detail = `取り込みに失敗しました (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* JSONでなければ既定メッセージのまま */
    }
    throw new Error(detail);
  }
  return (await res.json()) as IngestResponse;
}
