from flask import Flask, request, send_from_directory, jsonify, after_this_request
from . import scanner
from .scanner import scan_site
import os
import re
import zipfile
from datetime import datetime
from urllib.parse import urlparse
from flask_cors import CORS

app = Flask(__name__, static_url_path="", static_folder="../ui")
CORS(app)

SCAN_RESULTS_DIR = os.path.abspath("scan_results")
os.makedirs(SCAN_RESULTS_DIR, exist_ok=True)


def parse_urls(text: str):
    return [
        u.strip()
        for u in re.split(r"[\s,]+", text or "")
        if u.strip()
    ]


@app.route("/")
def index():
    return app.send_static_file("index.html")


# --------------------------------------------------
# START SCAN
# --------------------------------------------------
@app.route("/scan", methods=["POST"])
def scan():
    # IMPORTANT: reset stop flag for new scan
    scanner.STOP_REQUESTED = False

    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400

    data = request.get_json(silent=True) or {}
    raw_urls = data.get("urls", [])

    urls = []
    for u in raw_urls:
        urls.extend(parse_urls(u))

    urls = list(dict.fromkeys(urls))

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    print(f"\n=== Starting scan job at {timestamp} ===", flush=True)
    print(f"URLs to scan: {urls}", flush=True)

    for url in urls:
        if scanner.STOP_REQUESTED:
            print("=== Scan aborted before next site ===", flush=True)
            return jsonify({"status": "stopped"})

        try:
            print(f"=== Calling scan_site for {url} ===", flush=True)
            res = scan_site(url, timestamp)

            # ⛔ scan_site returns None when stopped
            if res is None:
                print("=== Scan aborted during site scan ===", flush=True)
                return jsonify({"status": "stopped"})

            results.append(res)

        except Exception as e:
            print(f"[ERROR] scan_site failed for {url}: {e}", flush=True)

    if scanner.STOP_REQUESTED or not results:
        return jsonify({"status": "stopped"})

    # --------------------------------------------------
    # ZIP CREATION
    # --------------------------------------------------
    zip_name = f"pdf_reports_{timestamp}.zip"
    zip_path = os.path.join(SCAN_RESULTS_DIR, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            report_path = r.get("report_full_path")
            base_url = r.get("base_url", "")

            if not report_path or not os.path.exists(report_path):
                continue

            host = urlparse(base_url).netloc or "site"
            host = re.sub(r"[^a-zA-Z0-9_.-]", "_", host)

            zf.write(
                report_path,
                arcname=os.path.join(host, os.path.basename(report_path))
            )

    print(f"[INFO] ZIP created: {zip_path}", flush=True)

    return jsonify({
        "results": results,
        "zip_file": f"/download/{zip_name}"
    })


# --------------------------------------------------
# DOWNLOAD ZIP
# --------------------------------------------------
@app.route("/download/<path:filename>")
def download(filename):
    file_path = os.path.join(SCAN_RESULTS_DIR, filename)

    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[INFO] Deleted ZIP after download: {file_path}", flush=True)
        except Exception as e:
            print(f"[WARN] Failed to delete ZIP: {e}", flush=True)
        return response

    return send_from_directory(
        SCAN_RESULTS_DIR,
        filename,
        as_attachment=True
    )



# --------------------------------------------------
# STOP SCAN
# --------------------------------------------------
@app.route("/stop", methods=["POST"])
def stop_scan():
    scanner.STOP_REQUESTED = True
    print("[INFO] Stop requested by user", flush=True)
    return jsonify({"status": "stopping"})


@app.route("/scan_results/<path:filename>")
def serve_scan_results(filename):
    return send_from_directory(SCAN_RESULTS_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
