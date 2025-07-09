import asyncio
import json
import random
import os
import time
from datetime import datetime
import pytz
from urllib.parse import urlparse
import certifi
import cloudscraper
from loguru import logger
import aiofiles
from pathlib import Path

# --- Configuration and Setup ---

CONFIG_DIR = Path(__file__).parent / "configs"
PROXY_FILE = Path(__file__).parent / "valid_proxies.txt"
CONFIG_DIR.mkdir(exist_ok=True)

TZ = "Europe/Lisbon"
ERROR_LOG_FILE = Path(__file__).parent / "error.log"

# --- Global State ---

running_configs = set()
stop_all_requested = False
configs_status = {}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

# --- Helper Functions ---

async def sleep(ms):
    await asyncio.sleep(ms / 1000)

def load_proxies():
    try:
        if not PROXY_FILE.exists():
            logger.error("Proxy file valid_proxies.txt not found.")
            return []
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and ":" in line]
    except Exception as e:
        logger.error(f"Error loading proxies: {e}")
        return []

def get_random_proxy(proxies):
    return random.choice(proxies) if proxies else None

def create_progress_bar(processed, total, bar_length=20):
    if total == 0:
        return f"|{'─' * bar_length}|"
    ratio = processed / total
    filled = round(bar_length * ratio)
    return f"|{'█'*filled}{'─'*(bar_length-filled)}|"

