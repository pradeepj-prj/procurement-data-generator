import type { AgentStepEvent, ChatResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export type Mode = "router" | "agent";

export interface HistoryEntry {
  role: "user" | "assistant";
  content: string;
}

export async function chat(
  question: string,
  includeTrace = true,
  mode: Mode = "router",
  history?: HistoryEntry[],
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      stream: false,
      include_trace: includeTrace,
      mode,
      history: history?.length ? history : undefined,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export async function chatAgentStream(
  question: string,
  onStep: (step: AgentStepEvent) => void,
  onAnswer: (answer: ChatResponse) => void,
  onError: (msg: string) => void,
  history?: HistoryEntry[],
): Promise<void> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      stream: true,
      include_trace: true,
      mode: "agent",
      history: history?.length ? history : undefined,
    }),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (!payload) continue;

      try {
        const event = JSON.parse(payload);
        if (event.event === "step") onStep(event);
        else if (event.event === "answer") onAnswer(event);
        else if (event.event === "error") onError(event.message);
      } catch {
        // ignore unparseable lines
      }
    }
  }
}

export async function health(): Promise<{ status: string; agent_available: boolean }> {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}
