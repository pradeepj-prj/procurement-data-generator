export interface Span {
  name: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  metadata: Record<string, unknown>;
  children: Span[];
}

export interface TraceResponse {
  trace_id: string;
  question: string;
  total_ms: number;
  intent: {
    pattern: string;
    entity_id?: string | null;
    entity_type?: string | null;
    search_query?: string | null;
  };
  graph_nodes: string[];
  graph_edges: Array<{ source: string; target: string; edge_type: string }>;
  spans: Span[];
  context_snippet: string;
  llm_request: {
    model: string;
    message_count: number;
    estimated_prompt_tokens: number;
  };
  llm_response: { estimated_tokens: number; latency_ms: number };
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  query_pattern: string;
  context_snippet: string;
  trace?: TraceResponse;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  trace?: TraceResponse;
  sources?: string[];
  query_pattern?: string;
  timing_ms?: number;
}
