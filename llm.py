import time
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# Default model per provider
MODELS = {
    "Groq":       "llama-3.3-70b-versatile",   # upgraded from 8b
    "OpenAI":     "gpt-4o-mini",
    "OpenRouter": "openai/gpt-4o-mini",         # OpenAI-compatible via openrouter.ai
    "Gemini":     "gemini-1.5-flash",
}

PROMPT = """You are analyzing a customer product review.

Given the review below, provide:
1. A 1-2 sentence summary of the main points
2. The overall sentiment: Positive / Negative / Mixed / Neutral

Review:
{review_text}

Reply in exactly this format:
Summary: <your summary>
Sentiment: <Positive/Negative/Mixed/Neutral>"""


def analyze_review(review_text, provider="OpenRouter", api_key=None, model=None, retries=3):
    prompt = PROMPT.format(review_text=review_text)
    used_model = model or MODELS.get(provider, MODELS["OpenRouter"])

    for attempt in range(retries):
        try:
            raw = _call_llm(prompt, provider, api_key, used_model)
            return _parse_response(raw)

        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower() or "quota" in err.lower():
                wait = 60 * (attempt + 1)
                logger.warning(f"Rate limited by {provider}. Waiting {wait}s...")
                time.sleep(wait)
            elif "401" in err or "invalid" in err.lower() or "api_key" in err.lower():
                logger.error(f"Invalid API key for {provider}")
                return {"summary": f"❌ Invalid {provider} API key — check your key in the sidebar.", "sentiment": "Error"}
            else:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(3)
                else:
                    return {"summary": f"LLM error: {str(e)[:120]}", "sentiment": "Error"}

    return {"summary": "Could not generate summary after retries.", "sentiment": "Unknown"}


def _call_llm(prompt, provider, api_key, model):
    """Route to the correct LLM provider."""

    if provider == "Groq":
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    elif provider in ("OpenAI", "OpenRouter"):
        from openai import OpenAI
        # OpenRouter uses OpenAI-compatible API at a different base URL
        base_url = "https://openrouter.ai/api/v1" if provider == "OpenRouter" else None
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    elif provider == "Gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(prompt)
        return response.text.strip()

    else:
        raise ValueError(f"Unknown provider: {provider}")


def _parse_response(text):
    summary   = ""
    sentiment = "Unknown"

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Summary:"):
            summary = line[len("Summary:"):].strip()
        elif line.startswith("Sentiment:"):
            sentiment = line[len("Sentiment:"):].strip()

    # Normalise sentiment to known values
    sentiment_lower = sentiment.lower()
    if   "positive" in sentiment_lower: sentiment = "Positive"
    elif "negative" in sentiment_lower: sentiment = "Negative"
    elif "mixed"    in sentiment_lower: sentiment = "Mixed"
    elif "neutral"  in sentiment_lower: sentiment = "Neutral"

    if not summary:
        summary = text[:250]

    return {"summary": summary, "sentiment": sentiment}


def analyze_chunked_review(chunks, provider="OpenRouter", api_key=None, model=None):
    """Analyze the first (most informative) chunk of a review."""
    return analyze_review(chunks[0], provider=provider, api_key=api_key, model=model)
