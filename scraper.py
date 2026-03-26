"""
Scraper for tennisrecruiting.net player profiles.
Extracts Weekly Rankings: National, WTN, UTR (and other fields).
"""

import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.tennisrecruiting.net"

# Browser-like headers to avoid 403
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tennisrecruiting.net/",
    "Connection": "keep-alive",
}


def _get(url, params=None):
    """GET with a shared session and browser headers."""
    session = requests.Session()
    # Touch the homepage first to pick up any cookies
    session.get(BASE_URL, headers=HEADERS, timeout=10)
    resp = session.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.text


def search_players(name, location):
    """
    Search tennisrecruiting.net for players matching `name` and `location`.
    `location` can be a US state abbreviation (e.g. 'NY') or a city name.

    Returns a list of dicts:
        [{"name": str, "location": str, "grad_year": str, "profile_url": str}, ...]
    """
    html = _get(f"{BASE_URL}/player.asp", params={"name": name, "state": location})
    soup = BeautifulSoup(html, "html.parser")

    results = []

    # Player search results are typically in a table with rows linking to player.asp?id=
    for a in soup.find_all("a", href=re.compile(r"player\.asp\?id=\d+")):
        row = a.find_parent("tr")
        cells = row.find_all("td") if row else []
        player_name = a.get_text(strip=True)
        if not player_name:
            continue

        # Grab location and grad year from sibling cells when available
        loc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        grad = cells[2].get_text(strip=True) if len(cells) > 2 else ""

        profile_url = BASE_URL + "/" + a["href"].lstrip("/")
        results.append({
            "name": player_name,
            "location": loc,
            "grad_year": grad,
            "profile_url": profile_url,
        })

    return results


def _clean(text):
    """Strip whitespace and return None for empty/NR/-- values."""
    t = text.strip() if text else ""
    return None if t in ("", "NR", "--", "N/A") else t


def get_player_rankings(profile_url):
    """
    Fetch a player's profile page and extract the Weekly Rankings box.

    Returns a dict:
    {
        "name": str,
        "location": str,
        "grad_year": str,
        "trn_rating": str | None,      # Star rating label e.g. "3-Star"
        # Weekly Rankings
        "national": str | None,        # e.g. "26"
        "sectional": str | None,       # Middle Atlantic / section name
        "state": str | None,           # State ranking
        "tennis_rpi": str | None,
        "usta_standing": str | None,
        "wtn": str | None,             # ITF World Tennis Number
        "utr": str | None,             # Universal Tennis Rating
        # Highest Rankings
        "highest_national": str | None,
        "highest_tennis_rpi": str | None,
        # Activity
        "overall_record": str | None,
        "profile_url": str,
    }
    """
    html = _get(profile_url)
    soup = BeautifulSoup(html, "html.parser")

    result = {"profile_url": profile_url}

    # ── Player name, location, grad year ──────────────────────────────────
    name_tag = soup.find("span", style=re.compile(r"color:\s*#[Ff][Ff]", re.I)) or \
               soup.find("td", class_=re.compile(r"player.?name", re.I))
    if not name_tag:
        # Fall back: look for a prominent blue-colored name near the top
        for tag in soup.find_all(["b", "span", "td"]):
            txt = tag.get_text(strip=True)
            if txt and 3 < len(txt) < 60 and tag.find_parent("table"):
                # heuristic: player names appear early in the page
                result.setdefault("name", txt)
                break
    else:
        result["name"] = name_tag.get_text(strip=True)

    # ── Locate the "WEEKLY RANKINGS" section ──────────────────────────────
    weekly_header = None
    for tag in soup.find_all(string=re.compile(r"WEEKLY\s+RANKINGS", re.I)):
        weekly_header = tag
        break

    weekly_data = {}
    if weekly_header:
        # Walk up to the enclosing table/div and parse label→value rows
        container = weekly_header
        for _ in range(6):
            container = getattr(container, "parent", None)
            if container and container.name in ("table", "div"):
                break

        if container:
            rows = container.find_all("tr")
            i = 0
            while i < len(rows):
                cells = rows[i].find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).rstrip(":")
                    value = _clean(cells[-1].get_text(strip=True))
                    # Strip trailing arrow characters (↑↓ or icon text)
                    if value:
                        value = re.sub(r"[\u2191\u2193\u25b2\u25bc]", "", value).strip()
                        # Remove trailing single letters that are icon artifacts
                        value = re.sub(r"\s+[A-Z]$", "", value).strip()
                    label_lower = label.lower()
                    if "national" in label_lower:
                        weekly_data["national"] = value
                    elif any(x in label_lower for x in ("middle", "atlantic", "southern", "midwest",
                                                         "pacific", "southwest", "intermountain",
                                                         "new england", "sectional")):
                        weekly_data["sectional"] = f"{label}: {value}" if value else None
                    elif "state" in label_lower or (
                        "new york" in label_lower or "california" in label_lower or
                        "florida" in label_lower or "texas" in label_lower
                    ):
                        weekly_data["state"] = f"{label}: {value}" if value else None
                    elif "rpi" in label_lower:
                        weekly_data["tennis_rpi"] = value
                    elif "usta" in label_lower:
                        weekly_data["usta_standing"] = value
                    elif "wtn" in label_lower or "itf" in label_lower:
                        weekly_data["wtn"] = value
                    elif "utr" in label_lower:
                        weekly_data["utr"] = value
                i += 1

    result.update(weekly_data)

    # ── Locate the "HIGHEST RANKINGS" section ─────────────────────────────
    highest_header = None
    for tag in soup.find_all(string=re.compile(r"HIGHEST\s+RANKINGS", re.I)):
        highest_header = tag
        break

    if highest_header:
        container = highest_header
        for _ in range(6):
            container = getattr(container, "parent", None)
            if container and container.name in ("table", "div"):
                break
        if container:
            for row in container.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).rstrip(":")
                    value = _clean(cells[-1].get_text(strip=True))
                    if "recruiting" in label.lower() or "national" in label.lower():
                        result["highest_national"] = value
                    elif "rpi" in label.lower():
                        result["highest_tennis_rpi"] = value

    # ── Overall record ─────────────────────────────────────────────────────
    for tag in soup.find_all(string=re.compile(r"overall\s+record", re.I)):
        row = tag.find_parent("tr")
        if row:
            cells = row.find_all("td")
            if len(cells) >= 2:
                result["overall_record"] = _clean(cells[-1].get_text(strip=True))
            break

    return result
