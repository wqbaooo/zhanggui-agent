#!/usr/bin/env python3
"""产品页面截图脚本 - 用于产品验收。"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:3005"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

PAGES = [
    ("overview", "/overview"),
    ("capture", "/capture"),
    ("profit", "/profit"),
    ("inventory", "/inventory"),
]

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}


async def take_screenshots():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for device_name, viewport in VIEWPORTS.items():
            print(f"\n=== {device_name} 截图 ===")
            context = await browser.new_context(
                viewport=viewport,
                device_scale_factor=2 if device_name == "mobile" else 1,
                is_mobile=device_name == "mobile",
                has_touch=device_name == "mobile",
            )
            page = await context.new_page()

            for page_name, path in PAGES:
                url = f"{BASE_URL}{path}"
                filename = f"{page_name}-{device_name}.png"
                filepath = OUTPUT_DIR / filename

                print(f"  截取: {url} -> {filename}")
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)
                    await page.screenshot(path=str(filepath), full_page=True)
                    print(f"    完成: {filepath}")
                except Exception as e:
                    print(f"    失败: {e}")

            await context.close()

        await browser.close()

    print(f"\n截图完成，保存至: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(take_screenshots())
