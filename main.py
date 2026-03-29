import os
import sys
import time
import logging
import pandas as pd
from dotenv import load_dotenv

from scraper import scrape_reviews, get_demo_reviews
from preprocess import preprocess_all
from llm import analyze_chunked_review

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Amazon Echo Dot 5th Gen — product used for testing
# has tons of reviews and a good mix of sentiments
DEFAULT_URL = "https://www.amazon.com/dp/B09B8YWXDF"


def main():
    demo_mode = "--demo" in sys.argv
    url_args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if url_args:
        url = url_args[0]
    else:
        url = DEFAULT_URL
        if not demo_mode:
            print(f"No URL provided, using default: {url}")
            print("Tip: run with --demo flag to skip scraping and test with sample data\n")

    print(f"\nAI Review Scraper")
    print("=" * 60)
    print(f"Product: {url}")
    print("=" * 60)

    # --- Step 1: Scrape (or use demo data) ---
    if demo_mode:
        print("\n[DEMO MODE] Using sample reviews instead of live scraping")
        reviews = get_demo_reviews()
    else:
        print("\n[1/4] Scraping reviews from Amazon...")
        reviews = scrape_reviews(url, max_pages=3)

        if not reviews:
            print("\nCouldn't scrape live reviews (Amazon bot protection is active)")
            print("Falling back to demo reviews to show the full pipeline...\n")
            reviews = get_demo_reviews()

    print(f"Got {len(reviews)} reviews to analyze\n")

    # --- Step 2: Preprocess ---
    print("[2/4] Cleaning and preprocessing text...")
    processed = preprocess_all(reviews)
    print(f"{len(processed)} reviews ready\n")

    # --- Step 3: LLM Analysis ---
    print("[3/4] Running Groq LLM analysis (llama3-8b-8192)...\n")
    results = []

    for i, review in enumerate(processed, 1):
        author = review.get("author", "Unknown")
        print(f"  Analyzing [{i}/{len(processed)}]: '{review.get('title', 'No title')}' by {author}")

        analysis = analyze_chunked_review(review["chunks"])

        results.append({
            "author": author,
            "rating": review.get("rating", "N/A"),
            "date": review.get("date", "N/A"),
            "title": review.get("title", ""),
            "review_text": review.get("review_text", ""),
            "llm_summary": analysis.get("summary", ""),
            "sentiment": analysis.get("sentiment", "Unknown")
        })

        print(f"    → Sentiment: {analysis.get('sentiment')} | {analysis.get('summary', '')[:80]}...")
        time.sleep(0.8)  # small delay between Groq API calls

    print(f"\n✓ Analysis complete for all {len(results)} reviews")

    # --- Step 4: Save Output ---
    print("\n[4/4] Saving results to CSV...")
    os.makedirs("output", exist_ok=True)
    output_path = "output/reviews.csv"

    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved: {output_path}")

    # print a little summary table
    print("\n--- Sentiment Summary ---")
    counts = df["sentiment"].value_counts()
    total = len(df)
    for sentiment, count in counts.items():
        pct = round(count / total * 100)
        bar = "█" * count
        print(f"  {sentiment:<10} {bar} {count} ({pct}%)")

    avg_rating = df[df["rating"] != "N/A"]["rating"].astype(float).mean()
    print(f"\n  Avg Rating : {avg_rating:.1f} / 5.0")
    print(f"  Total      : {total} reviews analyzed")
    print("\nDone!")


if __name__ == "__main__":
    main()
