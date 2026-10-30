# -*- coding: utf-8 -*-
"""mobile-v2 UI 截图自查：核心布局 + 3D 模型 + 摇杆 + 聊天抽屉 + 设备屏。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:17867"
OUT = pathlib.Path(__file__).resolve().parent / "shots"
OUT.mkdir(exist_ok=True)


def main():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception:
            browser = p.chromium.launch()

        # ---------- 手机遥控台 ----------
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
        page.goto(BASE, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(OUT / "01-main.png"))

        box = page.locator("#joystick").bounding_box()
        if box:
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.move(cx + box["width"] * 0.4, cy - box["height"] * 0.3, steps=6)
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "02-joystick.png"))
            print("pose:", page.inner_text("#poseYaw"), page.inner_text("#posePitch"))
            page.mouse.up()

        page.evaluate("() => document.getElementById('chatFab').click()")
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "03-chat-open.png"))
        page.fill("#chatMessageInput", "你好")
        page.click("#chatSendButton")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "04-thinking.png"))
        page.wait_for_timeout(3200)
        page.screenshot(path=str(OUT / "05-reply.png"))
        page.close()

        # ---------- 设备屏模拟器 ----------
        dev = browser.new_page(viewport={"width": 900, "height": 520})
        dev.goto(f"{BASE}/device-screen.html", wait_until="networkidle", timeout=20000)
        dev.wait_for_timeout(500)
        sbox = dev.locator("#shell").bounding_box()
        if sbox:
            cx, cy = sbox["x"] + sbox["width"] / 2, sbox["y"] + sbox["height"] / 2
            dev.mouse.move(cx, cy)
            dev.mouse.down()
            dev.mouse.move(cx + 60, cy - 30, steps=8)
            dev.wait_for_timeout(500)
            dev.screenshot(path=str(OUT / "device-screen.png"))
            dev.mouse.up()
        dev.close()
        browser.close()

    print("SHOTS:", OUT)
    if errors:
        print("CONSOLE WARN/ERR:")
        for e in errors[:8]:
            print("  ", e)
    else:
        print("NO CONSOLE ERRORS")


if __name__ == "__main__":
    main()