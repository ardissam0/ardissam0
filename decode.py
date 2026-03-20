#!/usr/bin/env python3
"""Decode a secret message from a published Google Doc.

The doc contains a table with columns: x-coordinate, Character, y-coordinate.
Characters placed on the grid spell out a secret message when printed.

Usage:
    python decode.py <google_doc_url>
    python decode.py  # uses the default verification URL
"""

import sys
import requests
from bs4 import BeautifulSoup


def decode_secret_message(url: str) -> None:
    """Fetch a published Google Doc, parse its character grid, and print it.

    Args:
        url: The published Google Doc URL containing the grid data.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all tables in the document
    tables = soup.find_all("table")
    if not tables:
        raise ValueError("No table found in the document.")

    # Parse the first table — skip the header row
    grid: dict[tuple[int, int], str] = {}
    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cols = row.find_all(["td", "th"])
            if len(cols) < 3:
                continue
            x_text = cols[0].get_text(strip=True)
            char = cols[1].get_text(strip=True)
            y_text = cols[2].get_text(strip=True)
            if not x_text.lstrip("-").isdigit() or not y_text.lstrip("-").isdigit():
                continue  # skip non-data rows
            x, y = int(x_text), int(y_text)
            grid[(x, y)] = char if char else " "

    if not grid:
        raise ValueError("No grid data found in the document.")

    max_x = max(x for x, _ in grid)
    max_y = max(y for _, y in grid)

    # y=0 is the bottom row; print from top (max_y) down to 0
    for y in range(max_y, -1, -1):
        row = ""
        for x in range(max_x + 1):
            row += grid.get((x, y), " ")
        print(row)


if __name__ == "__main__":
    default_url = (
        "https://docs.google.com/document/d/e/"
        "2PACX-1vSvM5gDlNvt7npYHhp_XfsJvuntUhq184By5xO_pA4b_gCWeXb6dM6ZxwN8rE6S4ghUsCj2VKR21oEP"
        "/pub"
    )
    target_url = sys.argv[1] if len(sys.argv) > 1 else default_url
    decode_secret_message(target_url)
