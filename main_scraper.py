import os
from dotenv import load_dotenv
import argparse
import time

# Import the new universal CRM scraper
from caroogocrm_scraper import scrape_crm_api

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Caroogo Inventory Master Scraper")
    parser.add_argument("--enrich-cargurus", action="store_true", help="Run CarGurus enrichment for scraped vehicles")
    args = parser.parse_args()

    # Call the newly created universal CRM API scraper
    scrape_crm_api()
    
    # Enrichment phase
    if args.enrich_cargurus:
        from scrapers.cargurus import CarGurusEnricher
        from supabase import create_client
        
        SUPABASE_URL = "https://hwferrqmgqcvqfsqsjmp.supabase.co"
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        print(f"Starting CarGurus enrichment...")
        v_res = supabase.table("vehicles").select("vin", "dealership_id").execute()
        
        for v in v_res.data:
            enricher = CarGurusEnricher(supabase, v["dealership_id"], "Unknown")
            enricher.enrich(v["vin"])
            time.sleep(2)

if __name__ == "__main__":
    main()
