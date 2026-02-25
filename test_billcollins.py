import httpx
from bs4 import BeautifulSoup
import re

def test_billcollins():
    url = "https://www.billcollinsford.net/new-inventory/index.htm"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    with httpx.Client(follow_redirects=True) as client:
        res = client.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Look for the internal API calls or the dealer ID variables in the source script tags
        script_content = res.text
        m = re.search(r'[\'"]siteId[\'"]\s*:\s*[\'"]([^\'"]+)[\'"]', script_content)
        m2 = re.search(r'[\'"]accountId[\'"]\s*:\s*[\'"]([^\'"]+)[\'"]', script_content)
        print("Site ID:", m.group(1) if m else "None")
        print("Account ID:", m2.group(1) if m2 else "None")

if __name__ == "__main__":
    test_billcollins()
