import { useCallback, useState } from "react";
import { chat } from "../api/client";
import type { ChatMessage, TraceResponse } from "../types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentTrace, setCurrentTrace] = useState<TraceResponse | null>(null);

  const send = useCallback(async (question: string) => {
    const userMsg: ChatMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await chat(question, true);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: res.answer,
        trace: res.trace,
        sources: res.sources,
        query_pattern: res.query_pattern,
        timing_ms: res.trace?.total_ms,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (res.trace) setCurrentTrace(res.trace);
    } catch (err) {
      const errMsg: ChatMessage = {
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }, []);

  return { messages, loading, send, currentTrace };
}
