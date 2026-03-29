import requests
from bs4 import BeautifulSoup
import time
import random
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# trying to look like a real browser as much as possible
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# sample reviews for demo/fallback mode
# these are realistic-looking reviews for the Echo Dot product
DEMO_REVIEWS = [
    {
        "author": "Sarah M.",
        "rating": "5.0",
        "date": "Reviewed in the United States on January 15, 2024",
        "title": "Best smart speaker for the price",
        "review_text": "I've had this for about 3 months now and honestly it's exceeded my expectations. The sound quality is surprisingly good for such a small device. I use it mainly for music, setting timers, and controlling my smart home lights. Setup was dead simple — took maybe 5 minutes. The new design is way better than the older egg-shaped ones. Only minor complaint is Alexa sometimes mishears me but that's maybe 1 out of 20 commands."
    },
    {
        "author": "James T.",
        "rating": "2.0",
        "date": "Reviewed in the United States on February 3, 2024",
        "title": "Disappointed with the microphone quality",
        "review_text": "Bought this to replace my older Echo Dot and honestly I regret it. The microphone doesn't pick up my voice from across the room like the old one did. I have to speak loudly or be close to it. Also had some connectivity issues where it would randomly disconnect from WiFi. Amazon support was helpful but the problem kept coming back. The sound quality is fine I guess but the whole point of these things is voice control and that part is worse than my 4 year old device."
    },
    {
        "author": "Priya K.",
        "rating": "4.0",
        "date": "Reviewed in the United States on March 10, 2024",
        "title": "Good product, minor software issues",
        "review_text": "Pretty happy with this purchase overall. Sound is clear and crisp, Alexa responds quickly most of the time. I dock one star because of some annoying software behavior — it sometimes randomly starts playing music I didn't ask for, and the daily briefing feature is hard to turn off completely. Once you figure out the settings it's fine. Build quality feels solid and the matte finish looks great on my desk."
    },
    {
        "author": "Mike R.",
        "rating": "5.0",
        "date": "Reviewed in the United States on December 28, 2023",
        "title": "Great gift, family loves it",
        "review_text": "Got this as a Christmas gift for my parents who aren't very tech savvy. They figured it out completely on their own which says a lot. My mom uses it to listen to oldies music all day and my dad uses it for weather updates and sports scores. The speaker is loud enough for an average sized room. Definitely recommend for older folks who just want something simple that works."
    },
    {
        "author": "Alex W.",
        "rating": "1.0",
        "date": "Reviewed in the United States on January 30, 2024",
        "title": "Stopped working after 6 weeks",
        "review_text": "Worked fine for about 6 weeks then completely died. Won't turn on at all, no lights, nothing. I tried different power adapters and outlets. Amazon replaced it but now I'm nervous the replacement will die too. First time I've had a hardware failure this quick on any Amazon device. Hoping this was just a bad unit."
    },
    {
        "author": "Chen L.",
        "rating": "4.0",
        "date": "Reviewed in the United States on February 20, 2024",
        "title": "Solid upgrade from Gen 4",
        "review_text": "Upgraded from the 4th gen and there's a noticeable improvement in bass. Not audiophile level by any means but for a $50 speaker it punches well above its weight. The temperature sensor is a nice addition — I check the room temp all the time now. Alexa feels snappier too, responses are quicker. Still has the same limitation of relying on Amazon ecosystem but if you're already in that world this is a no brainer."
    },
    {
        "author": "Diana P.",
        "rating": "3.0",
        "date": "Reviewed in the United States on March 5, 2024",
        "title": "Mixed feelings",
        "review_text": "It does what it's supposed to do but I feel like the smart home integration has gotten worse with recent updates. Commands that used to work reliably now sometimes fail or give weird responses. The hardware itself is fine, actually better than before. But Alexa as a platform feels like it's going backwards lately. I've been thinking about switching to Google Home for a while and this experience is making me more likely to do it."
    },
    {
        "author": "Tom B.",
        "rating": "5.0",
        "date": "Reviewed in the United States on January 8, 2024",
        "title": "Perfect for the bedroom",
        "review_text": "Using this as a bedside alarm clock replacement and it's perfect for that. I ask it to wake me up, get the weather, and play some lo-fi music while I sleep. The volume goes low enough that it doesn't disturb my partner. The night light feature (with the color ring) is a nice touch. Much better than constantly reaching for my phone in the morning."
    }
]


def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            # random delay to look less like a bot
            time.sleep(random.uniform(2.0, 4.5))
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (503, 429):
                logger.warning(f"Got {code} (bot check/rate limit), waiting before retry...")
                time.sleep(5 + attempt * 3)
            elif code == 404:
                logger.error("Page not found (404). Check the URL.")
                raise
            else:
                logger.warning(f"HTTP {code} on attempt {attempt+1}")
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
        logger.warning("No review elements found — Amazon likely blocked the request")
        return reviews

    for div in review_divs:
        try:
            author_el = div.find("span", class_="a-profile-name")
            rating_el = div.find("i", {"data-hook": "review-star-rating"})
            date_el = div.find("span", {"data-hook": "review-date"})
            title_el = div.find("a", {"data-hook": "review-title"})
            body_el = div.find("span", {"data-hook": "review-body"})

            author = author_el.text.strip() if author_el else "Unknown"
            # rating is like "4.0 out of 5 stars", just grab the number
            rating = rating_el.text.strip().split(" ")[0] if rating_el else "N/A"
            date = date_el.text.strip() if date_el else "N/A"
            title = title_el.text.strip() if title_el else ""
            body = body_el.text.strip() if body_el else ""

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

    # amazon product pages (/dp/) need to be sent to the reviews page
    if "amazon.com" in url and "/dp/" in url:
        asin = url.split("/dp/")[1].split("/")[0].split("?")[0]
        current_url = f"https://www.amazon.com/product-reviews/{asin}?reviewerType=all_reviews&sortBy=recent&pageNumber=1"
        logger.info(f"Detected Amazon product URL, using reviews page (ASIN: {asin})")
    else:
        current_url = url

    while current_url and page_num <= max_pages:
        logger.info(f"Scraping page {page_num}...")

        try:
            html = get_page(current_url)
            if not html:
                logger.error("Empty response, stopping")
                break

            reviews = parse_amazon_reviews(html)
            all_reviews.extend(reviews)
            logger.info(f"Page {page_num}: got {len(reviews)} reviews (total: {len(all_reviews)})")

            if not reviews:
                logger.info("No reviews on this page, stopping pagination")
                break

            next_url = get_next_page_url(html, current_url)
            current_url = next_url
            page_num += 1

        except Exception as e:
            logger.error(f"Error scraping page {page_num}: {e}")
            break

    logger.info(f"Scraping done. Total: {len(all_reviews)} reviews")
    return all_reviews


def get_demo_reviews():
    """Returns sample reviews for demo/testing when Amazon blocks scraping."""
    logger.info("Using demo reviews (Amazon scraping blocked)")
    return DEMO_REVIEWS
