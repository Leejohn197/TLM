from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome", headless=True, args=["--window-size=1920,1080"])
    print(f"Contexts after launch: {len(browser.contexts)}")
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    print("Page viewport:", page.viewport_size)
    browser.close()
