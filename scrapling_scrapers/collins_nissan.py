import re
import json
from scrapling.fetchers import Fetcher
from .base import BaseScraper


class CollinsNissanScraper(BaseScraper):
    """
    Scrapling-based version of scrapers/collins_nissan.py.
    Uses Fetcher (plain HTTP) + Scrapling CSS selectors instead of httpx + BeautifulSoup.
    """

    BASE_URL = "https://www.collinsnissan.com"

    def scrape(self):
        print(f"Starting {self.dealer_name} Scrape (Scrapling version)...")
        print(f"DEBUG: Using Dealership ID: {self.dealer_id}")

        fetcher = Fetcher()
        try:
            page = fetcher.get(f"{self.BASE_URL}/inventory/new", follow_redirects=True)
        except Exception as e:
            print(f"Failed to load inventory page: {e}")
            return

        # Collect model links containing /inventory/new/nissan/
        model_links = list({
            a.attrib.get("href")
            for a in page.find_all("a")
            if "/inventory/new/nissan/" in (a.attrib.get("href") or "")
        })

        print(f"Found {len(model_links)} models to scrape: {model_links}")

        for link in model_links:
            target_url = link if link.startswith("http") else f"{self.BASE_URL}{link}"
            self._scrape_model_page(fetcher, target_url)

    def _scrape_model_page(self, fetcher: Fetcher, url: str):
        print(f"Scraping model page: {url}")
        try:
            page = fetcher.get(url, follow_redirects=True)
        except Exception as e:
            print(f"Failed to load model page {url}: {e}")
            return

        vehicles = page.css(".si-vehicle-box")
        print(f"Found {len(vehicles)} vehicles on page. Starting iteration...")

        for i, v in enumerate(vehicles):
            print(f"DEBUG: Processing vehicle element {i + 1}")
            try:
                # Broadened selector: a with class containing "name" or "title", fallback h2/h3
                _matches = v.css('a[class*="name"], a[class*="title"]')
                title_el = (_matches[0] if _matches else None) or v.find("h2") or v.find("h3")
                print(f"DEBUG: Title element found: {bool(title_el)}")
                if not title_el:
                    continue

                name = title_el.text
                vin = v.attrib.get("data-vin") or self._extract_vin(v)
                print(f"DEBUG: Found VIN {vin} for {name}")
                if not vin:
                    continue

                year = 2025
                year_match = re.search(r"(20\d{2})", name)
                if year_match:
                    year = int(year_match.group(1))

                vehicle_record = {
                    "vin": vin,
                    "dealership_id": self.dealer_id,
                    "year": year,
                    "make": "Nissan",
                    "model": name.replace(str(year), "").strip().split(" ")[0],
                    "status": "In Stock",
                }

                # Price
                _price_results = v.css(".si-vehicle-price")
                price_box = _price_results[0] if _price_results else None
                if price_box:
                    price_text = price_box.text.replace("$", "").replace(",", "").strip()
                    try:
                        price = float(price_text)
                        self.update_pricing(vin, {"internet_price": price})
                    except ValueError:
                        pass

                result = self.upsert_vehicle(vehicle_record)
                print(f"Upserted: {year} {vehicle_record['model']} ({vin}) - Result: {result}")

            except Exception as e:
                print(f"Error parsing Nissan vehicle: {e}")

    @staticmethod
    def _extract_vin(element) -> str | None:
        """Regex fallback VIN extraction from element HTML."""
        match = re.search(r"[A-HJ-NPR-Z0-9]{17}", element.html_content)
        return match.group(0) if match else None
