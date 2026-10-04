"""
roaster.py
Core AI engine for RoastMyResume.
Uses Ollama to run Llama 3.2 (or any swappable model) LOCALLY.
No API keys. No cloud. No data leaks. Free forever.

WHY OPEN-SOURCE WINS HERE:
- Closed APIs (OpenAI/Anthropic) would see every user's resume
- Resume = most sensitive career document a person has
- Ollama lets you swap models: llama3.2 → mistral → gemma → phi3 in one line
- Zero cost, zero rate limits, works on a flight with no WiFi
"""

from ollama import Client
import json
import math
import re
from typing import Generator

from prompts.prompts import (
    ROAST_PROMPT,
    SCORING_PROMPT,
    REWRITE_PROMPT,
    INTERVIEW_PREP_PROMPT,
)

# ─── Model Configuration ───────────────────────────────────────────────────────
# Open-source advantage: swap any model here without changing anything else
DEFAULT_MODEL = "llama3.2"
FALLBACK_MODELS = ["mistral", "llama3.1", "gemma2", "phi3", "llama3.2:1b"]

_client = Client(host="http://localhost:11434")

# Approximate RAM each model needs (GB) to run without freezing the system
MODEL_RAM_GB = {
    "llama3.2:1b": 2, "llama3.2:latest": 4, "llama3.2": 4,
    "mistral": 6, "llama3.1": 6,
    "gemma2:2b": 3, "gemma2": 10,
    "phi3": 4, "phi3:mini": 4,
    "qwen2.5": 6, "deepseek-r1:1.5b": 2,
}


def get_model_ram_warning(model: str) -> str | None:
    """
    Return a warning string if available RAM is tight for the chosen model.
    Returns None if everything looks fine.
    """
    try:
        import psutil
        available_gb = psutil.virtual_memory().available / (1024 ** 3)
        needed_gb = MODEL_RAM_GB.get(model.replace(":latest", ""), 4)
        if available_gb < needed_gb * 0.9:
            return (
                f"⚠️ **Low RAM warning:** `{model}` needs ~{needed_gb} GB but only "
                f"{available_gb:.1f} GB is free. Close other apps first, "
                f"or switch to `llama3.2` (needs ~4 GB)."
            )
    except ImportError:
        pass  # psutil not installed — skip check silently
    return None

# ───────────────────────────────────────────────────────────────────────────────


def get_installed_models() -> list[str]:
    """Return exact installed model names, including tags, or [] if unavailable."""
    try:
        response = _client.list()
        models = response.get("models", []) if isinstance(response, dict) else response.models
        names = []
        for model in models:
            name = (
                model.get("model") or model.get("name")
                if isinstance(model, dict)
                else model.model
            )
            if isinstance(name, str) and name:
                names.append(name)
        return names
    except Exception:
        return []


def get_available_model() -> str:
    """
    Auto-detect which Ollama model is available.
    Open-source flexibility: works with whatever the user has pulled.
    """
    try:
        models_response = _client.list()
        available = [m.model.split(":")[0] for m in models_response.models]

        if DEFAULT_MODEL in available:
            return DEFAULT_MODEL

        for fallback in FALLBACK_MODELS:
            if fallback in available:
                return fallback

        if available:
            return models_response.models[0].model

        return DEFAULT_MODEL
    except Exception:
        return DEFAULT_MODEL


def check_ollama_running() -> tuple[bool, str]:
    """Check if Ollama is running and accessible."""
    try:
        models_response = _client.list()
        models = [m.model for m in models_response.models]
        if not models:
            return False, "Ollama is running but no models are pulled. Run: ollama pull llama3.2"
        return True, f"✅ Ollama running with models: {', '.join(models[:3])}"
    except Exception as e:
        return False, f"Ollama not running. Start it with: ollama serve\n\nError: {str(e)}"


def stream_roast(
    resume_text: str,
    jd_text: str,
    model: str = None,
    persona_system: str = "",
    temperature: float = 0.85,
) -> Generator:
    """
    Stream the brutal resume roast from local Ollama.
    persona_system injects the chosen persona as a system message —
    completely changing the AI's tone, focus, and style.
    This is ONLY possible with open-source models (closed APIs don't expose system prompts).
    """
    if not model:
        model = get_available_model()

    prompt = ROAST_PROMPT.format(
        resume_text=resume_text[:4000],
        jd_text=jd_text[:2000],
    )

    # Build messages — system persona first, then user prompt
    messages = []
    if persona_system:
        messages.append({"role": "system", "content": persona_system})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = _client.chat(
            model=model,
            messages=messages,
            stream=True,
            options={
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 2048,
            },
        )
        for chunk in stream:
            yield chunk["message"]["content"] if isinstance(chunk, dict) else chunk.message.content
    except Exception as e:
        yield (
            f"\n\n⚠️ Ollama error: {str(e)}\n"
            f"Make sure Ollama is running (`ollama serve`) "
            f"and model is pulled (`ollama pull {model}`)"
        )


