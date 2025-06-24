import cloudscraper
import time
import bs4
import requests
import random
from datetime import datetime

scraper = cloudscraper.create_scraper()
base_url = "https://www.wethrift.com/api/submit-action"
params_list = [
    {"slug": "dropship", "deal_id": "P3P5D9X5JJ", "type": "used", "value": "1", "deal_position": "1", "deal_code": "SAVE25"},
    {"slug": "dropship", "deal_id": "P3P5D9X5JJ", "type": "code_working", "value": "yes", "deal_position": "1", "deal_code": "SAVE25"}
]

while True:
    print("[INFO] Enviando ações API...")
    for params in params_list:
        params["t"] = str(int(time.time() * 1000))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[INFO] Request sent at {timestamp}")
        response = scraper.post(base_url, params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        print("---")
        time.sleep(2)
    
    sleep = random.uniform(300, 1000)
    print(f"[INFO] A aguardar {int(sleep)} segundos...\n")
    time.sleep(sleep)