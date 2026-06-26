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
