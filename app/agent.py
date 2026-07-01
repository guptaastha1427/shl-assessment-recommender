"""Core conversational agent for SHL Assessment recommendation.

Implements the Extract → Decide → Act pipeline:
1. Extract structured requirements from conversation history
2. Classify user intent (clarify/recommend/refine/compare/refuse)
3. Execute appropriate behavior
"""

import json
import logging
import re
from typing import Optional

import google.generativeai as genai

from app.catalog import Assessment, catalog_search
from app.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_RECOMMENDATIONS, MAX_TURNS
from app.models import ChatResponse, Message, Recommendation
from app.prompts import (
    CLARIFICATION_PROMPT,
    COMPARISON_PROMPT,
    RECOMMENDATION_PROMPT,
    REFUSAL_PROMPT,
    REQUIREMENT_EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _format_conversation(messages: list[Message]) -> str:
    """Format message list into a readable conversation string."""
    lines = []
    for msg in messages:
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def _call_llm(prompt: str, system_prompt: str = SYSTEM_PROMPT, temperature: float = 0.3) -> str:
    """Call Gemini LLM with error handling."""
    try:
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=1024,
            ),
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Remove markdown code blocks if present
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json or ``` prefix and ``` suffix
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.error(f"Failed to parse JSON from LLM response: {text[:200]}")
        return {}


def _extract_requirements(messages: list[Message]) -> dict:
    """Extract structured requirements from conversation history using LLM."""
    conversation = _format_conversation(messages)
    prompt = REQUIREMENT_EXTRACTION_PROMPT.format(conversation=conversation)

    response = _call_llm(prompt, temperature=0.1)
    requirements = _extract_json(response)

    if not requirements:
        # Fallback: basic heuristic extraction
        logger.warning("LLM requirement extraction failed, using fallback")
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user_msg = msg.content
                break

        requirements = {
            "role_title": None,
            "seniority": None,
            "skills_needed": [],
            "assessment_types_wanted": [],
            "constraints": {},
            "comparison_assessments": [],
            "job_description_text": last_user_msg,
            "is_sufficient": len(last_user_msg.split()) > 5,
            "intent": "recommend" if len(last_user_msg.split()) > 10 else "clarify",
            "refinement_action": None,
        }

    return requirements


def _build_search_query(requirements: dict) -> str:
    """Build a search query from extracted requirements."""
    parts = []

    if requirements.get("role_title"):
        parts.append(requirements["role_title"])

    if requirements.get("seniority"):
        parts.append(f"{requirements['seniority']} level")

    if requirements.get("skills_needed"):
        parts.append(" ".join(requirements["skills_needed"]))

    if requirements.get("assessment_types_wanted"):
        type_map = {
            "cognitive": "ability aptitude reasoning",
            "personality": "personality behaviour OPQ",
            "knowledge": "knowledge skills technical",
            "skills": "skills technical programming",
            "situational_judgment": "situational judgement SJT",
            "simulation": "simulation work sample",
            "competency": "competency behavioral",
        }
        for at in requirements["assessment_types_wanted"]:
            if at.lower() in type_map:
                parts.append(type_map[at.lower()])

    if requirements.get("job_description_text"):
        # Use first 200 chars of JD to augment search
        jd = requirements["job_description_text"][:200]
        parts.append(jd)

    return " ".join(parts) if parts else "general assessment"


def _get_type_filter(requirements: dict) -> Optional[list[str]]:
    """Map assessment type requests to catalog type codes."""
    type_map = {
        "cognitive": ["A"],
        "ability": ["A"],
        "aptitude": ["A"],
        "personality": ["P"],
        "behaviour": ["P"],
        "behavioral": ["P"],
        "knowledge": ["K"],
        "skills": ["K"],
        "technical": ["K"],
        "situational_judgment": ["B"],
        "sjt": ["B"],
        "simulation": ["S"],
        "competency": ["C"],
        "development": ["D"],
    }

    requested = requirements.get("assessment_types_wanted", [])
    if not requested:
        return None

    codes = set()
    for t in requested:
        t_lower = t.lower().replace(" ", "_")
        if t_lower in type_map:
            codes.update(type_map[t_lower])

    return list(codes) if codes else None


