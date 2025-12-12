import os
import io
import time
import queue
import re
from urllib.parse import urljoin, urldefrag, urlparse, quote

import requests
import xlsxwriter
from bs4 import BeautifulSoup
from pypdf import PdfReader
import PyPDF2

# ======================================================
# Global flag (toggled ONLY by backend.server)
# ======================================================
STOP_REQUESTED: bool = False


# ======================================================
# HELPERS
# ======================================================

def show_url(u: str) -> str:
    try:
        u.encode("ascii")
        return u
    except UnicodeEncodeError:
        return quote(u, safe=":/?&=%#")


def normalize_input_url(url: str) -> str:
    """
    Normalize user input:
    - add scheme if missing
    - ensure trailing slash
    """
    url = (url or "").strip()
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not url.endswith("/"):
        url += "/"

    return url


def normalize_url(base: str, href: str):
    try:
        href = urldefrag(href)[0]
        if not href:
            return None
        abs_url = urljoin(base, href)
        p = urlparse(abs_url)
        if p.scheme not in ("http", "https"):
            return None
        return p.geturl()
    except Exception:
        return None


def iter_anchor_links(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        u = normalize_url(base_url, a["href"])
        if u:
            yield u


def check_tags_and_alt(data: bytes):
    has_tags = False
    has_alt = False
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        if "/StructTreeRoot" in reader.trailer["/Root"]:
            has_tags = True
        if "/Alt" in str(reader.trailer):
            has_alt = True
    except Exception:
        pass
    return has_tags, has_alt


# ======================================================
# MAIN SCAN FUNCTION
# ======================================================

def scan_site(
    base_url: str,
    global_timestamp: str,
    output_root: str = "scan_results",
    progress_callback=None
):
    """
    Scans ONE site for PDFs and returns stats + report paths.
    """

    global STOP_REQUESTED

    MAX_DEPTH = 50
    MAX_PAGES = 20000
    REQUEST_TIMEOUT = 15
    REQUEST_DELAY = 0.1
    HEADERS = {"User-Agent": "PDFScanner/TagAlt-UI"}

    def report(msg: str):
        print(msg, flush=True)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    # --------------------------------------------------
    # Normalize base URL
    # --------------------------------------------------
    base_url = normalize_input_url(base_url)
    parsed_root = urlparse(base_url)

    ROOT_HOST = parsed_root.netloc
    ROOT_PATH = parsed_root.path.rstrip("/") or "/"

    safe_domain = re.sub(r"[^a-zA-Z0-9.-]", "_", ROOT_HOST)
    OUTPUT_DIR = os.path.join(output_root, f"{global_timestamp}_{safe_domain}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    visited_pages = set()
    pdf_stats = {}
    error_pages = 0
    pages_crawled = 0

    q = queue.Queue()
    q.put((base_url, 0))

    report(f"\n=== SCANNING {base_url} ===")

    # --------------------------------------------------
    # Crawl loop
    # --------------------------------------------------
    while not q.empty() and pages_crawled < MAX_PAGES:

        if STOP_REQUESTED:
            report("=== STOP REQUESTED — SCAN ABORTED ===")
            return None


        url, depth = q.get()

        if url in visited_pages or depth > MAX_DEPTH:
            continue

        parsed = urlparse(url)
        if parsed.netloc != ROOT_HOST:
            continue

        if not parsed.path.startswith(ROOT_PATH):
            continue

        visited_pages.add(url)
        pages_crawled += 1

        report(f"Crawling: {url}")

        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            ctype = (r.headers.get("Content-Type") or "").lower()
        except Exception:
            error_pages += 1
            continue

        if r.status_code >= 400:
            error_pages += 1

        if "text/html" not in ctype:
            continue

        anchors = list(iter_anchor_links(r.text, url))

        # ---------------- PDF extraction ----------------
        for link in anchors:
            if STOP_REQUESTED:
                break

            p = urlparse(link)
            if not (p.netloc == ROOT_HOST and p.path.startswith(ROOT_PATH)):
                continue

            if not link.lower().endswith(".pdf"):
                continue

            if link in pdf_stats:
                continue

            try:
                resp = requests.get(
                    link,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                    stream=True
                )
                if not resp.ok:
                    continue

                data = b"".join(resp.iter_content(chunk_size=64 * 1024))

                pages = len(PdfReader(io.BytesIO(data)).pages)
                has_tags, has_alt = check_tags_and_alt(data)

                if not has_tags:
                    status = "Inaccessible"
                elif has_tags and not has_alt:
                    status = "Likely Inaccessible"
                else:
                    status = "Accessible"

                pdf_stats[link] = {
                    "source_page": url,
                    "pages": pages,
                    "bytes": len(data),
                    "tags": has_tags,
                    "alt": has_alt,
                    "status": status,
                }

            except Exception:
                continue

        # ---------------- Queue inner links ----------------
        for link in anchors:
            p = urlparse(link)
            if (
                p.netloc == ROOT_HOST
                and p.path.startswith(ROOT_PATH)
                and link not in visited_pages
            ):
                q.put((link, depth + 1))

        time.sleep(REQUEST_DELAY)

    # ======================================================
    # Excel report
    # ======================================================
    report_path = os.path.join(OUTPUT_DIR, f"{ROOT_HOST}_pdf_report.xlsx")
    workbook = xlsxwriter.Workbook(report_path)

    ws = workbook.add_worksheet("PDF Report")
    fmt_header = workbook.add_format({"bold": True, "bg_color": "#D9D9D9"})
    fmt_inacc = workbook.add_format({"bg_color": "#FF9999"})
    fmt_likely = workbook.add_format({"bg_color": "#FFFF99"})

    headers = [
        "Source Page",
        "PDF URL",
        "Pages",
        "Bytes",
        "Has Tags",
        "Has Alt Text",
        "Status",
    ]
    for col, h in enumerate(headers):
        ws.write(0, col, h, fmt_header)

    count_inacc = 0
    count_likely = 0
    count_acc = 0
    total_pdf_pages = 0

    row = 1
    for pdf_url, info in pdf_stats.items():
        status = info["status"]
        pages = info["pages"]
        total_pdf_pages += pages

        if status == "Inaccessible":
            fmt = fmt_inacc
            count_inacc += 1
        elif status == "Likely Inaccessible":
            fmt = fmt_likely
            count_likely += 1
        else:
            fmt = None
            count_acc += 1

        ws.write(row, 0, info["source_page"], fmt)
        ws.write(row, 1, pdf_url, fmt)
        ws.write(row, 2, pages, fmt)
        ws.write(row, 3, info["bytes"], fmt)
        ws.write(row, 4, str(info["tags"]), fmt)
        ws.write(row, 5, str(info["alt"]), fmt)
        ws.write(row, 6, status, fmt)
        row += 1

    ws.set_column(0, 1, 80)

    # Summary sheet
    ws2 = workbook.add_worksheet("Summary")
    fmt_title = workbook.add_format({"bold": True, "font_size": 14, "underline": True})
    fmt_key = workbook.add_format({"bold": True, "bg_color": "#D9E1F2"})
    fmt_val = workbook.add_format({"bg_color": "#FFFFFF"})

    ws2.write("A1", "PDF Accessibility Scan Summary", fmt_title)

    stats_data = [
        ("Pages Crawled", pages_crawled),
        ("Error Pages", error_pages),
        ("Total PDFs Found", len(pdf_stats)),
        ("Total PDF Pages", total_pdf_pages),
        ("Inaccessible PDFs", count_inacc),
        ("Likely Inaccessible PDFs", count_likely),
        ("Accessible PDFs", count_acc),
        ("Output Folder", OUTPUT_DIR),
        ("Excel Report", report_path),
    ]

    row = 3
    for key, val in stats_data:
        ws2.write(row, 0, key, fmt_key)
        ws2.write(row, 1, val, fmt_val)
        row += 1

    workbook.close()

    # --------------------------------------------------
    # Paths for server.py ZIP logic
    # --------------------------------------------------
    abs_output_dir = os.path.abspath(OUTPUT_DIR)
    abs_report_path = os.path.abspath(report_path)
    rel_report_path = os.path.relpath(report_path, output_root).replace("\\", "/")

    return {
        "base_url": base_url,
        "pages_crawled": pages_crawled,
        "error_pages": error_pages,
        "pdf_count": len(pdf_stats),
        "count_inaccessible": count_inacc,
        "count_likely": count_likely,
        "count_accessible": count_acc,

        # for ZIP creation
        "output_dir": abs_output_dir,
        "report_full_path": abs_report_path,

        # optional UI link
        "report_path": f"/scan_results/{rel_report_path}",
    }
