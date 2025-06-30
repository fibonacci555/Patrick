import threading
import queue
import requests

q = queue.Queue()

valid_proxies = []
with open('proxies.txt', 'r') as f:
    proxies = f.read().split('\n')
    for proxy in proxies:
        q.put(proxy)
        
        
        
def check_proxy():
    global q
    while not q.empty():
        proxy = q.get()
        try:
            response = requests.get('https://ipinfo.io/json', proxies={'http': proxy, 'https': proxy})
        except:
            continue
        if response.status_code == 200:
            
            print(proxy)
        
        
for _ in range(10):
    threading.Thread(target=check_proxy).start()