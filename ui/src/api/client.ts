import type { ChatResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export type Mode = "router" | "agent";

export async function chat(
  question: string,
  includeTrace = true,
  mode: Mode = "router",
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      stream: false,
      include_trace: includeTrace,
      mode,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export async function health(): Promise<{ status: string; agent_available: boolean }> {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}
