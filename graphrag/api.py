"""FastAPI REST endpoint for the procurement GraphRAG."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
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


# ── Models ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    query_pattern: str
    context_snippet: str


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

        async def generate():
            for token in _router._llm.chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    result = _router.answer(req.question)
    return ChatResponse(**result)


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
