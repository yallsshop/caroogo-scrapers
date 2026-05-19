import os
import httpx
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = "https://hwferrqmgqcvqfsqsjmp.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_dealership(dealer_id_str):
    name_map = {
        "1": "Bill Collins Ford",
        "2": "Collins Nissan",
        "3": "Caroogo"
    }
    name = name_map.get(str(dealer_id_str), f"Dealer {dealer_id_str}")
    
    # Check if dealer exists
    response = supabase.table("dealerships").select("*").eq("name", name).execute()
    if response.data:
        return response.data[0]["id"]
    else:
        # Create it if we haven't seen it
        new_dealer = {
            "name": name,
            "website_url": "https://caroogo.com", # placeholder
            "platform": "CaroogoCRM"
        }
        res = supabase.table("dealerships").insert(new_dealer).execute()
        return res.data[0]["id"]

def scrape_crm_api():
    print("Starting Main CRM API Fetch...")
    url = "https://caroogocrm.com/api/apps/6900d8f18678d0668840afe5/entities/Vehicle"
    
    with httpx.Client(timeout=30.0) as client:
        res = client.get(url)
        if res.status_code != 200:
            print(f"Failed to fetch CRM data: {res.status_code}")
            return
            
        vehicles_data = res.json()
        print(f"Downloaded {len(vehicles_data)} total raw records from CRM.")
    
    # Deduplication map
    # Key: vin (or stock_number if vin is null)
    # Value: entire vehicle record
    unique_vehicles = {}
    dupes_skipped = 0
    
    for v in vehicles_data:
        vin = v.get("vin")
        stock = v.get("stock_number")
        
        # Determine the best unique identifier
        key = vin if vin else stock
        if not key:
            continue # If it has no VIN and no Stock, it's garbage data
            
        key = str(key).upper().strip()
        
        # If we already have this VIN/Stock, skip it to deduplicate
        if key in unique_vehicles:
            dupes_skipped += 1
            # We could merge them, but for now we take the first match to keep the DB clean
            continue
            
        unique_vehicles[key] = v

    print(f"Deduplicated down to {len(unique_vehicles)} unique items. Skipped {dupes_skipped} duplicates.")
    
    fetched_dealers = {}
    inserted = 0
    
    for key, v in unique_vehicles.items():
        # Get or create dealer in Supabase
        dealer_crm_id = v.get("dealership", "3")
        if dealer_crm_id not in fetched_dealers:
            fetched_dealers[dealer_crm_id] = init_dealership(dealer_crm_id)
            
        supa_dealer_id = fetched_dealers[dealer_crm_id]
        
        vin = v.get("vin")
        # If the API returned null for VIN, we MUST fallback to the stock number
        if not vin:
            vin = f"UNKNOWN_{v.get('stock_number', 'NOSTOCK')}"
            
        year = v.get("year", 0)
        make = v.get("make", "Unknown")
        model = v.get("model", "Unknown")
        condition = str(v.get("condition", "used")).capitalize()
        status = str(v.get("status", "available")).capitalize()
        if status.lower() == "available": status = "In Stock"
        
        vehicle_record = {
            "vin": vin,
            "dealership_id": supa_dealer_id,
            "stock_number": v.get("stock_number"),
            "condition": condition,
            "year": int(float(year)) if str(year).replace(".", "").isdigit() else 2024,
            "make": make,
            "model": model,
            "trim": v.get("trim"),
            "exterior_color": v.get("exterior_color"),
            "interior_color": v.get("interior_color"),
            "mileage": int(float(v.get("mileage", 0) or 0)),
            "status": status,
            "description": v.get("description", "")
        }
        
        try:
            # 1. Upsert Vehicle
            # Supabase requires an EXACT match on the primary key (vin) for upsert.
            supabase.table("vehicles").upsert(vehicle_record).execute()
            
            # 2. Insert/Update Pricing
            price = v.get("price", 0) or 0
            msrp = v.get("msrp", 0) or 0
            
            pricing_record = {
                "vin": vin,
                "msrp": msrp,
                "retail_price": price,
                "internet_price": v.get("internet_price", price) or price,
                "dealer_discount": max(0, msrp - price)
            }
            supabase.table("vehicle_pricing").upsert(pricing_record).execute()
            
            # 3. Process Images
            # Delete old ones first to prevent infinite piling
            images = v.get("images", [])
            if images:
                supabase.table("vehicle_media").delete().eq("vin", vin).execute()
                
            media_batch = []
            for i, img_obj in enumerate(images):
                img_url = img_obj.get("url")
                if img_url:
                    media_batch.append({
                        "vin": vin,
                        "media_type": "Image",
                        "url": img_url,
                        "is_primary": (i == 0)
                    })
            if media_batch:
                supabase.table("vehicle_media").insert(media_batch).execute()
                
            inserted += 1
            if inserted % 250 == 0:
                print(f"Processed {inserted} / {len(unique_vehicles)} so far...")
                
        except Exception as e:
            print(f"Failed to save record {vin} into Supabase - error: {e}")
            pass

    print("--- SCRAPE COMPLETE ---")

if __name__ == "__main__":
    scrape_crm_api()
