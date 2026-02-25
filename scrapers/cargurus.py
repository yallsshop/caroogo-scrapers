from .base import BaseScraper
from bs4 import BeautifulSoup
import re
import json

class CarGurusEnricher(BaseScraper):
    def enrich(self, vin):
        print(f"Enriching VIN: {vin} via CarGurus...")
        # CarGurus VIN search redirect
        search_url = f"https://www.cargurus.com/Cars/typeInInventorySearch.action?inventorySearchWidgetType=AUTO&searchId=NONE&zip=40219&distance=50&sourceContext=carGurusHomePageModel&address=Louisville%2C+KY&entitySelectingHelper.selectedEntity=m1&vin={vin}"
        
        try:
            res = self.client.get(search_url, follow_redirects=True)
            print(f"DEBUG: CarGurus landed on {res.url} with status {res.status_code}")
            if res.status_code != 200: 
                print(f"Failed to reach CarGurus for {vin}: {res.status_code}")
                return
            
            soup = BeautifulSoup(res.text, 'html.parser')
            next_data_script = soup.find('script', id='__NEXT_DATA__')
            
            enrichment_data = {}
            
            # 1. Try extracting from __NEXT_DATA__ (most reliable if present)
            if next_data_script:
                try:
                    data = json.loads(next_data_script.string)
                    # Traverse the complex Next.js state tree
                    # Note: Path might change, but usually in props.pageProps.listing
                    listing = data.get('props', {}).get('pageProps', {}).get('listing', {})
                    if listing:
                        enrichment_data["market_rating"] = listing.get('dealRating')
                        enrichment_data["market_value"] = listing.get('expectedPrice')
                        enrichment_data["days_on_market"] = listing.get('daysOnMarket')
                        
                        # Price History
                        history = listing.get('priceHistory', [])
                        for entry in history:
                            # entry typically: {"price": 15000, "date": "2024-02-15"}
                            self.supabase.table("vehicle_price_history").insert({
                                "vin": vin,
                                "price": entry.get('price'),
                                "recorded_at": entry.get('date')
                            }).execute()
                except Exception as e:
                    print(f"Error parsing NEXT_DATA for {vin}: {e}")

            # 2. Fallback to DOM selectors if NEXT_DATA failed or is incomplete
            if not enrichment_data.get("market_rating"):
                rating_elem = soup.find(attrs={"data-testid": "vdp-deal-rating"})
                if rating_elem:
                    enrichment_data["market_rating"] = rating_elem.text.strip()
            
            if not enrichment_data.get("days_on_market"):
                dom_elem = soup.find(text=re.compile(r"days on CarGurus"))
                if dom_elem:
                    match = re.search(r"(\d+)\s+days", dom_elem)
                    if match:
                        enrichment_data["days_on_market"] = int(match.group(1))

            if enrichment_data:
                # Filter out None values
                enrichment_data = {k: v for k, v in enrichment_data.items() if v is not None}
                if enrichment_data:
                    self.supabase.table("vehicles").update(enrichment_data).eq("vin", vin).execute()
                    print(f"Successfully enriched {vin} with {list(enrichment_data.keys())}")
            else:
                print(f"No enrichment data found for {vin}")

        except Exception as e:
            print(f"Critical error enriching {vin}: {e}")
