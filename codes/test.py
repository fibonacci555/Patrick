import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import logging
from urllib.parse import urlparse, parse_qs

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver():
    """Set up Chrome WebDriver with network interception capabilities."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
    options.add_experimental_option('prefs', {'profile.default_content_setting_values.notifications': 2})  # Disable notifications
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Enable Network monitoring
    driver.execute_cdp_cmd('Network.enable', {})
    return driver

def capture_network_requests(driver, button_text, timeout=10):
    """Capture network requests triggered by clicking a button with specified text."""
    network_requests = []
    
    def request_will_be_sent(params):
        """Callback for network request."""
        request = params.get('request', {})
        network_requests.append({
            'url': request.get('url', ''),
            'method': request.get('method', ''),
            'headers': request.get('headers', {}),
            'postData': request.get('postData', ''),
            'timestamp': params.get('timestamp', 0)
        })
    
    # Set up network listener
    driver.execute_cdp_cmd('Network.requestWillBeSent', {})
    driver.execute_cdp_cmd('Network.setRequestIntercepted', {'callback': request_will_be_sent})
    
    try:
        # Try to find clickable elements (button, a, input) with the button text
        button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH, 
                f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text.lower()}')] | "
                f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text.lower()}')] | "
                f"//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text.lower()}')]"
            ))
        )
        logger.info(f"Found clickable element with text '{button_text}'")
        button.click()
        
        # Wait for network activity
        time.sleep(5)  # Increased to capture more network activity
        logger.info(f"Captured {len(network_requests)} network requests")
        
        return network_requests
    
    except Exception as e:
        logger.error(f"Error clicking button '{button_text}': {str(e)}")
        return []

def extract_deal_info(requests, expected_deal_id, expected_deal_code):
    """Extract deal_id and deal_code from network requests."""
    for request in requests:
        url = request.get('url', '')
        if '/api/submit-action' in url:
            logger.info(f"Found submit-action request: {url}")
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            deal_id = query_params.get('deal_id', [None])[0]
            deal_code = query_params.get('deal_code', [None])[0]
            
            if deal_id or deal_code:
                return {
                    'deal_id': deal_id,
                    'deal_code': deal_code,
                    'deal_id_match': deal_id == expected_deal_id if expected_deal_id else None,
                    'deal_code_match': deal_code == expected_deal_code if expected_deal_code else None
                }
    return {
        'deal_id': None,
        'deal_code': None,
        'deal_id_match': False if expected_deal_id else None,
        'deal_code_match': False if expected_deal_code else None
    }

def handle_common_obstacles(driver):
    """Handle common website obstacles like cookie banners."""
    try:
        # Try to find and click common cookie banner accept buttons
        cookie_buttons = [
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]"
        ]
        for xpath in cookie_buttons:
            try:
                button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                logger.info("Clicked cookie banner button")
                time.sleep(1)  # Allow page to settle
            except:
                pass
    except Exception as e:
        logger.debug(f"No cookie banner found or error handling it: {str(e)}")

def analyze_websites(csv_file):
    """Analyze websites from CSV, click buttons, and extract Deal IDs and Codes."""
    # Read CSV
    df = pd.read_csv(csv_file)
    driver = setup_driver()
    results = []
    
    try:
        for index, row in df.iterrows():
            url = row['Link']
            button_text = row['Code']
            expected_deal_id = row['Deal ID'] if pd.notna(row['Deal ID']) else None
            expected_deal_code = row['Code'] if pd.notna(row['Code']) else None
            
            logger.info(f"Processing {url} with button '{button_text}'")
            result = {
                'Brend': row['Brend'],
                'Code': button_text,
                'Link': url,
                'Expected Deal ID': expected_deal_id,
                'Expected Deal Code': expected_deal_code,
                'Found Deal ID': None,
                'Found Deal Code': None,
                'Deal ID Match': None,
                'Deal Code Match': None,
                'Status': 'failed',
                'Error': None,
                'Requests': []
            }
            
            try:
                driver.get(url)
                # Wait for page to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Handle cookie banners or other obstacles
                handle_common_obstacles(driver)
                
                # Capture network requests after button click
                requests = capture_network_requests(driver, button_text)
                
                # Extract deal_id and deal_code
                deal_info = extract_deal_info(requests, expected_deal_id, expected_deal_code)
                
                result.update({
                    'Status': 'success' if deal_info['deal_id'] or deal_info['deal_code'] else 'failed',
                    'Found Deal ID': deal_info['deal_id'],
                    'Found Deal Code': deal_info['deal_code'],
                    'Deal ID Match': deal_info['deal_id_match'],
                    'Deal Code Match': deal_info['deal_code_match'],
                    'Requests': requests,
                    'Request Count': len(requests)
                })
                
            except Exception as e:
                logger.error(f"Failed to process {url}: {str(e)}")
                result['Error'] = str(e)
            
            results.append(result)
    
    finally:
        driver.quit()
    
    return results

def save_results(results, output_file="deal_id_results.json"):
    """Save results to JSON file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}")

if __name__ == "__main__":
    csv_file = "Wethrift - Tabellenblatt1.csv"
    results = analyze_websites(csv_file)
    save_results(results)