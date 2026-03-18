#!/usr/bin/env python3
"""Product scraper with AI-powered categorization and summarization.

Attempts Selenium (Amazon) -> requests (FakeStoreAPI) -> sample data fallback.
Enhances results with Claude AI for product categorization and buying recommendations.

Usage:
    python scraper.py                    # default: search for "laptops"
    python scraper.py --query="headphones"
"""

import argparse
import json
import logging
import sys

import anthropic
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CHROME_BINARY = "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome"
CHROMEDRIVER = "/opt/node22/bin/chromedriver"
AMAZON_URL = "https://www.amazon.com/s?k={query}"
FAKE_STORE_URL = "https://fakestoreapi.com/products"


def scrape_amazon(query: str, max_attempts: int = 2) -> list[dict]:
    """Scrape first 5 product listings from Amazon search results using Selenium."""
    opts = Options()
    opts.binary_location = CHROME_BINARY
    for arg in ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                 "--disable-gpu", "--window-size=1920,1080"]:
        opts.add_argument(arg)
    opts.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")

    for attempt in range(1, max_attempts + 1):
        driver = None
        try:
            log.info("Selenium attempt %d/%d for query '%s'", attempt, max_attempts, query)
            driver = webdriver.Chrome(service=Service(CHROMEDRIVER), options=opts)
            driver.get(AMAZON_URL.format(query=query))

            # Wait for search result cards to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                )
            )
            cards = driver.find_elements(
                By.CSS_SELECTOR, "div[data-component-type='s-search-result']"
            )[:5]

            if not cards:
                log.warning("No product cards found on attempt %d", attempt)
                continue

            products = []
            for card in cards:
                title = _safe_text(card, "h2 a span")
                url_el = card.find_elements(By.CSS_SELECTOR, "h2 a")
                url = url_el[0].get_attribute("href") if url_el else "N/A"
                price = _safe_text(card, "span.a-price > span.a-offscreen")
                rating = _safe_text(card, "span.a-icon-alt")
                products.append({"title": title, "price": price, "rating": rating, "url": url})

            log.info("Scraped %d products from Amazon via Selenium", len(products))
            return products
        except Exception as e:
            log.warning("Selenium attempt %d failed: %s", attempt, e)
        finally:
            if driver:
                driver.quit()
    return []


def _safe_text(parent, css: str) -> str:
    """Extract text from first matching element, or 'N/A'."""
    els = parent.find_elements(By.CSS_SELECTOR, css)
    return els[0].text.strip() if els else "N/A"


def fetch_fake_store(query: str) -> list[dict]:
    """Fallback: fetch products from FakeStoreAPI via requests."""
    try:
        log.info("Falling back to FakeStoreAPI...")
        resp = requests.get(FAKE_STORE_URL, params={"limit": 5}, timeout=10)
        resp.raise_for_status()
        return [
            {
                "title": p["title"],
                "price": f"${p['price']:.2f}",
                "rating": f"{p['rating']['rate']}/5 ({p['rating']['count']} reviews)",
                "url": f"https://fakestoreapi.com/products/{p['id']}",
            }
            for p in resp.json()[:5]
        ]
    except Exception as e:
        log.warning("FakeStoreAPI fallback failed: %s", e)
        return []


def sample_products(query: str) -> list[dict]:
    """Final fallback: return sample product data for demonstration."""
    log.info("Using sample data (network unavailable) for query '%s'", query)
    samples = [
        {"title": "ASUS VivoBook 15 Thin and Light Laptop, 15.6\" FHD",
         "price": "$379.99", "rating": "4.3/5", "url": "https://www.amazon.com/dp/B0B9N427DL"},
        {"title": "Acer Aspire 5 A515-56-702V Slim Laptop, 15.6\" Full HD IPS",
         "price": "$549.99", "rating": "4.5/5", "url": "https://www.amazon.com/dp/B09RC12GW3"},
        {"title": "Lenovo IdeaPad Gaming 3 15 Laptop, 15.6\" FHD 120Hz",
         "price": "$849.99", "rating": "4.4/5", "url": "https://www.amazon.com/dp/B0BSR6NFQK"},
        {"title": "HP Envy x360 2-in-1 Laptop, 15.6\" Full HD Touchscreen",
         "price": "$749.99", "rating": "4.2/5", "url": "https://www.amazon.com/dp/B0CMZG43VY"},
        {"title": "Dell XPS 15 9530 Laptop, 15.6\" 3.5K OLED InfinityEdge",
         "price": "$1,599.99", "rating": "4.6/5", "url": "https://www.amazon.com/dp/B0C2FVLQ1P"},
    ]
    return samples[:5]


def enhance_with_ai(products: list[dict], query: str) -> list[dict]:
    """Use Claude AI to categorize products and generate buying summaries."""
    try:
        client = anthropic.Anthropic()
        product_text = json.dumps(products, indent=2)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a product analyst. For each product below (search query: '{query}'), "
                    "provide a JSON array where each element has:\n"
                    '- "category": one of "budget", "mid-range", "gaming", "professional", "ultrabook"\n'
                    '- "ai_summary": a one-sentence buying recommendation with sentiment\n\n'
                    f"Products:\n{product_text}\n\n"
                    "Respond ONLY with the JSON array, no markdown fences or extra text."
                ),
            }],
        )

        ai_results = json.loads(response.content[0].text)
        for product, ai_data in zip(products, ai_results):
            product["category"] = ai_data.get("category", "unknown")
            product["ai_summary"] = ai_data.get("ai_summary", "No summary available.")
        log.info("AI enhancement complete")
    except Exception as e:
        log.warning("AI enhancement failed: %s — returning data without AI fields", e)
        for product in products:
            product.setdefault("category", "unknown")
            product.setdefault("ai_summary", "AI enhancement unavailable.")
    return products


def main():
    parser = argparse.ArgumentParser(description="Scrape products with AI enhancement")
    parser.add_argument("--query", default="laptops", help="Search query (default: laptops)")
    args = parser.parse_args()

    # Part 1: Scrape products with cascading fallbacks
    products = scrape_amazon(args.query)
    source = "Amazon (Selenium)"
    if not products:
        products = fetch_fake_store(args.query)
        source = "FakeStoreAPI (requests)"
    if not products:
        products = sample_products(args.query)
        source = "Sample data (offline fallback)"

    log.info("Data source: %s — %d products found", source, len(products))

    # Part 2: Enhance with AI
    products = enhance_with_ai(products, args.query)

    # Output final JSON
    print(json.dumps(products, indent=2))


if __name__ == "__main__":
    main()
