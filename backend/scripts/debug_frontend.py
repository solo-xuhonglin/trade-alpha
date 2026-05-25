"""Debug frontend white screen - capture console logs and screenshot."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    logs = []
    def on_console(msg):
        logs.append({"type": msg.type, "text": msg.text})

    page.on("console", on_console)
    page.on("pageerror", lambda e: logs.append({"type": "pageerror", "text": str(e)}))

    page.goto("http://localhost:3000", timeout=15000)
    page.wait_for_load_state("networkidle", timeout=15000)

    import time
    time.sleep(2)

    page.screenshot(path="C:\\Users\\Agent\\AppData\\Local\\Temp\\frontend_debug.png", full_page=True)

    print("=== CONSOLE LOGS ===")
    for l in logs:
        print(f"[{l['type']}] {l['text']}")

    print("\n=== PAGE CONTENT (first 3000 chars) ===")
    content = page.content()
    print(content[:3000])

    browser.close()
