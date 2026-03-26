import { useCallback, useState } from "react";
import { chat, chatAgentStream, type HistoryEntry, type Mode } from "../api/client";
import type { AgentStepEvent, ChatMessage, TraceResponse } from "../types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [agentSteps, setAgentSteps] = useState<AgentStepEvent[]>([]);
  const [currentTrace, setCurrentTrace] = useState<TraceResponse | null>(null);
  const [mode, setMode] = useState<Mode>("router");

  const send = useCallback(
    async (question: string) => {
      const userMsg: ChatMessage = { role: "user", content: question };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setAgentSteps([]);

      // Build conversation history from prior messages
      const history: HistoryEntry[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        if (mode === "agent") {
          await chatAgentStream(
            question,
            (step) => setAgentSteps((prev) => [...prev, step]),
            (answer) => {
              const assistantMsg: ChatMessage = {
                role: "assistant",
                content: answer.answer,
                trace: answer.trace,
                sources: answer.sources,
                query_pattern: answer.query_pattern,
                timing_ms: answer.trace?.total_ms,
              };
              setMessages((prev) => [...prev, assistantMsg]);
              if (answer.trace) setCurrentTrace(answer.trace);
            },
            (errorMsg) => {
              const errMsg: ChatMessage = {
                role: "assistant",
                content: `Error: ${errorMsg}`,
              };
              setMessages((prev) => [...prev, errMsg]);
            },
            history,
          );
        } else {
          const res = await chat(question, true, mode, history);
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
        }
      } catch (err) {
        const errMsg: ChatMessage = {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        };
        setMessages((prev) => [...prev, errMsg]);
      } finally {
        setLoading(false);
        setAgentSteps([]);
      }
    },
    [mode],
  );

  return { messages, loading, agentSteps, send, currentTrace, mode, setMode };
}
