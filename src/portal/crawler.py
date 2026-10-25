import random
import time
from datetime import date
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

from src.config import COMMUNES, TYPES, URL_PORTAL_INMOBILIARIO
from src.portal.scraper import extract_listings

# Project root = two levels up from this file (src/portal/crawler.py)
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "portal"

NEXT_BUTTON = 'a[data-andes-pagination-control="next"]'
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def remove_overlays(page):
    """Remove the cookie banner and onboarding tooltips that block clicks."""
    page.evaluate("""() => {
        document
            .querySelectorAll('.andes-coach-marks, #newCookieDisclaimerBanner')
            .forEach(el => el.remove());
    }""")


def click_next(page):
    """Click 'Siguiente'. Falls back to a JavaScript click if something blocks it."""
    remove_overlays(page)
    try:
        page.locator(NEXT_BUTTON).first.click(timeout=5000)
    except Exception:
        page.evaluate(f"() => document.querySelector('{NEXT_BUTTON}').click()")


def scrape_search(page, commune, property_type, start_url, max_pages):
    """Walk through every results page of one search and return all listings."""
    rows = []
    seen_ids = set()
    page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

    for page_number in range(1, max_pages + 1):
        try:
            page.wait_for_selector(".andes-money-amount", timeout=15000)
        except Exception:
            print(f"    page {page_number}: no listings found, stopping")
            break

        new_rows = extract_listings(page.content(), commune, property_type)
        new_ids = {r["id"] for r in new_rows} - seen_ids
        if not new_ids:
            print(f"    page {page_number}: no new listings, stopping")
            break
        seen_ids |= new_ids
        rows.extend(new_rows)
        print(f"    page {page_number}: {len(new_rows)} listings")

        button = page.locator(NEXT_BUTTON)
        if button.count() == 0:
            break
        parent_classes = button.first.locator("xpath=..").get_attribute("class") or ""
        if "disabled" in parent_classes:
            break

        time.sleep(random.uniform(2, 5))

        old_url = page.url
        click_next(page)
        try:
            page.wait_for_url(lambda u: u != old_url, timeout=15000)
        except Exception:
            page.wait_for_timeout(4000)

    return rows


def run_crawl(communes=None, property_types=None, max_pages=50, run_date=None):
    """
    Download listings and save one CSV per commune and property type.
    Searches that already have a CSV in this run's folder are skipped.
    Returns the folder where the files were saved.
    """
    communes = communes or COMMUNES
    property_types = property_types or TYPES
    run_date = run_date or date.today().isoformat()

    run_dir = RAW_DIR / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="es-CL",
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        for commune, slug in communes.items():
            for property_type in property_types:
                output_file = run_dir / f"{property_type}_{slug}.csv"
                if output_file.exists():
                    print(f"{commune} - {property_type}: already done, skipping")
                    continue

                print(f"{commune} - {property_type}")
                start_url = f"{URL_PORTAL_INMOBILIARIO}/{property_type}/{slug}"
                rows = scrape_search(page, commune, property_type, start_url, max_pages)

                if not rows:
                    print("  -> no listings, nothing saved\n")
                    continue

                df = pd.DataFrame(rows)
                df["scraped_at"] = run_date
                df = df.drop_duplicates(subset=["id"])
                df.to_csv(output_file, index=False, encoding="utf-8")
                print(f"  -> saved {len(df)} listings\n")

        browser.close()

    return run_dir


# Still runnable from the terminal: python -m src.portal.crawler
if __name__ == "__main__":
    run_crawl()