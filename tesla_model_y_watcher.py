#!/usr/bin/env python3
"""
Tesla Model Y Watcher - Cloud-Version (für GitHub Actions)
------------------------------------------------------------
Führt EINEN Durchlauf aus (kein while-Loop - das Scheduling
übernimmt der GitHub Actions Cron). Der NTFY_TOPIC kommt aus
einer Umgebungsvariable / einem Repo-Secret, nicht hartkodiert.
"""

import json
import os
import sys
from datetime import datetime

import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_vins.json")
CONDITION = "new"  # "new" oder "used"

API_URL = "https://www.tesla.com/inventory/api/v1/inventory-results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": f"https://www.tesla.com/de_de/inventory/{CONDITION}/my",
}
QUERY = {
    "query": {
        "model": "my",
        "condition": CONDITION,
        "options": {},
        "arrangeby": "Price",
        "order": "asc",
        "market": "DE",
        "language": "de",
        "super_region": "europe",
        "lng": "",
        "lat": "",
        "zip": "",
        "range": 0,
    },
    "offset": 0,
    "count": 50,
    "outsideOffset": 0,
    "outsideSearch": False,
}


def fetch_inventory() -> list:
    params = {"query": json.dumps(QUERY)}
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def load_seen_vins() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_vins(vins: set) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(vins), f)


def notify(title: str, message: str, link: str) -> None:
    if not NTFY_TOPIC:
        print("Kein NTFY_TOPIC gesetzt - überspringe Benachrichtigung.")
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Click": link},
        timeout=10,
    )


def describe(car: dict) -> str:
    trim = car.get("TRIM", "")
    paint = (car.get("PAINT") or [""])[0]
    price = car.get("Price")
    price_str = f"{price:,.0f} €".replace(",", ".") if price else "Preis n/a"
    return f"{trim} · {paint} · {price_str}"


def vehicle_link(car: dict) -> str:
    vin = car.get("VIN", "")
    return f"https://www.tesla.com/de_de/my/order/{vin}"


def main() -> None:
    results = fetch_inventory()
    seen = load_seen_vins()
    new_vins = set()

    for car in results:
        vin = car.get("VIN")
        if vin and vin not in seen:
            new_vins.add(vin)
            notify("Neues Model Y verfügbar!", describe(car), vehicle_link(car))

    if new_vins:
        save_seen_vins(seen | new_vins)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {len(results)} Fahrzeuge gefunden, {len(new_vins)} davon neu.")
    sys.exit(0)


if __name__ == "__main__":
    main()
