import sys
import os
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome", headless=True)
    os.system("ps aux | grep -i chrome | head -n 5")
    browser.close()
