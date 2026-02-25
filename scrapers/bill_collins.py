from .base import BaseScraper
import re

class BillCollinsScraper(BaseScraper):
    def scrape(self):
        print(f"Starting {self.dealer_name} Scrape (DealerOn API)...")
        # DealerOn Cosmos SRP API
        url = "https://www.billcollinsford.net/api/vhcliaa/vehicle-pages/cosmos/srp/vehicles/25727/2586115"
        
        page = 0
        seen_vins = set()
        while True:
            params = {
                "host": "www.billcollinsford.net",
                "baseFilter": "dHlwZT0nbic=", # New inventory
                "pn": page * 48
            }
            
            res = self.client.get(url, params=params)
            if res.status_code != 200: break
            
            data = res.json()
            cards = data.get("DisplayCards", [])
            if not cards: break
            
            vins_this_page = 0
            for card in cards:
                if card.get("IsAdCard"): continue
                v_card = card.get("VehicleCard", {})
                vin = v_card.get("Vin")
                if not vin: continue
                
                vins_this_page += 1
                if vin in seen_vins:
                    print(f"Detected loop with VIN {vin}, stopping scrape.")
                    return
                seen_vins.add(vin)
            
            if vins_this_page == 0:
                print("No vehicles with VINs found on this page. Stopping scrape.")
                break


                # Basic Vehicle Data
                vehicle_record = {
                    "vin": vin,
                    "dealership_id": self.dealer_id,
                    "stock_number": v_card.get("StockNumber"),
                    "condition": v_card.get("VehicleCondition", "New"),
                    "make": v_card.get("Make"),
                    "model": v_card.get("Model"),
                    "trim": v_card.get("Trim"),
                    "body_style": v_card.get("BodyStyle"),
                    "exterior_color": v_card.get("ExteriorColor"),
                    "interior_color": v_card.get("InteriorColor"),
                    "transmission": v_card.get("Transmission"),
                    "drivetrain": v_card.get("DriveType"),
                    "engine_description": v_card.get("Engine"),
                    "mileage": v_card.get("Odometer", 0),
                    "description": v_card.get("VehicleFeaturesModel", {}).get("InvComments", ""),
                    "status": "In Stock"
                }

                # Parse Year from Name if missing
                name = v_card.get("VehicleNameHtmlEncoded", "")
                year_match = re.search(r"20\d{2}", name)
                if year_match:
                    vehicle_record["year"] = int(year_match.group())

                self.upsert_vehicle(vehicle_record)

                # Pricing
                pricing_model = v_card.get("PricingModel", {})
                msrp = pricing_model.get("Msrp", 0)
                selling_price = v_card.get("TaggingPrice", 0)
                
                self.update_pricing(vin, {
                    "msrp": msrp,
                    "internet_price": selling_price,
                    "dealer_discount": msrp - selling_price if msrp and selling_price else 0
                })

                # Media
                photos = v_card.get("VehicleImageCarouselModel", {}).get("PhotoListDetailed", [])
                media_batch = []
                for i, p in enumerate(photos):
                    img_url = p.get("TargetUrl")
                    if img_url:
                        if not img_url.startswith("http"):
                            img_url = "https://www.billcollinsford.net" + img_url
                        media_batch.append({
                            "vin": vin,
                            "media_type": "Image",
                            "url": img_url,
                            "is_primary": (i == 0)
                        })
                self.update_media(vin, media_batch)

            page += 1
            print(f"Page {page} complete...")
