import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentStepEvent, ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  agentSteps: AgentStepEvent[];
  onSend: (question: string) => void;
  onNewChat?: () => void;
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

function AgentStepLog({ steps }: { steps: AgentStepEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps]);

  return (
    <div className="bg-gray-800/50 rounded-lg px-3 py-2 space-y-1.5 text-sm">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2 text-gray-400">
          {step.type === "reasoning" ? (
            <>
              <span className="text-purple-400 mt-0.5 shrink-0 text-xs font-medium">
                thinking
              </span>
              <span className="text-gray-300 text-xs">
                {step.tool_calls?.length
                  ? `Calling ${step.tool_calls.join(", ")}`
                  : "Formulating answer..."}
                {step.thought && (
                  <span className="text-gray-500 ml-1">
                    — {step.thought.slice(0, 120)}
                    {step.thought.length > 120 ? "..." : ""}
                  </span>
                )}
              </span>
            </>
          ) : (
            <>
              <span className="text-green-400 mt-0.5 shrink-0 text-xs font-medium">
                result
              </span>
              <span className="text-gray-300 text-xs">
                <span className="font-mono text-emerald-300">
                  {step.tool_name}
                </span>
                {step.result_preview && (
                  <span className="text-gray-500 ml-1">
                    — {step.result_preview.slice(0, 100)}
                    {step.result_preview.length > 100 ? "..." : ""}
                  </span>
                )}
              </span>
            </>
          )}
        </div>
      ))}
      <div className="flex items-center gap-2 text-gray-500 text-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
        Working...
      </div>
      <div ref={endRef} />
    </div>
  );
}

export function ChatPanel({ messages, loading, agentSteps, onSend, onNewChat, onEntityClick }: Props) {
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
      <div className="px-3 py-2 border-b bg-gray-900 text-sm font-medium text-gray-300 flex justify-between items-center">
        <span>Chat</span>
        {messages.length > 0 && (
          <button
            onClick={onNewChat}
            className="text-xs text-gray-500 hover:text-gray-300 px-2 py-0.5 rounded hover:bg-gray-800"
          >
            New Chat
          </button>
        )}
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
          agentSteps.length > 0 ? (
            <AgentStepLog steps={agentSteps} />
          ) : (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <span className="animate-pulse">Thinking...</span>
            </div>
          )
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
