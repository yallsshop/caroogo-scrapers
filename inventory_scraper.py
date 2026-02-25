"""
Caroogo Inventory Scraper - Simplified
Pulls all vehicle data from the Caroogo VehicleSearch API and upserts into Supabase.
Single file, single source of truth. Runs via GitHub Actions twice daily.
"""

import os
import httpx
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SUPABASE_URL = "https://hwferrqmgqcvqfsqsjmp.supabase.co"
SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh3ZmVycnFtZ3FjdnFmc3Fzam1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA3ODkxNDksImV4cCI6MjA4NjM2NTE0OX0.XOLifQXc2AmRuizRkKO6QEsjqY2k0_fhHnfEIPmJMAg",
)

API_URL = "https://vehicles.caroogo.com/api/v2/Vehicle/VehicleSearch"
PAGE_SIZE = 50

# Caroogo dealer IDs -> our Supabase dealership UUIDs
# These get resolved on first run
DEALER_MAP = {}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_or_create_dealership(dealer_id: int, location: dict | None = None) -> str:
    """Map Caroogo dealer IDs to Supabase dealership UUIDs."""
    if dealer_id in DEALER_MAP:
        return DEALER_MAP[dealer_id]

    # Known dealer mapping
    name_map = {
        50000: ("Bill Collins Ford Lincoln", "https://billcollinsford.net"),
        50001: ("Collins Nissan", "https://collinsnissan.com"),
    }

    name, website = name_map.get(dealer_id, (f"Dealer {dealer_id}", "https://caroogo.com"))

    res = supabase.table("dealerships").select("id").eq("name", name).execute()
    if res.data:
        uuid = res.data[0]["id"]
    else:
        new = supabase.table("dealerships").insert({
            "name": name,
            "website_url": website,
            "platform": "Caroogo",
        }).execute()
        uuid = new.data[0]["id"]

    DEALER_MAP[dealer_id] = uuid
    return uuid


def parse_condition(raw: str) -> str:
    """Map API condition strings to our enum values: New, Used, CPO."""
    lower = raw.lower()
    if "new" in lower:
        return "New"
    if "certified" in lower:
        return "CPO"
    return "Used"


def parse_vehicle(v: dict) -> dict | None:
    """Transform a VehicleSearch API record into a flat vehicles table row."""
    vin = v.get("vin")
    if not vin:
        return None

    # Dealer info from first entry in vehicleDealers
    dealers = v.get("vehicleDealers") or [{}]
    dealer_info = dealers[0] if dealers else {}
    dealer_id = dealer_info.get("dealerId", 50000)
    location = dealer_info.get("location") or {}

    # Current pricing - get non-expired prices
    prices = dealer_info.get("vehicleDealerPrices") or []
    current_prices = {}
    for p in prices:
        if p.get("expirationDate") is None:
            current_prices[p.get("pricingType", "")] = p.get("price", 0) or 0

    # Financing / monthly payment
    financing = v.get("vehicleDetailFinancing") or []
    monthly = 0
    for f in financing:
        if f.get("type") == "Retail" and f.get("term") == 60:
            monthly = f.get("payment", 0) or 0
            break

    # Inventory age
    inv_start = dealer_info.get("inventoryStart")
    days_in_stock = None
    if inv_start:
        try:
            start_dt = datetime.fromisoformat(inv_start.replace("+00:00", "+00:00"))
            days_in_stock = (datetime.now(start_dt.tzinfo) - start_dt).days
        except Exception:
            pass

    return {
        "vin": vin,
        "dealership_id": get_or_create_dealership(dealer_id, location),
        "stock_number": dealer_info.get("stockNumber"),
        "condition": parse_condition(dealer_info.get("vehicleCondition", "Used")),
        "year": v.get("modelYear"),
        "make": v.get("make"),
        "model": v.get("model"),
        "trim": v.get("trim"),
        "series": v.get("series"),
        "category": v.get("category"),
        "body_style": v.get("body"),
        "exterior_color": v.get("exteriorColor"),
        "interior_color": v.get("interiorColor"),
        "exterior_generic_color": v.get("exteriorGenericColor"),
        "interior_generic_color": v.get("interiorGenericColor"),
        "exterior_hex_code": v.get("exteriorHexCode"),
        "interior_hex_code": v.get("interiorHexCode"),
        "transmission": v.get("transmission"),
        "drivetrain": v.get("driveType"),
        "engine_description": v.get("engine"),
        "horsepower": v.get("horsepower"),
        "torque": v.get("torque"),
        "engine_type": v.get("engineType"),
        "fuel": v.get("fuel"),
        "cylinders": v.get("cylinders"),
        "doors": v.get("numberOfDoors"),
        "seat_count": v.get("seatCount"),
        "towing_capacity": v.get("towingCapacity"),
        "mileage": v.get("mileage") or 0,
        "mpg_city": v.get("highCityFuelEconomy"),
        "mpg_hwy": v.get("highHighwayFuelEconomy"),
        "certified_preowned": dealer_info.get("certifiedPreowned", False),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "inventory_start": inv_start,
        "days_on_market": days_in_stock,
        # Flattened pricing
        "msrp": current_prices.get("MSRP", v.get("currentMsrpPrice", 0) or 0),
        "internet_price": current_prices.get("Internet", v.get("currentInternetPrice", 0) or 0),
        "vendor_price": current_prices.get("Vendor", v.get("currentVendorPrice", 0) or 0),
        "employee_price": current_prices.get("Employee", v.get("currentEmployeePrice", 0) or 0),
        "wholesale_price": current_prices.get("Wholesale", v.get("currentWholesalePrice", 0) or 0),
        "monthly_payment": monthly,
        # Image
        "primary_image": v.get("primaryImage"),
        "source_dealer_id": dealer_id,
        "status": "In Stock",
        "scraped_at": "now()",
    }


