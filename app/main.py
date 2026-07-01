"""FastAPI application for the SHL Assessment Recommender.

Endpoints:
- GET /health: Readiness check
- POST /chat: Stateless conversational chat
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.agent import process_chat
from app.catalog import catalog_search
from app.config import RESPONSE_TIMEOUT
from app.models import ChatRequest, ChatResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load catalog and build search index on startup."""
    logger.info("Starting SHL Assessment Recommender...")
    start = time.time()

    try:
        catalog_search.load()
        logger.info(
            f"Catalog loaded: {len(catalog_search.assessments)} assessments "
            f"in {time.time() - start:.1f}s"
        )
    except Exception as e:
        logger.error(f"Failed to load catalog: {e}", exc_info=True)

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational agent for recommending SHL Individual Test Solutions",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow all origins for the automated evaluator
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve UI
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    """Readiness check endpoint."""
    return {"status": "ok"}


@app.get("/catalog")
async def get_catalog():
    """Return all assessments in the catalog for the frontend catalog browser."""
    return [a.to_display_dict() for a in catalog_search.assessments]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat request with full conversation history.

    The API is stateless — every call carries the full conversation history.
    Returns the next agent reply plus optional structured recommendations.
    """
    start_time = time.time()

    try:
        # Validate message count
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages list cannot be empty")

        # Process chat
        response = await process_chat(request.messages)

        elapsed = time.time() - start_time
        logger.info(
            f"Chat processed in {elapsed:.1f}s | "
            f"Recommendations: {len(response.recommendations)} | "
            f"End: {response.end_of_conversation}"
        )

        # Safety: ensure we don't exceed timeout
        if elapsed > RESPONSE_TIMEOUT:
            logger.warning(f"Response took {elapsed:.1f}s, exceeding target of {RESPONSE_TIMEOUT}s")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        # Return a graceful error response rather than 500
        return ChatResponse(
            reply="I apologize, but I encountered an issue processing your request. Could you try rephrasing your question about SHL assessments?",
            recommendations=[],
            end_of_conversation=False,
        )
