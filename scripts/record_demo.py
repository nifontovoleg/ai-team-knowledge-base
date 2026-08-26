"""Record silent demo video of the Team Knowledge Base UI (2–4 min target)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "evidence"
RAW_DIR = OUT_DIR / "_demo_raw"
FINAL = OUT_DIR / "demo.webm"
BASE = "http://127.0.0.1:8000"


def pause(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def main() -> None:
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="ru-RU",
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        pause(page, 7)

        # Documents showcase
        page.locator('button.tab[data-tab="documents"]').click()
        pause(page, 5)
        page.locator("#reload-docs").click()
        pause(page, 4)
        open_btn = page.locator("#docs-body button").filter(has_text="Открыть").first
        open_btn.click()
        pause(page, 10)
        page.locator("#doc-dialog button").filter(has_text="Закрыть").click()
        pause(page, 3)

        # Successful ask
        page.locator('button.tab[data-tab="ask"]').click()
        pause(page, 4)
        page.fill("#ask-question", "До какого времени нужно провести стендап?")
        pause(page, 4)
        page.locator("#ask-form button[type='submit']").click()
        page.wait_for_selector("#ask-answer", state="visible")
        page.wait_for_function(
            """() => {
              const t = document.querySelector('#ask-answer')?.textContent || '';
              return t && !t.includes('Думаю');
            }"""
        )
        pause(page, 12)
        src = page.locator("#ask-sources a").first
        if src.count():
            src.click()
            pause(page, 8)
            page.locator("#doc-dialog button").filter(has_text="Закрыть").click()
            pause(page, 3)

        # Needs review ask
        page.fill("#ask-question", "Какой размер бонуса за лучший мем месяца?")
        pause(page, 4)
        page.locator("#ask-form button[type='submit']").click()
        page.wait_for_function(
            """() => {
              const t = document.querySelector('#ask-answer')?.textContent || '';
              return t && !t.includes('Думаю');
            }"""
        )
        pause(page, 12)

        # History + filter + card + audit
        page.locator('button.tab[data-tab="history"]').click()
        pause(page, 6)
        page.locator("#filter-review").check()
        page.locator("#reload-history").click()
        pause(page, 6)
        page.locator("#qa-body button").filter(has_text="Открыть").first.click()
        pause(page, 10)
        page.locator("#qa-dialog button").filter(has_text="Закрыть").click()
        pause(page, 3)
        page.locator("#audit-body").scroll_into_view_if_needed()
        pause(page, 7)

        # Trigger CSV download (show click; file saved by browser context)
        with page.expect_download(timeout=15000) as dl_info:
            page.locator('a[href="/export/qa?format=csv"]').click()
        download = dl_info.value
        csv_path = OUT_DIR / "demo-export-qa_runs.csv"
        download.save_as(str(csv_path))
        pause(page, 5)

        # Also click JSON export briefly
        with page.expect_download(timeout=15000) as dl_json:
            page.locator('a[href="/export/qa?format=json"]').click()
        dl_json.value.save_as(str(OUT_DIR / "demo-export-qa_runs.json"))
        pause(page, 4)

        # Final hold on history
        pause(page, 5)

        page.close()
        context.close()
        browser.close()

    videos = list(RAW_DIR.glob("*.webm"))
    if not videos:
        raise SystemExit("no video recorded")
    # Playwright names the file after the page; take the newest
    video = max(videos, key=lambda p: p.stat().st_mtime)
    if FINAL.exists():
        FINAL.unlink()
    shutil.move(str(video), str(FINAL))
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    size_mb = FINAL.stat().st_size / (1024 * 1024)
    print(f"saved {FINAL} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    started = time.perf_counter()
    main()
    print(f"elapsed_sec={time.perf_counter() - started:.1f}")
