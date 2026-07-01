import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATALOG_URL = "https://www.shl.com/solutions/products/product-catalog/?type=1"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "shl_catalog.json"

def scrape_catalog():
    assessments = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        logger.info(f"Navigating to {CATALOG_URL}")
        page.goto(CATALOG_URL)
        
        # This is a placeholder for the actual scraping logic.
        # Since the SHL catalog has dynamic loading, you would typically:
        # 1. Wait for the assessment list to load
        # 2. Extract details from each item (name, url, type, duration, etc.)
        # 3. Handle pagination
        
        # Mocking some data for demonstration purposes
        logger.info("Scraping assessments...")
        
        assessments = [
            {
                "name": "Verify G+ (General Ability)",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-g-plus/",
                "description": "Combines numerical, deductive, and inductive reasoning.",
                "test_type": "A",
                "duration": 36,
                "remote_support": True,
                "adaptive_support": True,
                "category": "Cognitive Ability"
            },
            {
                "name": "OPQ32r",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/opq32r/",
                "description": "Occupational Personality Questionnaire for predicting workplace behavior.",
                "test_type": "P",
                "duration": 25,
                "remote_support": True,
                "adaptive_support": False,
                "category": "Personality & Behaviour"
            },
            {
                "name": "Java 8 (New)",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/java-8-new/",
                "description": "Assesses knowledge of Java programming concepts and syntax.",
                "test_type": "K",
                "duration": 40,
                "remote_support": True,
                "adaptive_support": False,
                "category": "Knowledge & Skills"
            }
        ]
        
        browser.close()
        
    # Save the data
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(assessments, f, indent=2)
        
    logger.info(f"Saved {len(assessments)} assessments to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_catalog()