def stream_chat_response(
    chat_history: list,
    resume_text: str,
    jd_text: str,
    model: str,
    persona_system: str,
    temperature: float = 0.7,
) -> Generator:
    """Stream interactive chat responses with the resume/JD context injected."""
    system_prompt = f"""You are having a direct, 1-on-1 follow-up conversation with the candidate about their resume and target role.

PERSONA TONE & IDENTITY:
{persona_system}

BEHAVIOR RULES (STRICT):
1. CONVERSATIONAL & NATURAL: Answer ONLY what the user asks. If the user sends a greeting (like "hi", "hello", "hey"), reply in 1-2 punchy sentences in character (e.g. asking what specific section or skill they want to discuss).
2. NEVER DUMP AN UNSOLICITED FULL REVIEW: Do NOT produce an unprompted multi-point essay, full resume breakdown, or formal letter. Keep replies concise, conversational, and direct.
3. CONTEXT-AWARE: When the user asks about specific technologies, skills, or career decisions (e.g. "Should I learn Next.js or stick to Node.js?"), give sharp, practical advice specifically comparing what is on their resume versus what this target job requires.
4. TONE: Stay 100% in character for your persona. Do not use generic corporate AI politeness.

CANDIDATE'S RESUME:
{resume_text[:3000]}

TARGET JOB DESCRIPTION:
{jd_text[:1500]}
"""
    messages = [{"role": "system", "content": system_prompt}]
    
    # Append the chat history (excluding the very first default system greeting from the UI)
    for msg in chat_history:
        # Don't send our own default placeholder greeting to the LLM
        if msg["content"].startswith("I'm ready. What do you want to ask"):
            continue
        messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        stream = _client.chat(
            model=model,
            messages=messages,
            stream=True,
            options={
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 1024,
            },
        )
        for chunk in stream:
            yield chunk["message"]["content"] if isinstance(chunk, dict) else chunk.message.content
    except Exception as e:
        yield f"\n\n⚠️ Chat error: {str(e)}"


def get_rejection_scores(resume_text: str, jd_text: str, model: str = None) -> dict:
    """
    Get structured JSON scores for each resume section.
    Returns a dict with rejection risk scores per section.
    """
    if not model:
        model = get_available_model()

    prompt = SCORING_PROMPT.format(
        resume_text=resume_text[:3000],
        jd_text=jd_text[:1500],
    )

    try:
        response = _client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.1,
                "num_predict": 1024,
            },
        )
        raw = response["message"]["content"] if isinstance(response, dict) else response.message.content

        # Unwrap fences without accidentally accepting an object inside a JSON array.
        raw = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        if fenced:
            raw = fenced.group(1)
        return _validate_scores(json.loads(raw))

    except Exception:
        return _default_scores()


def rewrite_section(
    section_name: str,
    section_text: str,
    jd_text: str,
    model: str = None,
) -> str:
    """Rewrite a specific resume section to be stronger and JD-matched."""
    if not model:
        model = get_available_model()

    if not section_text or len(section_text.strip()) < 10:
        return "⚠️ This section appears empty. Add content and try again."

    prompt = REWRITE_PROMPT.format(
        section_name=section_name,
        section_text=section_text[:2000],
        jd_text=jd_text[:1000],
    )

    try:
        response = _client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7, "num_predict": 1024},
        )
        return response.message.content
    except Exception as e:
        return f"⚠️ Rewrite failed: {str(e)}"


def generate_interview_prep(resume_text: str, role_title: str, model: str = None) -> str:
    """Generate likely interview questions based on resume gaps."""
    if not model:
        model = get_available_model()

    resume_summary = resume_text[:1000]

    prompt = INTERVIEW_PREP_PROMPT.format(
        resume_summary=resume_summary,
        role_title=role_title,
    )

    try:
        response = _client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.75, "num_predict": 1500},
        )
        return response.message.content
    except Exception as e:
        return f"⚠️ Interview prep failed: {str(e)}"


def _validated_number(value, maximum=100):
    """Parse a finite number, rejecting booleans, and clamp to its valid range."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Expected a numeric score")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Expected a finite score")
    number = max(0.0, number)
    if maximum is not None:
        number = min(maximum, number)
    return int(number) if number == int(number) else number


def _validate_scores(scores) -> dict:
    """Validate the score card before it reaches numeric charts and UI controls."""
    if not isinstance(scores, dict) or not scores:
        raise ValueError("Expected a score object")
    sections = scores.get("sections")
    if not isinstance(sections, dict) or not sections:
        raise ValueError("Expected nonempty sections")

    for field in ("overall_rejection_risk", "jd_keyword_match_percent"):
        scores[field] = _validated_number(scores[field])
    scores["attention_seconds"] = _validated_number(scores["attention_seconds"], maximum=None)

    for section in sections.values():
        if not isinstance(section, dict):
            raise ValueError("Expected a section object")
        section["score"] = _validated_number(section["score"])
        for field in ("risk", "one_liner"):
            if field in section and not isinstance(section[field], str):
                raise ValueError("Expected section feedback text")

    for field in ("missing_keywords", "strong_keywords_found"):
        keywords = scores.get(field, [])
        if not isinstance(keywords, list) or not all(isinstance(word, str) for word in keywords):
            raise ValueError("Expected a keyword list of strings")
        scores[field] = keywords
    for field in ("ats_compatibility", "resume_type_verdict"):
        if field in scores and not isinstance(scores[field], str):
            raise ValueError("Expected verdict text")
    return scores


def _default_scores() -> dict:
    """Return an explicit unavailable state, never fabricated numeric scores."""
    return {
        "analysis_error": True,
        "sections": {},
        "missing_keywords": [],
        "strong_keywords_found": [],
    }

def summarize_roast_for_audio(roast_text: str, model: str) -> str:
    """Summarize the full roast into a short script (under 1 minute to speak)."""
    if not model:
        model = get_available_model()

    prompt = f"""Summarize the following resume review into a punchy, spoken-word script. 
Keep it under 150 words (about 45 seconds of speech). 
Be direct, maintain the original persona's tone, and hit the main highlights of what is good and what needs fixing. Do not use markdown like asterisks or hashtags.

REVIEW TO SUMMARIZE:
{roast_text[:4000]}
"""
    try:
        response = _client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7, "num_predict": 256},
        )
        return response["message"]["content"] if isinstance(response, dict) else response.message.content
    except Exception as e:
        return roast_text[:800]  # Fallback to first ~800 chars
