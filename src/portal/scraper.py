import re
from bs4 import BeautifulSoup


def to_number(text):
    """Convert Chilean-formatted text to a number: '1.234,5' -> 1234.5"""
    if not text:
        return None
    clean = text.strip().replace(".", "").replace("$", "")
    try:
        return float(clean)
    except ValueError:
        return None

def extract_price(listing):
    """Return (price, currency). Skips the crossed-out old price on discounted listings."""
    for amount in listing.select(".andes-money-amount"):
        # Skip the previous (crossed-out) price
        classes = " ".join(amount.get("class", []))
        if "previous" in classes or amount.find_parent("s"):
            continue
        symbol = amount.select_one(".andes-money-amount__currency-symbol")
        integer = amount.select_one(".andes-money-amount__fraction")
        if not integer:
            continue
        currency = "UF" if symbol and symbol.get_text(strip=True) == "UF" else "CLP"
        value = to_number(integer.get_text())
        
        # Only UF has decimals; Mercado Libre renders them in a separate element
        decimals = amount.select_one(".andes-money-amount__cents")
        if currency == "UF" and decimals:
            value = to_number(f"{integer.get_text()},{decimals.get_text()}")
        return value, currency
    return None, None


def find_number(pattern, text):
    """find a number in text using regular expression"""
    match = re.search(pattern, text, re.IGNORECASE)
    return to_number(match.group(1)) if match else None

def text_of(listing, selector):
    """Return text of an element"""
    element = listing.select_one(selector)
    return element.get_text(strip=True) if element else None


def extract_neighborhood(location):
    """'Las Heras 973, Concepción, Barrio Poniente, Concepción' -> 'Barrio Poniente'"""
    if not location:
        return None
    parts = [p.strip() for p in location.split(",")]
    return parts[-2] if len(parts) >= 2 else None


def extract_listings(html, commune, property_type):
    """Take the HTML of a results page and return a list of listings."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for listing in soup.select("li.ui-search-layout__item"):
        text = listing.get_text(" ", strip=True)

        link = listing.select_one("a[href]")
        url = link["href"].split("#")[0].split("?")[0] if link else None
        id_match = re.search(r"MLC-?(\d+)", url or "")

        location = text_of(listing, ".poly-component__location")
        price, currency = extract_price(listing)

        rows.append({
            "source": "portal_inmobiliario",
            "id": f"MLC{id_match.group(1)}" if id_match else None,
            "commune": commune,
            "property_type": property_type,
            "title": text_of(listing, ".poly-component__title"),
            "broker": text_of(listing, ".poly-component__seller"),
            "price": price,
            "currency": currency,
            "bedrooms": find_number(r"(\d+)\s*dormitorio", text),
            "bathrooms": find_number(r"(\d+)\s*baño", text),
            "usable_m2": find_number(r"([\d.,]+)\s*m²\s*útil", text),
            "total_m2": find_number(r"([\d.,]+)\s*m²\s*total", text),
            "location": location,
            "neighborhood": extract_neighborhood(location),
            "url": url,
        })

    return rows


# Offline test using the saved HTML.
# This block only runs when you execute this file directly.
if __name__ == "__main__":
    import pandas as pd

    with open("data/raw/portal_ejemplo.html", encoding="utf-8") as f:
        rows = extract_listings(f.read(), "Concepción", "departamento")

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)

    print(f"Rows: {len(df)}\n")
    print(df[["id", "price", "currency", "bedrooms", "bathrooms", "usable_m2", "neighborhood"]].head(10))

    print("\nListings by currency:")
    print(df["currency"].value_counts(dropna=False))

    print("\nMissing values per column:")
    print(df.isna().sum())

    print("\nUF listings:")
    print(df[df["currency"] == "UF"][["price", "bedrooms", "usable_m2", "title"]])