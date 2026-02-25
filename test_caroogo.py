import httpx
import json

def fetch_caroogo():
    # Try fetching a specific vehicle by VIN to see if it has all images
    url = "https://vehicles.caroogo.com/api/v2/Vehicle/KNMAT2MT8LP540784"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    with httpx.Client() as client:
        response = client.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # print all keys
            print("Vehicle Keys:", data.keys())
            if "images" in data:
                print("Images:", len(data["images"]))
            elif "vehicleImages" in data:
                print("vehicleImages:", len(data["vehicleImages"]))
                if data["vehicleImages"]: print(json.dumps(data["vehicleImages"][0], indent=2))
        else:
            print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    fetch_caroogo()
