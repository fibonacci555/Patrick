import cloudscraper
from bs4 import BeautifulSoup

# Create a cloudscraper instance
scraper = cloudscraper.create_scraper()

# URL of the website to scrape
url = "https://www.wethrift.com/bookmap"

# Send a GET request to the website using cloudscraper
response = scraper.get(url)

# Check if the request was successful
if response.status_code == 200:
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all ul elements on the page
    ul_elements = soup.find_all('ul')
    
    if ul_elements:
        print(f"Found {len(ul_elements)} ul elements on the page.")
        for ul_index, ul in enumerate(ul_elements, 1):
            print(f"\nProcessing UL #{ul_index}:")
            # Find all li elements within the current ul
            li_elements = ul.find_all('li')
            
            if li_elements:
                print(f"Found {len(li_elements)} li elements in UL #{ul_index}.")
                for li_index, li in enumerate(li_elements, 1):
                    # Look for a button within the current li
                    button = li.find('button')
                    if button and button.get('title'):
                        print(f"  LI #{li_index}: Button title: {button.get('title')}")
                    else:
                        print(f"  LI #{li_index}: No button with a title attribute found.")
            else:
                print(f"No li elements found in UL #{ul_index}.")
    else:
        print("No ul elements found on the page.")
else:
    print(f"Failed to retrieve the webpage. Status code: {response.status_code}")