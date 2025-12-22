import threading
import queue
import requests

INPUT_FILE = "proxies.txt"
OUTPUT_FILE = "proxies.txt"  # sobrescreve o mesmo ficheiro
THREADS = 50
TIMEOUT = 10

q = queue.Queue()
valid_proxies = []
lock = threading.Lock()

# carregar proxies
with open(INPUT_FILE, "r") as f:
    for proxy in f.read().splitlines():
        if proxy.strip():
            q.put(proxy.strip())

def check_proxy():
    while True:
        try:
            proxy = q.get_nowait()
        except queue.Empty:
            break

        try:
            r = requests.get(
                "https://ipinfo.io/json",
                proxies={
                    "http": f"http://{proxy}",
                    "https": f"http://{proxy}",
                },
                timeout=TIMEOUT
            )

            if r.status_code == 200:
                with lock:
                    valid_proxies.append(proxy)
                    print(f"[VALID] {proxy}")

        except requests.RequestException:
            pass
        finally:
            q.task_done()

# iniciar threads
threads = []
for _ in range(THREADS):
    t = threading.Thread(target=check_proxy)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

# guardar apenas proxies válidos
with open(OUTPUT_FILE, "w") as f:
    f.write("\n".join(valid_proxies))

print(f"\nDone. {len(valid_proxies)} proxies válidos guardados.")
