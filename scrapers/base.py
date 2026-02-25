import httpx
from supabase import Client

class BaseScraper:
    def __init__(self, supabase: Client, dealer_id: str, dealer_name: str):
        self.supabase = supabase
        self.dealer_id = dealer_id
        self.dealer_name = dealer_name
        self.client = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)

    def upsert_vehicle(self, vehicle_data: dict):
        try:
            # Sync scraped_at
            import datetime
            vehicle_data["scraped_at"] = datetime.datetime.now().isoformat()
            
            # Use on_conflict to ensure VIN is the key for upsert
            result = self.supabase.table("vehicles").upsert(vehicle_data, on_conflict="vin").execute()
            return result
        except Exception as e:
            print(f"Error upserting vehicle {vehicle_data.get('vin')}: {e}")

    def update_pricing(self, vin: str, pricing_data: dict):
        try:
            pricing_data["vin"] = vin
            self.supabase.table("vehicle_pricing").insert(pricing_data).execute()
        except Exception as e:
            print(f"Error updating pricing for {vin}: {e}")

    def update_media(self, vin: str, media_list: list):
        try:
            # Clear old media to avoid duplicates
            self.supabase.table("vehicle_media").delete().eq("vin", vin).execute()
            if media_list:
                self.supabase.table("vehicle_media").insert(media_list).execute()
        except Exception as e:
            print(f"Error updating media for {vin}: {e}")
