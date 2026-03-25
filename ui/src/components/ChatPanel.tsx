import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (question: string) => void;
  onEntityClick?: (id: string) => void;
}

function SourceBadges({
  sources,
  onClick,
}: {
  sources: string[];
  onClick?: (id: string) => void;
}) {
  if (!sources.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {sources.map((s) => (
        <button
          key={s}
          onClick={() => onClick?.(s)}
          className="px-1.5 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 rounded font-mono"
        >
          {s}
        </button>
      ))}
    </div>
  );
}

export function ChatPanel({ messages, loading, onSend, onEntityClick }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    onSend(q);
  };

  return (
    <div className="flex flex-col h-full border-r">
      <div className="px-3 py-2 border-b bg-gray-900 text-sm font-medium text-gray-300">
        Chat
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "text-right" : ""}>
            {msg.role === "user" ? (
              <span className="inline-block bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm max-w-[90%]">
                {msg.content}
              </span>
            ) : (
              <div className="bg-gray-800 rounded-lg px-3 py-2 text-sm">
                <div className="prose prose-sm prose-invert max-w-none [&_p]:my-1 [&_ul]:my-1 [&_li]:my-0.5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  {msg.query_pattern && (
                    <span className="px-1.5 py-0.5 text-xs bg-gray-700 rounded">
                      {msg.query_pattern}
                    </span>
                  )}
                  {msg.timing_ms != null && (
                    <span className="text-xs text-gray-500">
                      {(msg.timing_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
                <SourceBadges
                  sources={msg.sources ?? []}
                  onClick={onEntityClick}
                />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t p-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about procurement data..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
