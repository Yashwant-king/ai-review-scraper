# AI Review Scraper

A Python tool that scrapes product reviews from major e-commerce platforms and uses AI (via Groq, OpenRouter, OpenAI, or Gemini) to generate a summary and sentiment for each review. Results are displayed in a Streamlit dashboard and can be exported to CSV.

## Chosen Product URL

```
https://www.amazon.com/dp/B09B8YWXDF
```
(Amazon Echo Dot 5th Gen — chosen because it has hundreds of reviews and good variety of sentiments)

## How It Works

```
Product URL → scraper.py (BeautifulSoup) → preprocess.py (clean + chunk) → llm.py (LLM API) → Streamlit UI / output/reviews.csv
```

1. **Scraping**: Fetches review pages with realistic browser headers and random delays to avoid bot detection. Handles pagination (up to 5 pages via UI, 3 pages via CLI).
2. **Preprocessing**: Cleans HTML entities, fixes encoding issues, removes noise, and chunks long reviews so they fit within the LLM's context window.
3. **LLM Analysis**: Sends each cleaned review to your chosen LLM provider and asks it to return a short summary + sentiment label (Positive / Negative / Mixed / Neutral).
4. **Output**: Displays live results in the Streamlit dashboard and saves everything to `output/reviews.csv`.

## Supported Platforms

| Platform | URL Format |
|----------|------------|
| 🛒 Amazon | `amazon.com/dp/...` |
| 🛍️ Flipkart | `flipkart.com/...` |
| ⭐ Trustpilot | `trustpilot.com/review/...` |
| 🏷️ eBay | `ebay.com/itm/...` |
| 🖥️ Best Buy | `bestbuy.com/site/...` |
| 💼 G2 | `g2.com/products/.../reviews` |

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
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```
You only need the key(s) for the provider(s) you want to use.

| Provider | Free Tier | Get Key |
|----------|-----------|---------|
| Groq | ✅ Yes | https://console.groq.com |
| OpenRouter | ✅ Yes (free credits) | https://openrouter.ai/keys |
| Gemini | ✅ Yes | https://aistudio.google.com/app/apikey |
| OpenAI | ❌ Paid | https://platform.openai.com/api-keys |

### 4. Run the Streamlit UI (recommended)
```bash
streamlit run streamlit_app.py
```
Then open `http://localhost:8501`, paste a product URL, choose your LLM provider, and click **Analyze**.

### 5. Or run the CLI
```bash
# use the default product URL
python main.py

# or pass your own Amazon product URL
python main.py https://www.amazon.com/dp/YOUR_ASIN
```

## LLM Providers

| Provider | Default Model | Notes |
|----------|--------------|-------|
| **OpenRouter** ⭐ | `openai/gpt-4o-mini` | Access to 100+ models via one key — recommended |
| **Groq** | `llama-3.3-70b-versatile` | Fastest inference, generous free tier |
| **OpenAI** | `gpt-4o-mini` | Reliable, paid |
| **Gemini** | `gemini-1.5-flash` | Free tier available |

You can also override the model name directly in the sidebar (e.g. `meta-llama/llama-3.1-8b-instruct` for OpenRouter).

## Output

The app saves results to `output/reviews.csv` with these columns:

| Column | Description |
|--------|-------------|
| author | Reviewer's name |
| rating | Star rating (e.g. 4.0) |
| date | Review date |
| title | Review title |
| review_text | Original review text |
| llm_summary | 1-2 sentence summary from the LLM |
| sentiment | Positive / Negative / Mixed / Neutral |
| provider | Which LLM provider was used |

## Design Choices

- **Multi-provider LLM support**: OpenRouter, Groq, OpenAI, and Gemini are all supported via a unified interface. Easy to extend with new providers.
- **Groq + LLaMA 3.3 70B**: Fast inference, free tier available, and OpenAI-compatible API
- **BeautifulSoup over Scrapy**: Simpler for a single-site scraper, doesn't need the full Scrapy overhead
- **Chunk-first strategy**: For very long reviews, only the first chunk is analyzed. This keeps API usage low while still capturing the main points (first paragraph usually has the gist)
- **Exponential backoff**: Both the scraper and LLM caller retry with increasing wait times on failure
- **`utf-8-sig` encoding for CSV**: Ensures the file opens correctly in Excel without encoding issues

## Limitations

- **Amazon bot detection**: Amazon actively blocks scrapers. If you get 0 reviews, try again after a few minutes or use a VPN. This is a known limitation of scraping Amazon without an official API.
- **Trustpilot works best**: It serves reviews as static HTML and is the most reliable platform for this tool.
- **Rate limits**: LLM providers have rate limits on free tiers. The script adds delays between API calls, but if you're analyzing 30+ reviews it might hit the limit. It will wait and retry automatically.
- **First-chunk only for long reviews**: Very long reviews (>3000 chars) are truncated to the first chunk for LLM analysis. Full multi-chunk analysis would multiply API costs.
- **Only supported platforms**: The scraper targets specific HTML structures per site. Unsupported sites will return an error.

## Project Structure

```
ai-review-scraper/
├── streamlit_app.py  # Streamlit web UI — main interface
├── main.py           # CLI entry point
├── scraper.py        # web scraping logic (requests + BeautifulSoup)
├── preprocess.py     # text cleaning and chunking
├── llm.py            # multi-provider LLM calls and response parsing
├── output/
│   └── reviews.csv   # generated after running
├── .env              # your API key(s) — not committed
├── .env.example      # template for .env
├── requirements.txt
└── README.md
```
