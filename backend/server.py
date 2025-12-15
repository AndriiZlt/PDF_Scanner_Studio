from flask import Flask, request, send_from_directory, jsonify, after_this_request
from . import scanner
from .scanner import scan_site
import os
import re
import zipfile
from datetime import datetime
from urllib.parse import urlparse
from flask_cors import CORS
import threading
import uuid

app = Flask(__name__, static_url_path="", static_folder="../ui")
CORS(app)

jobs = {}

def run_scan_job(job_id, data):
    jobs[job_id] = {"status": "running"}
    scanner.STOP_REQUESTED = False

    raw_urls = data.get("urls", [])
    urls = []
    for u in raw_urls:
        urls.extend(parse_urls(u))
    urls = list(dict.fromkeys(urls))

    if not urls:
        jobs[job_id] = {"status": "error", "error": "No URLs provided"}
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    for url in urls:
        if scanner.STOP_REQUESTED:
            jobs[job_id] = {"status": "stopped"}
            return

        res = scan_site(url, timestamp)
        if res is None:
            jobs[job_id] = {"status": "stopped"}
            return

        results.append(res)

    if not results:
        jobs[job_id] = {"status": "stopped"}
        return

    zip_name = f"pdf_reports_{timestamp}.zip"
    zip_path = os.path.join(SCAN_RESULTS_DIR, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            report_path = r.get("report_full_path")
            if report_path and os.path.exists(report_path):
                host = urlparse(r["base_url"]).netloc
                zf.write(report_path, arcname=f"{host}/{os.path.basename(report_path)}")

    jobs[job_id] = {
        "status": "done",
        "results": results,
        "zip_file": f"/download/{zip_name}",
    }

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
    data = request.json
    job_id = str(uuid.uuid4())

    thread = threading.Thread(
        target=run_scan_job,
        args=(job_id, data),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id}, 202

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


@app.route("/scan/status/<job_id>")
def scan_status(job_id):
    return jobs.get(job_id, {"status": "unknown"})

if __name__ == "__main__":
    app.run(debug=True)
