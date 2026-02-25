from .base import BaseScraper
from bs4 import BeautifulSoup
import re
import json

class CollinsNissanScraper(BaseScraper):
    def scrape(self):
        print(f"Starting {self.dealer_name} Scrape (Model Discovery)...")
        print(f"DEBUG: Using Dealership ID: {self.dealer_id}")
        base_url = "https://www.collinsnissan.com"
        res = self.client.get(f"{base_url}/inventory/new", follow_redirects=True)
        if res.status_code != 200: 
            print(f"Failed to load inventory page: {res.status_code}")
            return
        
        soup = BeautifulSoup(res.text, 'html.parser')
        model_links = []
        for a in soup.find_all('a', href=True):
            if '/inventory/new/nissan/' in a['href']:
                model_links.append(a['href'])
        
        model_links = list(set(model_links))
        print(f"Found {len(model_links)} models to scrape: {model_links}")

        for link in model_links:
            target_url = link if link.startswith("http") else f"{base_url}{link}"
            self.scrape_model_page(target_url)

    def scrape_model_page(self, url):
        print(f"Scraping model page: {url}")
        res = self.client.get(url)
        if res.status_code != 200:
            print(f"Failed to load model page: {url}")
            return
        
        soup = BeautifulSoup(res.text, 'html.parser')
        vehicles = soup.find_all(class_='si-vehicle-box')
        print(f"Found {len(vehicles)} vehicles on page. Starting iteration...")
        
        for i, v in enumerate(vehicles):
            print(f"DEBUG: Processing vehicle element {i+1}")
            try:
                # Broadening selector for title/name
                title_link = v.find('a', class_=re.compile(r'name|title')) or v.find('h2') or v.find('h3')
                print(f"DEBUG: Title element found: {bool(title_link)}")
                if not title_link: continue
                
                name = title_link.text.strip() # e.g. 2025 Nissan Rogue S
                vin = v.get('data-vin') or self.extract_vin(v)
                print(f"DEBUG: Found VIN {vin} for {name}")
                if not vin: continue

                # Parse Year and Model from name
                year = 2025
                year_match = re.search(r'(20\d{2})', name)
                if year_match:
                    year = int(year_match.group(1))

                vehicle_record = {
                    "vin": vin,
                    "dealership_id": self.dealer_id,
                    "year": year,
                    "make": "Nissan",
                    "model": name.replace(str(year), "").strip().split(' ')[0],
                    "status": "In Stock"
                }

                # Try to get price
                price_box = v.find(class_='si-vehicle-price')
                if price_box:
                    price_text = price_box.text.replace('$', '').replace(',', '').strip()
                    try:
                        price = float(price_text)
                        self.update_pricing(vin, {"internet_price": price})
                    except: pass

                result = self.upsert_vehicle(vehicle_record)
                print(f"Upserted: {year} {vehicle_record['model']} ({vin}) - Result: {result}")
            except Exception as e:
                print(f"Error parsing Nissan vehicle: {e}")

    def extract_vin(self, element):
        text = str(element)
        match = re.search(r'[A-HJ-NPR-Z0-9]{17}', text)
        return match.group(0) if match else None
