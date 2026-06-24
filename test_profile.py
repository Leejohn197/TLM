import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    try:
        # Try to connect to a running Chrome on default port 9222
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        print("Connected to running Chrome!")
        browser.close()
    except Exception as e:
        print("Cannot connect:", e)