def _format_assessments_for_prompt(assessments: list[tuple[Assessment, float]]) -> str:
    """Format search results for the LLM prompt."""
    lines = []
    for i, (a, score) in enumerate(assessments, 1):
        parts = [f"{i}. {a.name}"]
        if a.description:
            parts.append(f"   Description: {a.description}")
        if a.test_type:
            type_names = a._expand_type_codes()
            parts.append(f"   Type: {', '.join(type_names)} ({a.test_type})")
        if a.duration:
            parts.append(f"   Duration: {a.duration} minutes")
        parts.append(f"   Remote Testing: {'Yes' if a.remote_support else 'No'}")
        parts.append(f"   Adaptive/IRT: {'Yes' if a.adaptive_support else 'No'}")
        parts.append(f"   URL: {a.url}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _count_turns(messages: list[Message]) -> int:
    """Count total conversation turns (user + assistant messages)."""
    return len(messages)


def _has_prior_recommendations(messages: list[Message]) -> bool:
    """Check if the assistant has already made recommendations in prior turns."""
    for msg in messages:
        if msg.role == "assistant" and any(
            kw in msg.content.lower()
            for kw in ["recommend", "assessment", "here are", "suggest", "shortlist"]
        ):
            return True
    return False


async def process_chat(messages: list[Message]) -> ChatResponse:
    """Process a chat request and return the agent's response.

    This is the main entry point for the agent. It implements:
    1. Extract requirements from full conversation
    2. Classify intent
    3. Execute appropriate behavior
    """
    turn_count = _count_turns(messages)

    # Safety: if we're near the turn limit, force a recommendation
    force_recommend = turn_count >= MAX_TURNS - 2

    try:
        # Step 1: Extract requirements
        requirements = _extract_requirements(messages)
        intent = requirements.get("intent", "clarify")

        logger.info(f"Turn {turn_count}: intent={intent}, sufficient={requirements.get('is_sufficient')}")

        # Step 2: Route to appropriate handler
        if intent == "off_topic":
            return _handle_off_topic(messages)

        if intent == "compare":
            return _handle_comparison(messages, requirements)

        if intent in ("recommend", "refine") or force_recommend or requirements.get("is_sufficient"):
            return _handle_recommendation(messages, requirements)

        if intent == "clarify" and not force_recommend:
            return _handle_clarification(messages, requirements)

        # Default: try to recommend
        return _handle_recommendation(messages, requirements)

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        # Graceful degradation: try a simple search
        return _handle_fallback(messages)


def _handle_clarification(messages: list[Message], requirements: dict) -> ChatResponse:
    """Generate a clarifying question."""
    conversation = _format_conversation(messages)
    prompt = CLARIFICATION_PROMPT.format(
        conversation=conversation,
        requirements=json.dumps(requirements, indent=2),
    )
    reply = _call_llm(prompt)

    return ChatResponse(
        reply=reply,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_recommendation(messages: list[Message], requirements: dict) -> ChatResponse:
    """Search catalog and generate recommendations."""
    # Build search query
    query = _build_search_query(requirements)
    logger.info(f"Search query: {query}")

    # Get filters
    type_filter = _get_type_filter(requirements)
    max_duration = requirements.get("constraints", {}).get("max_duration_minutes")
    remote_required = requirements.get("constraints", {}).get("remote_required")

    # Search catalog
    results = catalog_search.search(
        query=query,
        top_k=MAX_RECOMMENDATIONS,
        type_filter=type_filter,
        max_duration=max_duration,
        remote_required=remote_required,
    )

    if not results:
        # Broaden search: remove filters
        results = catalog_search.search(query=query, top_k=MAX_RECOMMENDATIONS)

    if not results:
        return ChatResponse(
            reply="I couldn't find assessments matching your specific criteria. Could you provide more details about the role or skills you'd like to assess?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Generate natural language response
    conversation = _format_conversation(messages)
    assessments_text = _format_assessments_for_prompt(results)
    prompt = RECOMMENDATION_PROMPT.format(
        conversation=conversation,
        requirements=json.dumps(requirements, indent=2),
        assessments=assessments_text,
    )
    reply = _call_llm(prompt)

    # Build structured recommendations (programmatically from search results, NOT from LLM)
    recommendations = [
        Recommendation(
            name=assessment.name,
            url=assessment.url,
            test_type=assessment.test_type,
        )
        for assessment, _score in results[:MAX_RECOMMENDATIONS]
    ]

    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        end_of_conversation=False,
    )


def _handle_comparison(messages: list[Message], requirements: dict) -> ChatResponse:
    """Compare specific assessments from the catalog."""
    comparison_names = requirements.get("comparison_assessments", [])

    # Find the assessments in the catalog
    found_assessments = []
    for name in comparison_names:
        assessment = catalog_search.find_by_name(name)
        if assessment:
            found_assessments.append(assessment)

    if len(found_assessments) < 2:
        # Not enough assessments found for comparison
        return ChatResponse(
            reply="I couldn't find all the assessments you mentioned for comparison. Could you clarify the exact assessment names? You can describe them and I'll find the right ones.",
            recommendations=[],
            end_of_conversation=False,
        )

    # Format assessments for comparison
    assessments_text = _format_assessments_for_prompt(
        [(a, 1.0) for a in found_assessments]
    )

    # Get the comparison question
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.role == "user":
            last_user_msg = msg.content
            break

    prompt = COMPARISON_PROMPT.format(
        assessments=assessments_text,
        question=last_user_msg,
    )
    reply = _call_llm(prompt)

    # Include the compared assessments as recommendations
    recommendations = [
        Recommendation(
            name=a.name,
            url=a.url,
            test_type=a.test_type,
        )
        for a in found_assessments
    ]

    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        end_of_conversation=False,
    )


def _handle_off_topic(messages: list[Message]) -> ChatResponse:
    """Politely refuse off-topic requests."""
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.role == "user":
            last_user_msg = msg.content
            break

    prompt = REFUSAL_PROMPT.format(message=last_user_msg)
    reply = _call_llm(prompt)

    return ChatResponse(
        reply=reply,
        recommendations=[],
        end_of_conversation=False,
    )


def _handle_fallback(messages: list[Message]) -> ChatResponse:
    """Fallback handler when the main pipeline fails."""
    # Try a simple keyword search with the last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.role == "user":
            last_user_msg = msg.content
            break

    if last_user_msg:
        results = catalog_search.search(last_user_msg, top_k=5)
        if results:
            recommendations = [
                Recommendation(
                    name=a.name,
                    url=a.url,
                    test_type=a.test_type,
                )
                for a, _ in results
            ]
            return ChatResponse(
                reply="Based on your request, here are some relevant SHL assessments. Let me know if you'd like to refine these or need more specific recommendations.",
                recommendations=recommendations,
                end_of_conversation=False,
            )

    return ChatResponse(
        reply="I'd be happy to help you find the right SHL assessment. Could you tell me about the role you're hiring for and what skills or traits you'd like to evaluate?",
        recommendations=[],
        end_of_conversation=False,
    )