async def log_error(config_id, message):
    timestamp = datetime.now(pytz.timezone(TZ)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiofiles.open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(f"[{timestamp}] [Config: {config_id}] {message}\n")

# --- Config Management ---

def load_configs():
    configs = []
    for file in CONFIG_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                configs.append(json.load(f))
        except Exception as e:
            logger.error(f"Error loading config file {file}: {e}")
    return configs

def save_config(config):
    config_id = config.get("config_id", str(int(time.time())))
    config["config_id"] = config_id
    with open(CONFIG_DIR / f"{config_id}.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_id

def delete_config(config_id):
    p = CONFIG_DIR / f"{config_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False

# --- Cloudsraper Setup ---

tmp_scraper = cloudscraper.create_scraper()
# Configura bundle de CAs atualizado
tmp_scraper.verify = certifi.where()
SCRAPER = tmp_scraper

# --- Dynamic Dashboard Rendering ---

async def render_dashboard():
    while not stop_all_requested:
        now = datetime.now(pytz.timezone(TZ)).strftime('%H:%M:%S')
        print("\033[H\033[J", end="")
        print(f"Wethrift API Sender    Active Configs: {len(running_configs)}    Time: {now}")
        print("-"*130)
        if not configs_status:
            print("No configurations are currently running.")
        else:
            for st in configs_status.values():
                total = st['total']
                done = st['successful'] + st['failed']
                bar = create_progress_bar(done, total)
                progress = f"{done}/{total}".ljust(7)
                success = f"Success: {st['successful']}".ljust(12)
                resp = st.get('last_response', 'N/A')[:50].ljust(50)
                line = (
                    f"▶ ID: {st['id'].ljust(15)} | {bar} {progress} | {success} | "
                    f"Status: {st['status'].ljust(10)} | Response: {resp}"
                )
                if st['status'] == 'Waiting':
                    cd = max(0, round((st['next_run_end_time'] - time.time())/1000))
                    line += f" | Next run in: {cd}s"
                print(line)
        print("-"*130)
        if stop_all_requested:
            print("Stopping all configurations... please wait.")
        await asyncio.sleep(0.2)

# --- Main Work ---

async def run_script(config):
    config_id = config.get('config_id')
    base_url = config.get('base_url', 'https://www.wethrift.com/api/submit-action')
    slug = config.get('slug', 'scraper')
    min_sleep = 1500
    max_sleep = 3000
    deals = config.get('deals', [])

    # Build store URL
    try:
        p = urlparse(base_url)
        store_url = f"{p.scheme}://{p.netloc}/{slug}"
    except ValueError:
        store_url = 'Invalid base_url'

    proxies = load_proxies()
    if not proxies:
        await log_error(config_id, 'No valid proxies found. Running without proxies.')

    # Prepare params list
    params_list = []
    for pos in range(1, 11):
        for d in deals:
            for t, v in [('used', '1'), ('code_working', 'yes')]:
                params_list.append({
                    'slug': slug,
                    'deal_id': d['deal_id'],
                    'type': t,
                    'value': v,
                    'deal_position': str(pos),
                    'deal_code': d['deal_code'],
                })

    configs_status[config_id] = {
        'id': config_id,
        'status': 'Starting...',
        'total': len(params_list),
        'successful': 0,
        'failed': 0,
        'next_run_end_time': 0,
        'url': store_url,
        'last_response': 'N/A',
    }

    loop = asyncio.get_event_loop()

    while config_id in running_configs and not stop_all_requested:
        st = configs_status[config_id]
        st.update({'status': 'Running', 'successful': 0, 'failed': 0})

        for params in params_list:
            if config_id not in running_configs or stop_all_requested:
                break
            params['t'] = str(int(time.time()))
            proxy = get_random_proxy(proxies)
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.wethrift.com/',
                'Origin': 'https://www.wethrift.com',
                'X-Requested-With': 'XMLHttpRequest',
                'Connection': 'keep-alive',
            }

            try:
                # Execute cloudscraper POST in executor to avoid blocking
                def do_request():
                    proxies_dict = {
                        'http': f"http://{proxy}",
                        'https': f"http://{proxy}"
                    } if proxy else None
                    return SCRAPER.post(
                        base_url,
                        params=params,
                        headers=headers,
                        proxies=proxies_dict,
                        timeout=15
                    )
                response = await loop.run_in_executor(None, do_request)
                code = response.status_code
                try:
                    data = response.json()
                    response_text = 'Success' if data.get('success') else f"Error: {data.get('message','Unknown')}"
                except Exception:
                    response_text = f"Status {code}"
                full = f"{code} {response_text}"
                print(full)
                st['last_response'] = full
                if code == 200 and data.get('success'):
                    st['successful'] += 1
                else:
                    st['failed'] += 1
                    await log_error(config_id, f"Request failed: {full}")
                    if code == 403:
                        await log_error(config_id, f"↳ 403 Forbidden on params: {params}")
            except Exception as e:
                err = f"Error: {e}"
                st['failed'] += 1
                st['last_response'] = err
                await log_error(config_id, err)

            await asyncio.sleep(2)

        if config_id not in running_configs or stop_all_requested:
            break

        sleep_time = random.uniform(min_sleep, max_sleep)
        st['status'] = 'Waiting'
        st['next_run_end_time'] = time.time() + sleep_time
        await asyncio.sleep(sleep_time)

    final_state = 'Stopped' if stop_all_requested else 'Finished'
    if config_id in configs_status:
        configs_status[config_id]['status'] = final_state
    running_configs.discard(config_id)

# --- Main Execution ---

async def main():
    logger.info('Loading configurations...')
    configs = load_configs()
    if not configs:
        logger.info("No configurations found in the 'configs' directory.")
        return

    dashboard_task = asyncio.create_task(render_dashboard())

    tasks = []
    for config in configs:
        running_configs.add(config['config_id'])
        store_url = 'N/A'
        if config.get('slug'):
            try:
                p = urlparse(config.get('base_url', 'https://www.wethrift.com/api/submit-action'))
                store_url = f"{p.scheme}://{p.netloc}/{config['slug']}"
            except ValueError:
                store_url = 'Invalid base_url'
        configs_status[config['config_id']] = {
            'id': config['config_id'],
            'status': 'Queued',
            'total': 0,
            'successful': 0,
            'failed': 0,
            'next_run_end_time': 0,
            'url': store_url,
            'last_response': 'N/A',
        }
        tasks.append(run_script(config))

    await asyncio.gather(*tasks)
    dashboard_task.cancel()
    print("[H[J", end="")  # Clear console
    print("All configurations have finished or been stopped.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Graceful shutdown requested. Stopping all configs...")
        stop_all_requested = True
        asyncio.run(asyncio.sleep(1))  # Allow tasks to finish
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
