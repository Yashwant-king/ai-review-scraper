import re
import html as html_lib
import logging

logger = logging.getLogger(__name__)

# keeping chunks under ~800 tokens (roughly 3200 chars)
# groq's llama3-8b can handle more but shorter = faster + cheaper
MAX_CHUNK_CHARS = 3000


def clean_text(text):
    if not text:
        return ""

    # decode html entities (&amp; -> &, etc.)
    text = html_lib.unescape(text)

    # strip any html tags that somehow snuck in
    text = re.sub(r'<[^>]+>', '', text)

    # handle encoding weirdness
    text = text.encode('utf-8', errors='ignore').decode('utf-8')

    # collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    if len(text) <= max_chars:
        return [text]

    # try to split at sentence endings so chunks make sense
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = current + " " + sentence if current else sentence
        else:
            if current:
                chunks.append(current.strip())
            # handle case where a single sentence is longer than max_chars
            if len(sentence) > max_chars:
                chunks.append(sentence[:max_chars])
            else:
                current = sentence

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_chars]]


def preprocess_review(review):
    cleaned = review.copy()
    cleaned["review_text"] = clean_text(review.get("review_text", ""))
    cleaned["title"] = clean_text(review.get("title", ""))

    chunks = chunk_text(cleaned["review_text"])
    cleaned["chunks"] = chunks
    cleaned["is_chunked"] = len(chunks) > 1

    if cleaned["is_chunked"]:
        logger.debug(f"Long review by '{review.get('author')}' split into {len(chunks)} chunks")

    return cleaned


def preprocess_all(reviews):
    processed = []
    skipped = 0

    for r in reviews:
        p = preprocess_review(r)

        # skip reviews that are basically empty after cleaning
        if len(p["review_text"]) < 15:
            skipped += 1
            continue

        processed.append(p)

    if skipped:
        logger.info(f"Skipped {skipped} reviews (too short after cleaning)")

    return processed
