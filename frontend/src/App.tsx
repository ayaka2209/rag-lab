import { useState } from "react";
import { ask, type AskResponse, type Chunk } from "./api";

// 画面に並べる1件の会話（質問と、それに対する回答）。
type Turn = {
  question: string;
  answer: string;
  contexts: Chunk[];
};

export default function App() {
  // useState =「画面が覚えておく値」。値が変わると画面が描き直される。
  const [input, setInput] = useState(""); // 入力中のテキスト
  const [turns, setTurns] = useState<Turn[]>([]); // これまでの会話
  const [loading, setLoading] = useState(false); // 問い合わせ中か
  const [error, setError] = useState<string | null>(null);

  async function handleAsk() {
    const question = input.trim();
    if (!question || loading) return;

    setError(null);
    setLoading(true);
    setInput("");

    try {
      const res: AskResponse = await ask(question);
      // 先頭に新しい会話を積む（最新が上に来る）
      setTurns((prev) => [
        { question, answer: res.answer, contexts: res.contexts },
        ...prev,
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "不明なエラー");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>🔎 RAG学習ラボ</h1>
        <p className="sub">
          社内文書（sample.md）を根拠に、Geminiが答えます。資料に無いことは「分かりません」と答えます。
        </p>
      </header>

      <div className="ask-bar">
        <input
          type="text"
          value={input}
          placeholder="例: リモートワークは週何日まで可能ですか？"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          disabled={loading}
        />
        <button onClick={handleAsk} disabled={loading || !input.trim()}>
          {loading ? "検索中…" : "質問する"}
        </button>
      </div>

      {error && <div className="error">⚠️ {error}</div>}

      <div className="turns">
        {turns.length === 0 && !loading && (
          <p className="empty">上の入力欄に質問を入れて「質問する」を押してください。</p>
        )}

        {turns.map((t, i) => (
          <article className="turn" key={i}>
            <div className="q">Q. {t.question}</div>
            <div className="a">{t.answer}</div>

            {/* RAGの肝：どのチャンクを根拠にしたかを開いて見せる */}
            <details className="sources">
              <summary>根拠にした資料（{t.contexts.length}件）を見る</summary>
              {t.contexts.map((c) => (
                <div className="chunk" key={c.chunk_id}>
                  <div className="chunk-meta">
                    チャンク#{c.chunk_index}（類似度 {c.similarity}）
                  </div>
                  <pre className="chunk-body">{c.content}</pre>
                </div>
              ))}
            </details>
          </article>
        ))}
      </div>
    </div>
  );
}
