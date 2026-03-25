import { useState } from "react";
import type { Span, TraceResponse } from "../types";

interface Props {
  trace: TraceResponse | null;
}

const SPAN_COLORS: Record<string, string> = {
  classify: "bg-purple-500",
  retrieve: "bg-green-500",
  generate: "bg-blue-500",
};

function SpanBar({ span, maxMs }: { span: Span; maxMs: number }) {
  const [expanded, setExpanded] = useState(false);
  const width = maxMs > 0 ? Math.max((span.duration_ms / maxMs) * 100, 2) : 0;
  const color =
    SPAN_COLORS[span.name] ??
    (span.name.startsWith("retrieve.") ? "bg-emerald-600" : "bg-gray-600");

  return (
    <div className="mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left group"
      >
        <div className="flex items-center gap-2 text-xs">
          <span className="w-3 text-gray-500">{expanded ? "v" : ">"}</span>
          <span className="text-gray-300 font-mono truncate flex-1">
            {span.name}
          </span>
          <span className="text-gray-500">{span.duration_ms.toFixed(0)}ms</span>
        </div>
        <div className="ml-5 mt-0.5 h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full ${color} rounded-full`}
            style={{ width: `${width}%` }}
          />
        </div>
      </button>

      {expanded && (
        <div className="ml-5 mt-1 text-xs text-gray-500 space-y-0.5 pl-2 border-l border-gray-800">
          {Object.entries(span.metadata).map(([k, v]) => (
            <div key={k}>
              <span className="text-gray-400">{k}:</span>{" "}
              {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </div>
          ))}
          {span.children.map((child, i) => (
            <SpanBar key={i} span={child} maxMs={maxMs} />
          ))}
        </div>
      )}
    </div>
  );
}

export function TracePanel({ trace }: Props) {
  if (!trace) {
    return (
      <div className="flex flex-col h-full border-l">
        <div className="px-3 py-2 border-b bg-gray-900 text-sm font-medium text-gray-300">
          Trace
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm p-4">
          Query trace will appear here
        </div>
      </div>
    );
  }

  const maxMs = Math.max(...trace.spans.map((s) => s.duration_ms), 1);

  return (
    <div className="flex flex-col h-full border-l">
      <div className="px-3 py-2 border-b bg-gray-900 text-sm font-medium text-gray-300 flex justify-between">
        <span>Trace</span>
        <span className="text-gray-500 font-mono text-xs">
          {trace.trace_id}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {/* Summary */}
        <div className="text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-400">Total</span>
            <span className="font-mono text-gray-200">
              {(trace.total_ms / 1000).toFixed(2)}s
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Pattern</span>
            <span className="font-mono text-gray-200">
              {trace.intent.pattern}
            </span>
          </div>
          {trace.intent.entity_id && (
            <div className="flex justify-between">
              <span className="text-gray-400">Entity</span>
              <span className="font-mono text-gray-200">
                {trace.intent.entity_id}
              </span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-gray-400">Nodes</span>
            <span className="font-mono text-gray-200">
              {trace.graph_nodes.length}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Edges</span>
            <span className="font-mono text-gray-200">
              {trace.graph_edges.length}
            </span>
          </div>
        </div>

        {/* Waterfall */}
        <div>
          <div className="text-xs text-gray-400 mb-2 font-medium">
            Pipeline
          </div>
          {trace.spans.map((span, i) => (
            <SpanBar key={i} span={span} maxMs={maxMs} />
          ))}
        </div>

        {/* LLM Info */}
        <div>
          <div className="text-xs text-gray-400 mb-1 font-medium">LLM</div>
          <div className="text-xs space-y-0.5 text-gray-500">
            <div>
              Model:{" "}
              <span className="text-gray-300">
                {trace.llm_request.model}
              </span>
            </div>
            <div>
              Prompt tokens:{" "}
              <span className="text-gray-300">
                ~{trace.llm_request.estimated_prompt_tokens}
              </span>
            </div>
            <div>
              Response tokens:{" "}
              <span className="text-gray-300">
                ~{trace.llm_response.estimated_tokens}
              </span>
            </div>
            <div>
              Latency:{" "}
              <span className="text-gray-300">
                {(trace.llm_response.latency_ms / 1000).toFixed(2)}s
              </span>
            </div>
          </div>
        </div>

        {/* Context snippet */}
        {trace.context_snippet && (
          <div>
            <div className="text-xs text-gray-400 mb-1 font-medium">
              Context
            </div>
            <pre className="text-xs text-gray-500 whitespace-pre-wrap bg-gray-900 p-2 rounded max-h-40 overflow-y-auto">
              {trace.context_snippet}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
