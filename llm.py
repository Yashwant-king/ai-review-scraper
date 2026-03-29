import os
import time
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# using llama3-8b — fast and handles this kind of task well
MODEL = "llama3-8b-8192"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PROMPT = """You are a helpful assistant that analyzes product reviews.

Given the customer review below, do two things:
1. Write a 1-2 sentence summary of what the customer is saying
2. Classify the overall sentiment as one of: Positive, Negative, Mixed, Neutral

Review:
{review_text}

Reply in exactly this format (no extra text):
Summary: <your summary>
Sentiment: <Positive/Negative/Mixed/Neutral>"""


def analyze_review(review_text, retries=3):
    prompt = PROMPT.format(review_text=review_text)

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # low temp = more consistent outputs
                max_tokens=180
            )
            raw = response.choices[0].message.content.strip()
            return _parse_response(raw)

        except Exception as e:
            err = str(e)

            if "429" in err or "rate_limit" in err.lower():
                # groq free tier has rate limits, just wait it out
                wait = 60 * (attempt + 1)
                logger.warning(f"Rate limited by Groq. Waiting {wait}s...")
                time.sleep(wait)

            elif "401" in err or "invalid_api_key" in err.lower():
                logger.error("API key is invalid. Please check GROQ_API_KEY in your .env file")
                raise

            else:
                logger.warning(f"Attempt {attempt+1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    logger.error("Giving up on this review after all retries")
                    return {"summary": "Could not generate summary", "sentiment": "Unknown"}

    return {"summary": "Could not generate summary", "sentiment": "Unknown"}


def _parse_response(text):
    summary = ""
    sentiment = "Unknown"

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Summary:"):
            summary = line[len("Summary:"):].strip()
        elif line.startswith("Sentiment:"):
            sentiment = line[len("Sentiment:"):].strip()

    # if parsing failed for some reason, use the raw text as summary
    if not summary:
        summary = text[:250]

    return {"summary": summary, "sentiment": sentiment}


def analyze_chunked_review(chunks):
    if len(chunks) == 1:
        return analyze_review(chunks[0])

    # for multi-chunk reviews, just use the first chunk
    # first chunk usually has the most important points anyway
    # doing all chunks would cost a lot of API calls
    logger.debug(f"Multi-chunk review ({len(chunks)} chunks), analyzing first chunk only")
    return analyze_review(chunks[0])
