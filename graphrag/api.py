"""FastAPI REST endpoint for the procurement GraphRAG."""

from __future__ import annotations

import argparse
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graphrag.config import GraphRAGConfig, get_backend
from graphrag.llm.genai_hub import GenAIHubClient
from graphrag.llm.router import IntentRouter

# ── Globals ──────────────────────────────────────────────────────────────────

_router: IntentRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize backend + LLM on startup."""
    global _router
    config = GraphRAGConfig.from_env()
    backend = get_backend(config)
    llm = GenAIHubClient(config)
    _router = IntentRouter(backend, llm)
    yield


app = FastAPI(
    title="Procurement GraphRAG",
    description="Natural language Q&A over the procurement knowledge graph",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    stream: bool = False
    include_trace: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    query_pattern: str
    context_snippet: str
    trace: dict[str, Any] | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse | StreamingResponse:
    assert _router is not None, "Router not initialized"

    if req.stream:
        intent = _router.classify(req.question)
        context = _router.retrieve(intent)

        from graphrag.llm.prompts import build_rag_messages

        messages = build_rag_messages(req.question, context)

        if req.include_trace:
            # For streaming + trace: stream tokens, then send trace as final event
            from graphrag.observability.trace import (
                QueryTrace,
                Span,
                TracingLLMProxy,
                _now_ms,
            )

            trace = QueryTrace(question=req.question)
            trace.intent = {
                "pattern": intent.pattern,
                "entity_id": intent.entity_id,
            }

            async def generate_with_trace() -> AsyncGenerator[str, None]:
                gen_span = Span(name="generate", start_ms=_now_ms())
                tokens: list[str] = []
                for token in _router._llm.chat_stream(messages):
                    tokens.append(token)
                    yield f"data: {token}\n\n"
                gen_span.end_ms = _now_ms()
                full_response = "".join(tokens)
                gen_span.metadata = {
                    "model": getattr(_router._llm, "model_name", "unknown"),
                    "estimated_response_tokens": len(full_response) // 4,
                    "latency_ms": round(gen_span.duration_ms, 2),
                }
                trace.spans.append(gen_span)
                trace.total_ms = gen_span.duration_ms
                trace.context_snippet = context[:500]
                yield f"data: {json.dumps({'trace': trace.to_dict()})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_with_trace(), media_type="text/event-stream"
            )

        async def generate() -> AsyncGenerator[str, None]:
            for token in _router._llm.chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    # Non-streaming
    if req.include_trace:
        result, trace = _router.answer_with_trace(req.question)
        result["trace"] = trace.to_dict()
        return ChatResponse(**result)

    result = _router.answer(req.question)
    return ChatResponse(**result)


# ── Static file serving (UI) ────────────────────────────────────────────────

_ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_ui_dist), html=True), name="ui")


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Procurement GraphRAG API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "graphrag.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
