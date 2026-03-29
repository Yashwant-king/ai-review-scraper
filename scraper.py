import requests
from bs4 import BeautifulSoup
import time
import random
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# trying to look like a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            # random delay so we don't hammer the server
            time.sleep(random.uniform(2.0, 4.5))
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 503:
                logger.warning(f"Got 503 (bot check?) on attempt {attempt+1}, waiting a bit...")
                time.sleep(5 + attempt * 3)
            elif e.response.status_code == 404:
                logger.error("Page not found (404). Check the URL.")
                raise
            else:
                logger.warning(f"HTTP error on attempt {attempt+1}: {e}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed on attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    return None


def parse_amazon_reviews(html):
    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    review_divs = soup.find_all("div", {"data-hook": "review"})

    if not review_divs:
        logger.warning("No review elements found — Amazon may be blocking the request or the page structure changed")
        return reviews

    for div in review_divs:
        try:
            author_el = div.find("span", class_="a-profile-name")
            rating_el = div.find("i", {"data-hook": "review-star-rating"})
            date_el = div.find("span", {"data-hook": "review-date"})
            title_el = div.find("a", {"data-hook": "review-title"})
            body_el = div.find("span", {"data-hook": "review-body"})

            author = author_el.text.strip() if author_el else "Unknown"
            # rating looks like "4.0 out of 5 stars", grab just the number
            rating = rating_el.text.strip().split(" ")[0] if rating_el else "N/A"
            date = date_el.text.strip() if date_el else "N/A"
            title = title_el.text.strip() if title_el else ""
            body = body_el.text.strip() if body_el else ""

            # no point keeping empty reviews
            if not body:
                continue

            reviews.append({
                "author": author,
                "rating": rating,
                "date": date,
                "title": title,
                "review_text": body
            })

        except Exception as e:
            logger.debug(f"Skipping review due to parse error: {e}")
            continue

    return reviews


def get_next_page_url(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.find("li", class_="a-last")

    if next_btn and next_btn.find("a"):
        href = next_btn.find("a").get("href", "")
        if href.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        elif href.startswith("http"):
            return href

    return None


def scrape_reviews(url, max_pages=3):
    all_reviews = []
    page_num = 1

    # amazon product pages (/dp/) need to be redirected to the reviews page
    if "amazon.com" in url and "/dp/" in url:
        asin = url.split("/dp/")[1].split("/")[0].split("?")[0]
        current_url = f"https://www.amazon.com/product-reviews/{asin}?reviewerType=all_reviews&sortBy=recent&pageNumber=1"
        logger.info(f"Detected Amazon product URL, switching to reviews page (ASIN: {asin})")
    else:
        current_url = url

    while current_url and page_num <= max_pages:
        logger.info(f"Scraping page {page_num}...")

        try:
            html = get_page(current_url)
            if not html:
                logger.error("Got no HTML back, stopping")
                break

            reviews = parse_amazon_reviews(html)
            all_reviews.extend(reviews)
            logger.info(f"Page {page_num}: scraped {len(reviews)} reviews (total so far: {len(all_reviews)})")

            if not reviews:
                logger.info("No more reviews found, done with pagination")
                break

            next_url = get_next_page_url(html, current_url)
            current_url = next_url
            page_num += 1

        except Exception as e:
            logger.error(f"Error on page {page_num}: {e}")
            break

    logger.info(f"Finished scraping. Total reviews collected: {len(all_reviews)}")
    return all_reviews
