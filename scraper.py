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

def init_dealership(name, website, platform):
    response = supabase.table("dealerships").select("*").eq("name", name).execute()
    if response.data:
        return response.data[0]["id"]
    else:
        new_dealer = {
            "name": name,
            "website_url": website,
            "platform": platform
        }
        res = supabase.table("dealerships").insert(new_dealer).execute()
        return res.data[0]["id"]

def scrape_caroogo():
    print("Starting Caroogo API Scrape...")
    dealer_id = init_dealership("Caroogo", "https://caroogo.com", "Caroogo")
    
    url = "https://vehicles.caroogo.com/api/v2/Vehicle/VehicleSearch"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    current_page = 1
    page_size = 50
    total_scraped = 0
    
    with httpx.Client() as client:
        while True:
            payload = {
                "currentPage": current_page,
                "pageSize": page_size,
                "sortBy": "Year",
                "sortDirection": "Desc"
            }
            res = client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                print(f"Failed to fetch Caroogo page {current_page}")
                break
                
            data = res.json()
            vehicles = data.get("vehicles", [])
            if not vehicles:
                break
                
            for v in vehicles:
                vin = v.get("vin")
                if not vin: continue
                
                # Try to get condition and stock number from vehicleDealers array
                dealers = v.get("vehicleDealers", [{}])
                primary_dealer_info = dealers[0] if dealers else {}
                condition_raw = primary_dealer_info.get("vehicleCondition", "Used")
                condition = "Used"
                if "new" in condition_raw.lower(): condition = "New"
                elif "cpo" in condition_raw.lower() or "certified" in condition_raw.lower(): condition = "CPO"

                stock_number = primary_dealer_info.get("stockNumber", "")
                
                vehicle_data = {
                    "vin": vin,
                    "dealership_id": dealer_id,
                    "stock_number": stock_number,
                    "condition": condition,
                    "year": v.get("modelYear"),
                    "make": v.get("make"),
                    "model": v.get("model"),
                    "trim": v.get("trim"),
                    "body_style": v.get("body"),
                    "exterior_color": v.get("exteriorColor"),
                    "interior_color": v.get("interiorColor"),
                    "transmission": v.get("transmission"),
                    "drivetrain": v.get("driveType"),
                    "engine_description": v.get("engine"),
                    "doors": v.get("numberOfDoors"),
                    "mileage": v.get("mileage"),
                    "mpg_city": v.get("highCityFuelEconomy"),
                    "mpg_hwy": v.get("highHighwayFuelEconomy"),
                    "status": "In Stock"  # Default assumption for API results
                }
                
                try:
                    # Upsert vehicle
                    supabase.table("vehicles").upsert(vehicle_data).execute()
                    
                    # Insert Pricing
                    pricing_data = {
                        "vin": vin,
                        "msrp": v.get("currentMsrpPrice", 0),
                        "retail_price": v.get("currentVendorPrice", 0),
                        "internet_price": v.get("currentInternetPrice", 0),
                        "dealer_discount": 0
                    }
                    supabase.table("vehicle_pricing").insert(pricing_data).execute()
                    
                    # Media - Caroogo primary image
                    primary_img = v.get("primaryImage")
                    if primary_img:
                        # Prevent duplicate media on re-runs by deleting old media for this VIN first
                        supabase.table("vehicle_media").delete().eq("vin", vin).execute()
                        
                        media_data = {
                            "vin": vin,
                            "media_type": "Image",
                            "url": primary_img,
                            "is_primary": True
                        }
                        supabase.table("vehicle_media").insert(media_data).execute()
                except Exception as e:
                    print(f"Error on VIN {vin}: {e}")
                    import traceback
                    traceback.print_exc()

            total_scraped += len(vehicles)
            print(f"Scraped {total_scraped} vehicles from Caroogo...")
            
            # Move to next page
            current_page += 1

