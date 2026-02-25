import os
from supabase import create_client, Client
from dotenv import load_dotenv
import argparse
import time

# Import modular scrapers
from scrapers.bill_collins import BillCollinsScraper
from scrapers.collins_nissan import CollinsNissanScraper
from scrapers.cargurus import CarGurusEnricher

load_dotenv()

SUPABASE_URL = "https://hwferrqmgqcvqfsqsjmp.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh3ZmVycnFtZ3FjdnFmc3Fzam1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA3ODkxNDksImV4cCI6MjA4NjM2NTE0OX0.XOLifQXc2AmRuizRkKO6QEsjqY2k0_fhHnfEIPmJMAg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_dealers():
    res = supabase.table("dealerships").select("*").execute()
    return res.data

def main():
    parser = argparse.ArgumentParser(description="Caroogo Inventory Master Scraper")
    parser.add_argument("--dealer", help="Specific dealer name to scrape")
    parser.add_argument("--enrich-cargurus", action="store_true", help="Run CarGurus enrichment for scraped vehicles")
    args = parser.parse_args()

    dealers = get_dealers()
    print(f"Found {len(dealers)} dealers in database.")
    
    for d in dealers:
        print(f"Checking dealer: {d['name']} (ID: {d['id']})")
        if args.dealer and args.dealer.lower() not in d["name"].lower():
            continue
            
        print(f"Running scraper for: {d['name']}")
        if "Bill Collins Ford" in d["name"]:
            s = BillCollinsScraper(supabase, d["id"], d["name"])
            s.scrape()
        elif "Collins Nissan" in d["name"]:
            s = CollinsNissanScraper(supabase, d["id"], d["name"])
            s.scrape()
        else:
            print(f"No scraper implemented for {d['name']}")

        # Enrichment phase
        if args.enrich_cargurus:
            print(f"Starting CarGurus enrichment for {d['name']}...")
            # Get vehicles for this dealer
            v_res = supabase.table("vehicles").select("vin").eq("dealership_id", d["id"]).execute()
            vins = [v["vin"] for v in v_res.data]
            print(f"Found {len(vins)} vehicles to enrich.")
            
            enricher = CarGurusEnricher(supabase, d["id"], d["name"])
            for vin in vins:
                enricher.enrich(vin)
                time.sleep(2)

if __name__ == "__main__":
    main()
