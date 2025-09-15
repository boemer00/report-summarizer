#!/usr/bin/env python3
"""
One-off converter: take the most recent HTML report in ./reports and print to PDF
using an installed Chrome/Chromium in headless mode. No wkhtmltopdf required.

Usage:
  python scripts/html_to_pdf.py

Optional env var:
  CHROME_PATH=/path/to/Chrome  # override auto-detection
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path


def find_latest_html(reports_dir: Path) -> Path | None:
    files = list(reports_dir.glob("report_*.html"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def find_chrome_binary() -> str | None:
    # 1) Env override
    env_path = os.getenv("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2) Common macOS app paths
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in mac_paths:
        if Path(p).exists():
            return p

    # 3) PATH fallbacks
    for name in ["google-chrome", "chrome", "chromium", "chromium-browser"]:
        which = shutil.which(name)
        if which:
            return which

    return None


def html_to_pdf(chrome_path: str, html_path: Path, pdf_path: Path) -> None:
    html_uri = html_path.resolve().as_uri()

    # Prefer the new headless mode if supported, otherwise fallback
    base_args = [
        chrome_path,
        "--no-sandbox",
        "--disable-gpu",
        f"--print-to-pdf={str(pdf_path)}",
        "--print-to-pdf-no-header",
    ]

    cmd_new = base_args.copy()
    cmd_new.insert(1, "--headless=new")
    cmd_new.append(html_uri)

    result = subprocess.run(cmd_new, capture_output=True, text=True)
    if result.returncode == 0:
        return

    # Fallback to legacy flag
    cmd_old = base_args.copy()
    cmd_old.insert(1, "--headless")
    cmd_old.append(html_uri)
    result2 = subprocess.run(cmd_old, capture_output=True, text=True)
    if result2.returncode != 0:
        raise RuntimeError(
            f"Chrome failed to print to PDF.\nNew headless stderr: {result.stderr}\nOld headless stderr: {result2.stderr}"
        )


def main() -> int:
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("No reports directory found.")
        return 1

    latest_html = find_latest_html(reports_dir)
    if not latest_html:
        print("No HTML reports found in ./reports")
        return 1

    pdf_path = latest_html.with_suffix(".pdf")

    chrome = find_chrome_binary()
    if not chrome:
        print("Could not find Chrome/Chromium. Set CHROME_PATH or install Chrome.")
        return 1

    try:
        html_to_pdf(chrome, latest_html, pdf_path)
        print(f"PDF created: {pdf_path}")
        return 0
    except Exception as e:
        print(f"Failed to create PDF: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
