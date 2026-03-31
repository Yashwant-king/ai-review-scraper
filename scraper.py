import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import re
import json
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supported platforms
SUPPORTED_PLATFORMS = ["Amazon", "Flipkart", "Trustpilot", "eBay", "Best Buy", "G2"]

# Rotate User-Agents to reduce bot detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

PLATFORM_REFERERS = {
    "Amazon":    "https://www.amazon.com/",
    "Flipkart":  "https://www.flipkart.com/",
    "Trustpilot":"https://www.trustpilot.com/",
    "Best Buy":  "https://www.bestbuy.com/",
    "eBay":      "https://www.ebay.com/",
    "G2":        "https://www.g2.com/",
}

PLATFORM_ICONS = {
    "Amazon":    "🛒",
    "Flipkart":  "🛍️",
    "Trustpilot":"⭐",
    "eBay":      "🏷️",
    "Best Buy":  "🖥️",
    "G2":        "💼",
    "Unknown":   "❓",
}


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _get_headers(platform=""):
    """Return headers with a randomly chosen User-Agent and platform-aware Referer."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": PLATFORM_REFERERS.get(platform, "https://www.google.com/"),
    }


def _is_blocked(html, platform=""):
    """Detect a CAPTCHA or bot-challenge page — only use highly specific phrases."""
    if not html or len(html) < 300:
        return True
    # These strings only appear on challenge/block pages, not normal content
    indicators = [
        "Enter the characters you see below",
        "Type the characters you see in this image",
        "Sorry, we just need to make sure you're not a robot",
        "To discuss automated access to Amazon data",
        "<title>Robot Check</title>",
        "api-services-support@amazon.com",
        "Pardon Our Interruption",           # Cloudflare / Akamai
        "cf-browser-verification",           # Cloudflare
        "Just a moment...",                  # Cloudflare challenge page title
        "Enable JavaScript and cookies to continue",   # Cloudflare JS challenge
        "Please enable cookies.",            # Cloudflare cookie challenge
        "/_Incapsula_Resource",              # Imperva / Incapsula
        "px.gif",                            # PerimeterX bot protection
    ]
    # Case-sensitive — these exact strings only appear in challenge pages
    return any(ind in html for ind in indicators)


def detect_platform(url):
    """Auto-detect the e-commerce / review platform from the URL."""
    url_lower = url.lower()
    if "amazon."     in url_lower: return "Amazon"
    if "flipkart.com" in url_lower: return "Flipkart"
    if "trustpilot.com" in url_lower: return "Trustpilot"
    if "bestbuy.com"  in url_lower: return "Best Buy"
    if "ebay.com"     in url_lower: return "eBay"
    if "g2.com"       in url_lower: return "G2"
    return "Unknown"


def _build_reviews_url(url, platform):
    """Convert a product page URL to the dedicated reviews URL where needed."""
    if platform == "Amazon":
        if "/dp/" in url:
            asin = url.split("/dp/")[1].split("/")[0].split("?")[0]
            return (f"https://www.amazon.com/product-reviews/{asin}"
                    f"?reviewerType=all_reviews&sortBy=recent&pageNumber=1")
        return url

    if platform == "G2":
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path.endswith("/reviews"):
            path += "/reviews"
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    # Trustpilot, Flipkart, eBay, Best Buy — use URL as-is
    return url


def _make_session(platform):
    """
    Build a requests.Session and prefetch the homepage to get cookies.
    This makes subsequent requests look more like a real browser session.
    """
    sess = requests.Session()
    home = PLATFORM_REFERERS.get(platform, "https://www.google.com/")
    try:
        sess.get(home, headers=_get_headers(platform), timeout=8, allow_redirects=True)
        time.sleep(random.uniform(0.8, 2.0))
        logger.info(f"[{platform}] Session established (cookies: {len(sess.cookies)})")
    except Exception as e:
        logger.debug(f"[{platform}] Preflight failed (continuing anyway): {e}")
    return sess


def get_page(url, platform="", session=None, retries=3):
    """Fetch a URL with retries, a shared session, and bot-check detection."""
    requester = session or requests  # use session if provided, else plain requests
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.5, 4.0))
            resp = requester.get(url, headers=_get_headers(platform), timeout=15)
            resp.raise_for_status()
            html = resp.text
            logger.info(f"[{platform}] Got {len(html):,} bytes (status {resp.status_code})")
            if _is_blocked(html, platform):
                logger.warning(f"[{platform}] Bot-challenge page detected on attempt {attempt + 1}")
                time.sleep(7 + attempt * 5)
                continue
            return html

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (429, 503):
                logger.warning(f"[{platform}] HTTP {code} — rate limited, waiting…")
                time.sleep(10 + attempt * 6)
            elif code == 404:
                logger.error(f"[{platform}] 404 — page not found.")
                raise
            else:
                logger.warning(f"[{platform}] HTTP {code} on attempt {attempt + 1}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"[{platform}] Request error on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise

    return None

# ─────────────────────────────────────────────
#  JSON-LD STRUCTURED DATA PARSER (universal)
# ─────────────────────────────────────────────

def _parse_json_ld_reviews(html):
    """
    Extract reviews from JSON-LD <script type="application/ld+json"> blocks.
    Works for any site that embeds schema.org Review markup (Trustpilot, G2, etc.).
    """
    soup = BeautifulSoup(html, "html.parser")
    reviews = []
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                reviews.extend(_extract_ld_reviews(item))
        except (json.JSONDecodeError, AttributeError):
            continue
    return reviews


def _extract_ld_reviews(data):
    """Recursively extract review dicts from a JSON-LD object tree."""
    reviews = []
    if not isinstance(data, dict):
        return reviews

    schema_type = data.get("@type", "")

    # Direct schema type: Review
    if schema_type == "Review":
        r = _parse_single_ld_review(data)
        if r:
            reviews.append(r)

    # Container types that hold a 'review' list
    elif schema_type in ("Product", "LocalBusiness", "Organization",
                         "SoftwareApplication", "WebPage"):
        raw = data.get("review", [])
        if isinstance(raw, dict):
            raw = [raw]
        for r in raw:
            parsed = _parse_single_ld_review(r)
            if parsed:
                reviews.append(parsed)

    # Recurse into @graph
    for item in data.get("@graph", []):
        reviews.extend(_extract_ld_reviews(item))

    return reviews


def _parse_single_ld_review(r):
    """Convert a single JSON-LD Review dict into our standard review format."""
    if not isinstance(r, dict):
        return None
    body = r.get("reviewBody") or r.get("description") or ""
    if not body or len(str(body).strip()) < 10:
        return None

    author = r.get("author", {})
    if isinstance(author, dict):
        author = author.get("name", "Unknown")

    rating_info = r.get("reviewRating", {})
    rating = "N/A"
    if isinstance(rating_info, dict):
        rating = str(rating_info.get("ratingValue", "N/A"))

    date = r.get("datePublished") or r.get("dateCreated") or "N/A"

    return {
        "author":      str(author).strip() if author else "Unknown",
        "rating":      rating,
        "date":        str(date)[:10] if date else "N/A",
        "title":       str(r.get("name") or r.get("headline") or "").strip(),
        "review_text": str(body).strip(),
    }



# ─────────────────────────────────────────────
#  PLATFORM PARSERS
# ─────────────────────────────────────────────

def parse_amazon_reviews(html):
    # Amazon product-reviews pages embed JSON-LD on some regions — try it first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"Amazon: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []
    review_divs = soup.find_all("div", {"data-hook": "review"})

    if not review_divs:
        logger.warning("Amazon: no review elements found (likely blocked)")
        return reviews

    for div in review_divs:
        try:
            author_el = div.find("span", class_="a-profile-name")
            rating_el = div.find("i", {"data-hook": "review-star-rating"})
            date_el   = div.find("span", {"data-hook": "review-date"})
            title_el  = div.find("a", {"data-hook": "review-title"})
            body_el   = div.find("span", {"data-hook": "review-body"})

            body = body_el.text.strip() if body_el else ""
            if not body:
                continue

            # rating string is "4.0 out of 5 stars" — grab just the number
            rating = rating_el.text.strip().split(" ")[0] if rating_el else "N/A"

            reviews.append({
                "author":      author_el.text.strip() if author_el else "Unknown",
                "rating":      rating,
                "date":        date_el.text.strip() if date_el else "N/A",
                "title":       title_el.text.strip() if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"Amazon: skipping review — {e}")

    return reviews


def parse_flipkart_reviews(html):
    # Try JSON-LD first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"Flipkart: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    # Flipkart uses obfuscated class names that change over time.
    # Try multiple known patterns across different Flipkart layouts.
    review_blocks = (
        soup.find_all("div", class_=re.compile(r"EPCmJX"))          # layout A
        or soup.find_all("div", class_=re.compile(r"_27M-vq"))      # layout B
        or soup.find_all("div", class_=re.compile(r"col _2wzgFH"))  # layout C
    )

    if not review_blocks:
        # Fallback: look for the reviews container and grab child divs
        container = soup.find("div", class_=re.compile(r"_4Ewn4|JAISCM|EIHun5"))
        if container:
            review_blocks = container.find_all("div", recursive=False)

    if not review_blocks:
        logger.warning("Flipkart: no review containers found")
        return reviews

    for block in review_blocks:
        try:
            # Rating: numeric div or span
            rating_el = (
                block.find("div", class_=re.compile(r"XQDdHH|_3LWZlK"))
                or block.find("span", class_=re.compile(r"XQDdHH|_3LWZlK"))
            )
            # Review title
            title_el = block.find("p", class_=re.compile(r"z9E0IG|_2-N8zT"))
            # Review body
            body_el = block.find("div", class_=re.compile(r"ZmyHeo|_6K-7Co"))
            # Author
            author_el = block.find("p", class_=re.compile(r"_2sc7ZR|_4AzHi"))
            # Date
            date_el = block.find("p", class_=re.compile(r"_2NsDsV|_2sc7ZR"))

            body = body_el.get_text(" ", strip=True) if body_el else ""
            if not body or len(body) < 10:
                continue

            reviews.append({
                "author":      author_el.text.strip() if author_el else "Flipkart Customer",
                "rating":      rating_el.text.strip() if rating_el else "N/A",
                "date":        date_el.text.strip() if date_el else "N/A",
                "title":       title_el.text.strip() if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"Flipkart: skipping review — {e}")

    return reviews


def parse_trustpilot_reviews(html):
    # Trustpilot reliably embeds JSON-LD — try it first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"Trustpilot: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    # Strategy: find every <article> on the page that has a <p> (body) and <time> (date).
    # This is stable regardless of class-name obfuscation.
    articles = soup.find_all("article")
    candidate_articles = [a for a in articles if a.find("p") and a.find("time")]

    if not candidate_articles:
        # Fallback: class-name patterns
        candidate_articles = (
            soup.find_all("article", {"data-service-review-card-paper": True})
            or soup.find_all("article", class_=re.compile(r"paper|reviewCard|card", re.I))
        )

    if not candidate_articles:
        logger.warning("Trustpilot: no review articles found in HTML")
        return reviews

    for article in candidate_articles:
        try:
            # Rating: data attribute > image alt text > star count
            rating = "N/A"
            rating_div = article.find(attrs={"data-service-review-rating": True})
            if rating_div:
                rating = rating_div["data-service-review-rating"]
            else:
                star_img = article.find("img", {"alt": re.compile(r"Rated \d|\d star", re.I)})
                if star_img:
                    m = re.search(r"(\d+\.?\d*)", star_img.get("alt", ""))
                    if m:
                        rating = m.group(1)

            # Title: h2 → h3 → first strong
            title_el = article.find("h2") or article.find("h3") or article.find("strong")

            # Body: biggest <p> in the article
            paras = article.find_all("p")
            body_el = max(paras, key=lambda p: len(p.get_text()), default=None) if paras else None

            # Author: span with consumer/profile class, or first named span
            author_el = (
                article.find(attrs={"data-consumer-name-typography": True})
                or article.find("span", class_=re.compile(r"consumer|name|author", re.I))
                or article.find("a", class_=re.compile(r"consumer|profile", re.I))
            )

            # Date: <time> tag
            time_el = article.find("time")
            date = "N/A"
            if time_el:
                date = time_el.get("datetime", time_el.get_text())[:10]

            body = body_el.get_text(" ", strip=True) if body_el else ""
            if not body or len(body) < 10:
                continue

            reviews.append({
                "author":      author_el.get_text(strip=True) if author_el else "Trustpilot User",
                "rating":      str(rating),
                "date":        date,
                "title":       title_el.get_text(strip=True) if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"Trustpilot: skipping review — {e}")

    return reviews


def parse_ebay_reviews(html):
    # Try JSON-LD first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"eBay: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    # eBay product review containers
    containers = (
        soup.find_all("div", class_=re.compile(r"ebayui-review-section|review-item|rvw", re.I))
        or soup.find_all("div", attrs={"itemprop": "review"})
    )

    # Fallback: look for the reviews section and grab children
    if not containers:
        review_section = soup.find("section", id=re.compile(r"review|feedback", re.I))
        if review_section:
            containers = review_section.find_all(["div", "article"])

    if not containers:
        logger.warning("eBay: no review containers found")
        return reviews

    for container in containers:
        try:
            # Rating — try aria-label or text
            rating = "N/A"
            rating_el = container.find(
                ["span", "div"],
                class_=re.compile(r"rating|star", re.I)
            )
            if rating_el:
                m = re.search(r"(\d\.?\d*)", rating_el.get("aria-label", rating_el.text))
                if m:
                    rating = m.group(1)

            # Also try itemprop
            rating_meta = container.find("meta", {"itemprop": "ratingValue"})
            if rating_meta:
                rating = rating_meta.get("content", rating)

            title_el = container.find(["h3", "h4"], class_=re.compile(r"title|heading", re.I))
            body_el  = container.find("p") or container.find(
                "span", class_=re.compile(r"review-content|body", re.I)
            )

            body = body_el.text.strip() if body_el else ""
            if not body:
                continue

            reviews.append({
                "author":      "eBay Buyer",
                "rating":      rating,
                "date":        "N/A",
                "title":       title_el.text.strip() if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"eBay: skipping review — {e}")

    return reviews


def parse_bestbuy_reviews(html):
    # Try JSON-LD first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"Best Buy: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    containers = (
        soup.find_all("li", class_=re.compile(r"review-item|ugc-review"))
        or soup.find_all("div", class_=re.compile(r"ugc-review|review-item"))
    )

    if not containers:
        logger.warning("Best Buy: no review containers found")
        return reviews

    for container in containers:
        try:
            # Rating — look for "X out of 5" text
            rating = "N/A"
            rating_el = container.find(
                ["p", "span"],
                class_=re.compile(r"rating-overview|sr-only|c-rating", re.I)
            )
            if rating_el:
                m = re.search(r"(\d\.?\d*)\s*out of\s*\d", rating_el.text, re.I)
                if m:
                    rating = m.group(1)

            title_el  = container.find(["h3", "h4", "p"], class_=re.compile(r"review-title|title", re.I))
            body_el   = container.find("p", class_=re.compile(r"pre-white-space|review-content", re.I))
            author_el = container.find(["span", "p"], class_=re.compile(r"author|reviewer", re.I))
            date_el   = container.find("time") or container.find(
                ["span", "p"], class_=re.compile(r"date|time", re.I)
            )

            body = body_el.text.strip() if body_el else ""
            if not body:
                continue

            reviews.append({
                "author":      author_el.text.strip() if author_el else "Best Buy Customer",
                "rating":      rating,
                "date":        date_el.text.strip() if date_el else "N/A",
                "title":       title_el.text.strip() if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"Best Buy: skipping review — {e}")

    return reviews


def parse_g2_reviews(html):
    # G2 embeds JSON-LD with itemprop — try it first
    ld_reviews = _parse_json_ld_reviews(html)
    if ld_reviews:
        logger.info(f"G2: got {len(ld_reviews)} reviews via JSON-LD")
        return ld_reviews

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    containers = (
        soup.find_all("div", attrs={"itemprop": "review"})
        or soup.find_all("div", class_=re.compile(r"paper paper--white paper--shadow"))
        or soup.find_all("div", class_=re.compile(r"review-card", re.I))
    )

    if not containers:
        logger.warning("G2: no review containers found")
        return reviews

    for container in containers:
        try:
            # Rating — prefer itemprop meta tag
            rating = "N/A"
            rating_meta = container.find("meta", {"itemprop": "ratingValue"})
            if rating_meta:
                rating = rating_meta.get("content", "N/A")
            else:
                star_el = container.find(class_=re.compile(r"stars|rating", re.I))
                if star_el:
                    m = re.search(r"(\d\.?\d*)", star_el.get("title", star_el.text))
                    if m:
                        rating = m.group(1)

            title_el  = container.find(["h3", "p"], {"itemprop": "name"}) \
                        or container.find(class_=re.compile(r"review-title", re.I))
            body_el   = container.find(["span", "p"], {"itemprop": "reviewBody"}) \
                        or container.find(["div", "p"], class_=re.compile(r"review-desc|body", re.I))
            author_el = container.find(["span", "div", "a"], {"itemprop": "name"})
            date_el   = container.find("time") or container.find(
                ["span", "p"], class_=re.compile(r"date|time", re.I)
            )

            body = body_el.text.strip() if body_el else ""
            if not body:
                continue

            reviews.append({
                "author":      author_el.text.strip() if author_el else "G2 User",
                "rating":      str(rating),
                "date":        date_el.text.strip() if date_el else "N/A",
                "title":       title_el.text.strip() if title_el else "",
                "review_text": body,
            })
        except Exception as e:
            logger.debug(f"G2: skipping review — {e}")

    return reviews


# ─────────────────────────────────────────────
#  PAGINATION
# ─────────────────────────────────────────────

def _get_next_page_url(html, current_url, platform):
    """Return the next-page URL or None if there is no next page."""
    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(current_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    def resolve(href):
        if not href:
            return None
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return base + href
        return None

    if platform == "Amazon":
        btn = soup.find("li", class_="a-last")
        if btn and btn.find("a"):
            return resolve(btn.find("a").get("href"))

    elif platform == "Trustpilot":
        btn = (
            soup.find("a", {"name": "pagination-button-next"})
            or soup.find("a", {"data-pagination-button-next-link": True})
            or soup.find("a", {"rel": "next"})
            or soup.find("a", class_=re.compile(r"pagination-button-next|next", re.I))
        )
        if btn:
            return resolve(btn.get("href"))

    elif platform == "Flipkart":
        btn = soup.find("a", class_=re.compile(r"_1LKTO3|_3s3Jj|next", re.I))
        if btn:
            return resolve(btn.get("href"))

    elif platform in ("Best Buy", "G2", "eBay"):
        btn = (
            soup.find("a", {"rel": "next"})
            or soup.find("a", class_=re.compile(r"next|pagination-next", re.I))
        )
        if btn:
            return resolve(btn.get("href"))

    return None


# ─────────────────────────────────────────────
#  PARSER REGISTRY & MAIN ENTRY
# ─────────────────────────────────────────────

PARSERS = {
    "Amazon":    parse_amazon_reviews,
    "Flipkart":  parse_flipkart_reviews,
    "Trustpilot":parse_trustpilot_reviews,
    "eBay":      parse_ebay_reviews,
    "Best Buy":  parse_bestbuy_reviews,
    "G2":        parse_g2_reviews,
}


def scrape_reviews(url, max_pages=3, status_cb=None):
    """
    Scrape reviews from the given URL.
    - Auto-detects the platform and routes to the right parser.
    - Uses a session with cookie prefetching to look more like a real browser.
    - status_cb: optional callable(str) for live progress updates (e.g. st.write).
    Returns (reviews: list, debug: dict).
    """
    def _log(msg):
        logger.info(msg)
        if status_cb:
            status_cb(msg)

    debug = {"platform": None, "pages_tried": 0, "html_sizes": [], "blocked": False}
    platform = detect_platform(url)
    debug["platform"] = platform

    if platform == "Unknown" or platform not in PARSERS:
        _log(f"❌ Unsupported platform for URL: {url}")
        return [], debug

    current_url = _build_reviews_url(url, platform)
    parse_fn    = PARSERS[platform]
    all_reviews = []
    page_num    = 1

    _log(f"🌐 Platform: **{platform}**")
    _log(f"🔗 Reviews URL: `{current_url}`")

    # Build one session per scrape job (shares cookies across pages)
    session = _make_session(platform)
    _log(f"🍚 Session ready (cookies: {len(session.cookies)})")

    while current_url and page_num <= max_pages:
        _log(f"\n📄 Fetching page {page_num}…")
        debug["pages_tried"] += 1
        try:
            html = get_page(current_url, platform=platform, session=session)

            if not html:
                debug["blocked"] = True
                _log(f"⚠️ Page {page_num}: empty / bot-blocked response")
                break

            debug["html_sizes"].append(len(html))
            _log(f"📦 Page {page_num}: received {len(html):,} bytes")

            # Quick sanity check — if page is too small it's probably an error page
            if len(html) < 2000:
                _log(f"⚠️ Page suspiciously small ({len(html)} bytes) — likely error page")
                _log(f"   Preview: {html[:300]}")
                break

            reviews = parse_fn(html)
            all_reviews.extend(reviews)
            _log(f"✅ Page {page_num}: found {len(reviews)} reviews (total so far: {len(all_reviews)})")

            if not reviews:
                _log(f"   ℹ️ No reviews found on this page — stopping pagination")
                # Show first 500 chars of HTML for debugging
                _log(f"   HTML preview: `{html[:500].strip()}`")
                break

            current_url = _get_next_page_url(html, current_url, platform)
            page_num += 1

        except Exception as e:
            _log(f"❌ Error on page {page_num}: {e}")
            debug["blocked"] = True
            break

    _log(f"\n🏁 Scraping done. Total: **{len(all_reviews)} reviews** from {platform}")
    return all_reviews, debug
