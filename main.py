import os
import sys
import time
import logging
import pandas as pd
from dotenv import load_dotenv

from scraper import scrape_reviews
from preprocess import preprocess_all
from llm import analyze_chunked_review

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# product I used for testing — feel free to change via CLI arg
DEFAULT_URL = "https://www.amazon.com/dp/B09B8YWXDF"


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = DEFAULT_URL
        print(f"No URL provided, using default: {url}")
        print("(You can pass a URL as argument: python main.py <url>)\n")

    print(f"Starting review scraper for:\n{url}\n")
    print("-" * 60)

    # --- Step 1: Scrape ---
    print("\n[1/4] Scraping reviews...")
    reviews = scrape_reviews(url, max_pages=3)

    if not reviews:
        print("\nNo reviews scraped. A few things to try:")
        print("  - Amazon sometimes blocks bots, try waiting 5 mins and retry")
        print("  - Make sure the URL is a product page, not a search page")
        print("  - Try a different product URL")
        sys.exit(1)

    print(f"Got {len(reviews)} reviews\n")

    # --- Step 2: Preprocess ---
    print("[2/4] Cleaning review text...")
    processed = preprocess_all(reviews)
    print(f"{len(processed)} reviews ready for LLM analysis\n")

    # --- Step 3: LLM Analysis ---
    print("[3/4] Running sentiment analysis via Groq...\n")
    results = []

    for i, review in enumerate(processed, 1):
        print(f"  [{i}/{len(processed)}] Analyzing review by {review.get('author', 'Unknown')}...")

        analysis = analyze_chunked_review(review["chunks"])

        results.append({
            "author": review.get("author", "Unknown"),
            "rating": review.get("rating", "N/A"),
            "date": review.get("date", "N/A"),
            "title": review.get("title", ""),
            "review_text": review.get("review_text", ""),
            "llm_summary": analysis.get("summary", ""),
            "sentiment": analysis.get("sentiment", "Unknown")
        })

        # small delay between calls to be safe with rate limits
        time.sleep(1)

    print(f"\nDone! Analyzed {len(results)} reviews")

    # --- Step 4: Save Output ---
    print("\n[4/4] Saving results...")
    os.makedirs("output", exist_ok=True)
    output_path = "output/reviews.csv"

    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved to: {output_path}")

    # quick summary
    print("\n--- Sentiment Breakdown ---")
    for sentiment, count in df["sentiment"].value_counts().items():
        bar = "█" * count
        print(f"  {sentiment:<10} {bar} ({count})")

    print("\nAll done!")


if __name__ == "__main__":
    main()
