import requests
import json
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

# WooCommerce API credentials
consumer_key = "ck_f2926020d6cc2df0f1186f642ba9fac9e949d4fd"
consumer_secret = "cs_4eb13078eb91058f4facd8870c46f3c6e7ca1745"
base_url = "https://store.doctorsstudio.com"

def print_separator():
    print("\n" + "="*80 + "\n")

def test_products():
    endpoint = "/wp-json/wc/v3/products"
    params = {
        "per_page": 100,
        "page": 1,
        "status": "publish"
    }
    
    print(f"Testing endpoint: {base_url}{endpoint}")
    print(f"Parameters: {params}")
    print("-" * 40)
    
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    })
    
    try:
        response = session.get(
            f"{base_url}{endpoint}",
            auth=(consumer_key, consumer_secret),
            params=params
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'Not specified')}")
        
        try:
            data = response.json()
            print("\nResponse is valid JSON")
            
            if isinstance(data, list):
                print(f"Total Products: {len(data)}")
                
                if len(data) > 0:
                    print("\nProduct List:")
                    for product in data:
                        print(f"\nProduct ID: {product.get('id')}")
                        print(f"Name: {product.get('name')}")
                        print(f"Status: {product.get('status')}")
                        print(f"Price: {product.get('price')}")
                        print(f"Regular Price: {product.get('regular_price')}")
                        print(f"SKU: {product.get('sku')}")
                        print("-" * 20)
            else:
                print("\nUnexpected response format:")
                print(json.dumps(data, indent=2))
                
        except json.JSONDecodeError:
            print("Response is not valid JSON")
            print("First 200 characters of response:")
            print(response.text[:200])
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_products()
