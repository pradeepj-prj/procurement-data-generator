import type { ChatResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export async function chat(
  question: string,
  includeTrace = true,
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      stream: false,
      include_trace: includeTrace,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function health(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}
