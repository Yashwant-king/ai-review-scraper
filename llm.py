import os
import time
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# models for each provider
MODELS = {
    "Groq": "llama-3.1-8b-instant",
    "OpenAI": "gpt-3.5-turbo",
    "Gemini": "gemini-1.5-flash"
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


def analyze_review(review_text, provider="Groq", api_key=None, retries=3):
    prompt = PROMPT.format(review_text=review_text)

    for attempt in range(retries):
        try:
            raw = _call_llm(prompt, provider, api_key)
            return _parse_response(raw)

        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower() or "quota" in err.lower():
                wait = 60 * (attempt + 1)
                logger.warning(f"Rate limited by {provider}. Waiting {wait}s...")
                time.sleep(wait)
            elif "401" in err or "invalid" in err.lower() or "api_key" in err.lower():
                logger.error(f"Invalid API key for {provider}")
                return {"summary": f"❌ Invalid {provider} API key", "sentiment": "Error"}
            else:
                logger.warning(f"Attempt {attempt+1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(3)
                else:
                    return {"summary": f"Error: {str(e)[:100]}", "sentiment": "Error"}

    return {"summary": "Could not generate summary", "sentiment": "Unknown"}


def _call_llm(prompt, provider, api_key):
    """Route to the correct LLM provider."""

    if provider == "Groq":
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=MODELS["Groq"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()

    elif provider == "OpenAI":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=MODELS["OpenAI"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()

    elif provider == "Gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODELS["Gemini"])
        response = model.generate_content(prompt)
        return response.text.strip()

    else:
        raise ValueError(f"Unknown provider: {provider}")


def _parse_response(text):
    summary = ""
    sentiment = "Unknown"

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Summary:"):
            summary = line[len("Summary:"):].strip()
        elif line.startswith("Sentiment:"):
            sentiment = line[len("Sentiment:"):].strip()

    if not summary:
        summary = text[:250]

    return {"summary": summary, "sentiment": sentiment}


def analyze_chunked_review(chunks, provider="Groq", api_key=None):
    # for long reviews just use first chunk — has the main points
    return analyze_review(chunks[0], provider=provider, api_key=api_key)
