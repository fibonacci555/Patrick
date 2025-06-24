import asyncio
from playwright.async_api import async_playwright
import requests
import random
import time

# Parâmetros da API
API_SLUG = "dropship"
API_DEAL_ID = "P3P5D9X5JJ"
API_DEAL_CODE = "SAVE25"
API_POSITION = "2"

def enviar_acao_api():
    base_url = "https://www.wethrift.com/api/submit-action"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.wethrift.com",
        "Referer": "https://www.wethrift.com/dropship"
    }

    used_payload = {
        "slug": API_SLUG,
        "deal_id": API_DEAL_ID,
        "type": "used",
        "value": "1",
        "deal_position": API_POSITION,
        "deal_code": API_DEAL_CODE
    }

    confirm_payload = {
        "slug": API_SLUG,
        "deal_id": API_DEAL_ID,
        "type": "code_working",
        "value": "yes",
        "deal_position": API_POSITION,
        "deal_code": API_DEAL_CODE
    }

    r1 = requests.post(base_url, headers=headers, data=used_payload)
    print("[INFO] Enviada ação 'used':", r1.status_code)

    r2 = requests.post(base_url, headers=headers, data=confirm_payload)
    print("[INFO] Enviada ação 'code_working: yes':", r2.status_code)

async def verificar_e_clicar():
    while True:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto("https://www.wethrift.com/dropship")

            try:
                # Espera pelo botão com o cupão no top-coupon
                await page.wait_for_selector("#top-coupon", timeout=15000)
                cupao = await page.get_attribute("#top-coupon", "title")
                
                print(f"[INFO] Cupão atual: {cupao}")

                if cupao != "SAVE25":
                    print("[INFO] Cupão é diferente. A enviar ações API...")
                    enviar_acao_api()
                else:
                    print("[INFO] Cupão já é SAVE25.")

            except Exception as e:
                print("[ERRO]", e)

           

        delay = random.uniform(180, 300)
        print(f"[INFO] A aguardar {int(delay)} segundos...\n")
        time.sleep(delay)

asyncio.run(verificar_e_clicar())
