from flask import Flask
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

app = Flask(__name__)

URL = "https://uzmanpara.milliyet.com.tr/canli-borsa/bist-TUM-hisseleri/"

def get_prices():
    r = requests.get(URL, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "hisseSenetleri"})
    rows = []
    if table:
        for tr in table.find("tbody").find_all("tr"):
            cols = [td.text.strip() for td in tr.find_all("td")]
            if cols:
                rows.append(cols[:3])  # Sembol, Fiyat, Değişim %
    df = pd.DataFrame(rows, columns=["Hisse", "Fiyat", "Değişim"])
    return df.to_html(index=False)

@app.route("/")
def home():
    return "<h2>Borsa Canlı Fiyatlar (60sn)</h2>" + get_prices()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