def scrape_bill_collins():
    print("Starting Bill Collins Ford API Scrape...")
    dealer_id = init_dealership("Bill Collins Ford", "https://billcollinsford.net", "DealerOn")
    
    # DealerOn cosmos API endpoints usually follow this pattern. We're picking up 96 vehicles per request.
    url = "https://www.billcollinsford.net/api/vhcliaa/vehicle-pages/cosmos/srp/vehicles/25727/2586115"
    headers = {
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    page = 1
    total_scraped = 0
    
    with httpx.Client() as client:
        while True:
            params = {
                "host": "www.billcollinsford.net",
                "baseFilter": "dHlwZT0nbic=", # Usually 'type=n' (new) base64 encoded
                "displayCardsShown": "NaN",
                "pn": page * 48 # Pagination parameter, picking 48
            }
            
            res = client.get(url, params=params, headers=headers)
            if res.status_code != 200:
                print(f"Failed to fetch Bill Collins page {page}: {res.status_code}")
                break
                
            data = res.json()
            cards = data.get("DisplayCards", [])
            
            # DealerOn returns all accumulated cards sometimes, or just the next chunk. Let's just process what we get and handle duplicates via upsert.
            if not cards:
                break
                
            new_this_batch = 0
            vins_this_page = 0
            for card in cards:
                if card.get("IsAdCard"): continue
                
                v_data = card.get("VehicleCard", {})
                if not v_data: continue
                
                vin = v_data.get("Vin")
                # Sometimes vin is weirdly nested or hidden directly in the VehicleCard, let's grab it from the CompareModel if not present
                if not vin:
                    comp_model = v_data.get("VehicleCompareModel", {})
                    vin = comp_model.get("Vin")
                
                if not vin: continue
                vins_this_page += 1
                
                make_model_str = v_data.get("VehicleMakeAndModel", "").strip()
                make, *model_parts = make_model_str.split(" ", 1)
                model = model_parts[0] if model_parts else ""
                
                # Try parsing price
                pricing = v_data.get("PricingModel", {})
                internet_price = 0
                msrp = 0
                if pricing:
                    try:
                        price_str = pricing.get("FinalPrice", "0").replace("$", "").replace(",", "")
                        internet_price = float(price_str) if price_str.replace(".","").isdigit() else 0
                        msrp_str = pricing.get("Msrp", "0") if isinstance(pricing.get("Msrp"), str) else "0"
                        msrp = float(msrp_str.replace("$", "").replace(",", "")) if msrp_str.replace(".","").isdigit() else 0
                    except: pass
                
                # Fallback TaggingPrice
                if not internet_price:
                    tp = v_data.get("TaggingPrice", "0")
                    internet_price = float(tp) if tp.isdigit() else 0

                vehicle_record = {
                    "vin": vin,
                    "dealership_id": dealer_id,
                    "stock_number": v_data.get("StockNumber"),
                    "condition": v_data.get("VehicleCondition", "New"),
                    "year": 2024, # Have to parse it from somewhere, maybe title? 
                    "make": make,
                    "model": model,
                    "trim": v_data.get("Trim"),
                    "body_style": v_data.get("BodyStyle"),
                    "exterior_color": v_data.get("ExteriorColor"),
                    "interior_color": v_data.get("InteriorColor"),
                    "transmission": v_data.get("Transmission"),
                    "drivetrain": v_data.get("DriveType"),
                    "engine_description": v_data.get("Engine"),
                    "doors": 4, 
                    "mileage": 0,
                    "status": "In Stock"
                }
                
                try:
                    # Basic extraction from VehicleNameHtmlEncoded (e.g. 2025 Ford Maverick XL)
                    name_html = v_data.get("VehicleImageCarouselModel", {}).get("VehicleNameHtmlEncoded", "")
                    if name_html:
                        match = re.search(r"20\d{2}", name_html)
                        if match: vehicle_record["year"] = int(match.group())
                except: pass
                
                try:
                    # New Vehicle Make filtering
                    condition = v_data.get("VehicleCondition", "New")
                    if condition.lower() == "new" and "ford" not in make.lower():
                        continue # Skip New vehicles that aren't Fords, to get them from their respective sites

                    supabase.table("vehicles").upsert(vehicle_record).execute()
                    
                    price_record = {
                        "vin": vin,
                        "msrp": msrp,
                        "internet_price": internet_price,
                        "currency": "USD"
                    }
                    supabase.table("vehicle_pricing").insert(price_record).execute()
                    
                    # Process images
                    carousel = v_data.get("VehicleImageCarouselModel", {})
                    photos = carousel.get("PhotoListDetailed", [])
                    if photos:
                        # Prevent duplicates by clearing existing media for this VIN
                        supabase.table("vehicle_media").delete().eq("vin", vin).execute()
                        
                    is_p = True
                    for p in photos:
                        img_url = p.get("TargetUrl")
                        if img_url:
                            if not img_url.startswith("http"): img_url = "https://www.billcollinsford.net" + img_url
                            supabase.table("vehicle_media").insert({
                                "vin": vin,
                                "media_type": "Image",
                                "url": img_url,
                                "is_primary": is_p
                            }).execute()
                            is_p = False
                    new_this_batch += 1
                except Exception as e:
                    pass
            
            if vins_this_page == 0:
                print("No vehicles with VINs found. Stopping Bill Collins iteration.")
                break

            total_scraped += new_this_batch
            print(f"Scraped {total_scraped} vehicles from Bill Collins Ford...")
            
            # Increment page for the next loop
            page += 1

if __name__ == "__main__":
    scrape_caroogo()
    scrape_bill_collins()
