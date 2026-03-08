import re
import json
from scrapling.fetchers import StealthyFetcher
from .base import BaseScraper


class CarGurusEnricher(BaseScraper):
    """
    Scrapling-based version of scrapers/cargurus.py.
    Uses StealthyFetcher instead of httpx to better handle CarGurus anti-bot protection.
    """

    SEARCH_URL = (
        "https://www.cargurus.com/Cars/typeInInventorySearch.action"
        "?inventorySearchWidgetType=AUTO&searchId=NONE&zip=40219&distance=50"
        "&sourceContext=carGurusHomePageModel&address=Louisville%2C+KY"
        "&entitySelectingHelper.selectedEntity=m1&vin={vin}"
    )

    def enrich(self, vin: str):
        print(f"Enriching VIN: {vin} via CarGurus (Scrapling version)...")
        search_url = self.SEARCH_URL.format(vin=vin)

        try:
            fetcher = StealthyFetcher(auto_match=False)
            page = fetcher.fetch(search_url, headless=True, network_idle=True)

            print(f"DEBUG: CarGurus status {page.status}")
            if page.status == 404:
                print(f"Failed to reach CarGurus for {vin}: {page.status}")
                return

            enrichment_data = {}

            # 1. Try __NEXT_DATA__ JSON (most reliable)
            next_data_el = page.find("script", id="__NEXT_DATA__")
            if next_data_el:
                try:
                    data = json.loads(next_data_el.text)
                    listing = data.get("props", {}).get("pageProps", {}).get("listing", {})
                    if listing:
                        enrichment_data["market_rating"] = listing.get("dealRating")
                        enrichment_data["market_value"] = listing.get("expectedPrice")
                        enrichment_data["days_on_market"] = listing.get("daysOnMarket")

                        for entry in listing.get("priceHistory", []):
                            self.supabase.table("vehicle_price_history").insert({
                                "vin": vin,
                                "price": entry.get("price"),
                                "recorded_at": entry.get("date"),
                            }).execute()
                except Exception as e:
                    print(f"Error parsing NEXT_DATA for {vin}: {e}")

            # 2. DOM fallbacks if NEXT_DATA missing or incomplete
            if not enrichment_data.get("market_rating"):
                rating_el = page.css_first('[data-testid="vdp-deal-rating"]')
                if rating_el:
                    enrichment_data["market_rating"] = rating_el.text

            if not enrichment_data.get("days_on_market"):
                # XPath text search for "days on CarGurus"
                matches = page.xpath('//*[contains(text(), "days on CarGurus")]')
                if matches:
                    dom_text = matches[0].text
                    match = re.search(r"(\d+)\s+days", dom_text)
                    if match:
                        enrichment_data["days_on_market"] = int(match.group(1))

            if enrichment_data:
                enrichment_data = {k: v for k, v in enrichment_data.items() if v is not None}
                if enrichment_data:
                    self.supabase.table("vehicles").update(enrichment_data).eq("vin", vin).execute()
                    print(f"Successfully enriched {vin} with {list(enrichment_data.keys())}")
            else:
                print(f"No enrichment data found for {vin}")

        except Exception as e:
            print(f"Critical error enriching {vin}: {e}")
