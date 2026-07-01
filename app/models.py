"""Pydantic models for the SHL Assessment Recommender API.

Strict schema matching the evaluator's expectations.
"""

from pydantic import BaseModel, Field
from typing import Literal


class Message(BaseModel):
    """A single message in the conversation history."""
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Incoming chat request with full conversation history."""
    messages: list[Message] = Field(
        ...,
        min_length=1,
        description="Full conversation history. Must contain at least one message.",
    )


class Recommendation(BaseModel):
    """A single assessment recommendation from the SHL catalog."""
    name: str = Field(..., description="Assessment name from the SHL catalog")
    url: str = Field(..., description="Direct URL to the assessment in the SHL catalog")
    test_type: str = Field(..., description="Test type code (e.g., A, K, P, S)")


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    reply: str = Field(
        ...,
        description="The agent's natural language response",
    )
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Empty when gathering context or refusing. 1-10 items when recommending.",
    )
    end_of_conversation: bool = Field(
        default=False,
        description="True only when the agent considers the task complete.",
    )
