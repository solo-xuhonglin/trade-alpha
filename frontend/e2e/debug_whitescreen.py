"""Get detailed ModelConfigView error."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})

    page = context.new_page()
    logs = []

    def handle_console(msg):
        logs.append({"type": msg.type, "text": msg.text})
        # Print immediately
        print(f"[{msg.type}] {msg.text}")

    def handle_pageerror(err):
        logs.append({"type": "pageerror", "text": str(err)})
        print(f"[pageerror] {err}")

    page.on("console", handle_console)
    page.on("pageerror", handle_pageerror)

    page.goto("http://localhost:3000/models", timeout=15000)
    page.wait_for_load_state("networkidle", timeout=15000)

    import time
    time.sleep(2)

    page.screenshot(path="/tmp/models_debug.png", full_page=True)
    print("\nScreenshot saved")

    browser.close()