def scrape():
    print(f"[{datetime.now().isoformat()}] Starting Caroogo inventory scrape...")

    page = 1
    total_upserted = 0
    all_vins = set()

    with httpx.Client(timeout=30.0) as client:
        while True:
            payload = {
                "currentPage": page,
                "pageSize": PAGE_SIZE,
                "sortBy": "Year",
                "sortDirection": "Desc",
            }

            res = client.post(API_URL, json=payload, headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "CaroogoScraper/2.0",
            })

            if res.status_code != 200:
                print(f"  API error on page {page}: {res.status_code}")
                break

            data = res.json()
            vehicles = data.get("vehicles", [])

            if not vehicles:
                break

            total_count = data.get("totalCount", "?")
            batch = []

            for v in vehicles:
                record = parse_vehicle(v)
                if record and record["vin"] not in all_vins:
                    all_vins.add(record["vin"])
                    batch.append(record)

            if batch:
                try:
                    supabase.table("vehicles").upsert(batch).execute()
                    total_upserted += len(batch)
                except Exception as e:
                    print(f"  Batch upsert failed on page {page}: {e}")
                    # Fall back to individual upserts
                    for record in batch:
                        try:
                            supabase.table("vehicles").upsert(record).execute()
                            total_upserted += 1
                        except Exception as e2:
                            print(f"  Failed VIN {record['vin']}: {e2}")

            print(f"  Page {page}: {len(batch)} vehicles (total: {total_upserted}/{total_count})")
            page += 1

    # Mark vehicles no longer in feed as potentially sold
    if all_vins:
        existing = supabase.table("vehicles").select("vin").eq("status", "In Stock").execute()
        stale_vins = [v["vin"] for v in (existing.data or []) if v["vin"] not in all_vins]
        if stale_vins:
            # Batch update stale vehicles in chunks
            for i in range(0, len(stale_vins), 50):
                chunk = stale_vins[i : i + 50]
                supabase.table("vehicles").update({"status": "Sold"}).in_("vin", chunk).execute()
            print(f"  Marked {len(stale_vins)} vehicles as Sold (no longer in feed)")

    print(f"[{datetime.now().isoformat()}] Done. {total_upserted} vehicles upserted.")


if __name__ == "__main__":
    scrape()
