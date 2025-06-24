url = "https://www.wethrift.com/ofp-funding"


import requests
from bs4 import BeautifulSoup
import pandas as pd

page = requests.get(url)
soup = BeautifulSoup(page.content, 'html.parser')

table = soup.find('table', {'class': 'table table-striped'})
rows = table.find_all('tr')

df = pd.DataFrame()

for row in rows:
    cols = row.find_all('td')
    if len(cols) == 2:
        df = df.append({'Name': cols[0].text.strip(), 'Link': cols[1].a['href']}, ignore_index=True)

