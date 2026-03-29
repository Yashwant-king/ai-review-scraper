# AI Review Scraper

A Python tool that scrapes product reviews from Amazon and uses the Groq LLM API (LLaMA 3) to generate a summary and sentiment for each review. Results are saved to a CSV file.

## Chosen Product URL

```
https://www.amazon.com/dp/B09B8YWXDF
```
(Amazon Echo Dot 5th Gen — chosen because it has hundreds of reviews and good variety of sentiments)

## How It Works

```
Product URL → scraper.py (BeautifulSoup) → preprocess.py (clean + chunk) → llm.py (Groq API) → output/reviews.csv
```

1. **Scraping**: Fetches review pages with realistic browser headers and random delays to avoid bot detection. Handles pagination (up to 3 pages by default).
2. **Preprocessing**: Cleans HTML entities, fixes encoding issues, removes noise, and chunks long reviews so they fit within the LLM's context window.
3. **LLM Analysis**: Sends each cleaned review to Groq's LLaMA 3 8B model and asks it to return a short summary + sentiment label (Positive / Negative / Mixed / Neutral).
4. **Output**: Saves everything to `output/reviews.csv`.

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/Yashwant-king/ai-review-scraper.git
cd ai-review-scraper
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at https://console.groq.com

### 4. Run it
```bash
# use the default product URL
python main.py

# or pass your own Amazon product URL
python main.py https://www.amazon.com/dp/YOUR_ASIN
```

## Output

The script saves results to `output/reviews.csv` with these columns:

| Column | Description |
|--------|-------------|
| author | Reviewer's name |
| rating | Star rating (e.g. 4.0) |
| date | Review date |
| title | Review title |
| review_text | Original review text |
| llm_summary | 1-2 sentence summary from LLaMA 3 |
| sentiment | Positive / Negative / Mixed / Neutral |

## Design Choices

- **Groq + LLaMA 3 8B**: Fast inference, free tier available, and OpenAI-compatible API — easy to swap out if needed
- **BeautifulSoup over Scrapy**: Simpler for a single-site scraper, doesn't need the full Scrapy overhead
- **Chunk-first strategy**: For very long reviews, only the first chunk is analyzed. This keeps API usage low while still capturing the main points (first paragraph usually has the gist)
- **Exponential backoff**: Both the scraper and LLM caller retry with increasing wait times on failure
- **`utf-8-sig` encoding for CSV**: Ensures the file opens correctly in Excel without encoding issues

## Limitations

- **Amazon bot detection**: Amazon actively blocks scrapers. If you get 0 reviews, try again after a few minutes or use a VPN. This is a known limitation of scraping Amazon without an official API.
- **Rate limits**: Groq's free tier has rate limits. The script adds delays between API calls, but if you're analyzing 30+ reviews it might hit the limit. It will wait and retry automatically.
- **First-chunk only for long reviews**: Very long reviews (>3000 chars) are truncated to the first chunk for LLM analysis. Full multi-chunk analysis would multiply API costs.
- **Only Amazon for now**: The scraper targets Amazon's HTML structure specifically. Different sites would need their own parsing logic.

## Project Structure

```
ai-review-scraper/
├── scraper.py       # web scraping logic (requests + BeautifulSoup)
├── preprocess.py    # text cleaning and chunking
├── llm.py           # Groq API calls and response parsing
├── main.py          # entry point, ties everything together
├── output/
│   └── reviews.csv  # generated after running
├── .env             # your API key (not committed)
├── requirements.txt
└── README.md
```
