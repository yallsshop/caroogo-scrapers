"""
Parallel Scrapling scraper test runner.

Usage:
    python run_scrapling_test.py --scraper collins_nissan
    python run_scrapling_test.py --scraper cargurus --vin <VIN>

This runs the Scrapling-based scrapers in scrapling_scrapers/ alongside
the existing scrapers without touching or replacing anything.
"""

import os
import argparse
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = "https://hwferrqmgqcvqfsqsjmp.supabase.co"
SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh3ZmVycnFtZ3FjdnFmc3Fzam1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA3ODkxNDksImV4cCI6MjA4NjM2NTE0OX0.XOLifQXc2AmRuizRkKO6QEsjqY2k0_fhHnfEIPmJMAg",
)

# Dealer IDs — update these to match your Supabase records
COLLINS_NISSAN_DEALER_ID = os.getenv("COLLINS_NISSAN_DEALER_ID", "collins_nissan")


def main():
    parser = argparse.ArgumentParser(description="Scrapling scraper test runner")
    parser.add_argument(
        "--scraper",
        required=True,
        choices=["collins_nissan", "cargurus"],
        help="Which scraper to run",
    )
    parser.add_argument(
        "--vin",
        help="VIN to enrich (required for --scraper cargurus)",
    )
    args = parser.parse_args()

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    if args.scraper == "collins_nissan":
        from scrapling_scrapers.collins_nissan import CollinsNissanScraper

        scraper = CollinsNissanScraper(
            supabase=supabase,
            dealer_id=COLLINS_NISSAN_DEALER_ID,
            dealer_name="Collins Nissan (Scrapling)",
        )
        scraper.scrape()

    elif args.scraper == "cargurus":
        if not args.vin:
            parser.error("--vin is required when using --scraper cargurus")

        from scrapling_scrapers.cargurus import CarGurusEnricher

        enricher = CarGurusEnricher(
            supabase=supabase,
            dealer_id="unknown",
            dealer_name="CarGurus Enricher (Scrapling)",
        )
        enricher.enrich(args.vin)


if __name__ == "__main__":
    main()
