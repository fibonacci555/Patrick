import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def verificar_e_clicar():
    options = webdriver.ChromeOptions()
    #options.add_argument("--headless")  # Corre sem abrir janela
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get("https://www.wethrift.com/dropship")

        # Espera o elemento do cupão principal
        top_coupon = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "top-coupon"))
        )

        current_coupon = top_coupon.find_element(By.CSS_SELECTOR, 'button[title]').get_attribute("title").strip()
        print(f"[INFO] Cupão atual: {current_coupon}")

        if current_coupon != "SAVE25":
            print("[INFO] Cupão diferente de SAVE25. A clicar...")

            # Clica no botão SAVE25
            btn_save25 = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[title="SAVE25"]'))
            )
            btn_save25.click()
            print("[INFO] Botão SAVE25 clicado.")
            time.sleep(4)

            # Clica em "Yes"
            btn_yes = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@alt="Coupon worked"]//span[text()="Yes"]'))
            )
            btn_yes.click()
            print("[INFO] Botão YES clicado.")
            time.sleep(4)

            # Clica em "No thanks."
            no_thanks = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//span[text()="No thanks."]'))
            )
            no_thanks.click()
            print("[INFO] Botão 'No thanks.' clicado.")
            time.sleep(4)

            # Clica em "Close"
            btn_close = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[text()="Close"]'))
            )
            btn_close.click()
            print("[INFO] Janela fechada com 'Close'.")
            time.sleep(4)

        else:
            print("[INFO] Cupão já é SAVE25. Nenhuma ação tomada.")

    except Exception as e:
        print(f"[ERRO] Ocorreu um erro: {e}")

    finally:
        driver.quit()

# Loop contínuo a cada 3–5 minutos
while True:
    verificar_e_clicar()
    tempo_espera = random.uniform(180, 300)
    print(f"[INFO] A aguardar {int(tempo_espera)} segundos até à próxima verificação...\n")
    time.sleep(tempo_espera)
