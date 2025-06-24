import asyncio
import random
from playwright.async_api import async_playwright

async def clicar_cupao_se_necessario():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # True = não abre janela
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.wethrift.com/dropship", wait_until="networkidle")

        try:
            # Espera pelo cupão no top-coupon
            await page.wait_for_selector('#top-coupon button[title]', timeout=15000)
            cupao_atual = await page.get_attribute('#top-coupon button[title]', 'title')
            print(f"[INFO] Cupão atual: {cupao_atual}")

            if cupao_atual != "SAVE25":
                print("[INFO] Cupão diferente de SAVE25 — a iniciar sequência de cliques...")

                # 1. Clicar no botão SAVE25
                await page.click('button[title="SAVE25"]')
                print("[OK] Clicado em SAVE25")

                # 2. Clicar no botão "Yes"
                await page.wait_for_selector('//div[@alt="Coupon worked"]//span[text()="Yes"]', timeout=10000)
                await page.click('//div[@alt="Coupon worked"]//span[text()="Yes"]')
                print("[OK] Clicado em Yes")

                # 3. Clicar em "No thanks."
                await page.wait_for_selector('//span[text()="No thanks."]', timeout=10000)
                await page.click('//span[text()="No thanks."]')
                print("[OK] Clicado em No thanks.")

                # 4. Clicar em "Close"
                await page.wait_for_selector('//div[text()="Close"]', timeout=10000)
                await page.click('//div[text()="Close"]')
                print("[OK] Clicado em Close")

            else:
                print("[INFO] Cupão já é SAVE25 — não é necessário clicar.")

        except Exception as e:
            print("[ERRO] Algo correu mal:", e)

        await browser.close()

# Loop que repete a cada 3 a 5 minutos
async def loop_com_intervalos():
    while True:
        await clicar_cupao_se_necessario()
        tempo = random.uniform(180, 300)
        print(f"[INFO] A aguardar {int(tempo)} segundos para próxima verificação...\n")
        await asyncio.sleep(tempo)

# Correr
asyncio.run(loop_com_intervalos())
