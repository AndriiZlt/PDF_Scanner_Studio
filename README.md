PDF Accessibility Scanner
A web-based tool that crawls websites, finds PDF files, and evaluates their basic accessibility features (tags and alternative text).
The scanner generates an Excel report and provides a clear visual summary in the UI.
________________________________________
Features
•	Crawl one or multiple websites
•	Scan only within the same domain and path
•	Detect PDFs and analyze:
o	Tagged PDF structure
o	Presence of alternative text
•	Generate Excel accessibility reports
•	Download results as a ZIP archive
•	Clear UI status states (idle, running, success, warning, error)
•	Stop scan at any time
________________________________________
Tech Stack
•	Backend: Python, Flask
•	Frontend: HTML, CSS, Vanilla JavaScript
•	PDF analysis: PyPDF2, pypdf
•	Reports: xlsxwriter
•	Deployment: Render.com (Gunicorn)
________________________________________
Project Structure
PDF_Scan_Studio/
├─ backend/
│  ├─ __init__.py
│  ├─ server.py
│  ├─ scanner.py
├─ ui/
│  ├─ index.html
│  ├─ app.js
│  ├─ styles.css
├─ scan_results/
├─ requirements.txt
├─ start_app.py
└─ README.md
________________________________________
Local Setup
1. Clone repository
git clone https://github.com/YOUR_USERNAME/pdf-scan-studio.git
cd pdf-scan-studio
2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
3. Install dependencies
pip install -r requirements.txt
4. Run locally
python start_app.py
Open browser at:
http://127.0.0.1:5000
________________________________________
Usage
1.	Enter one or more website URLs
o	Separate by comma, space, or new line
2.	Click Start Scan
3.	Monitor scan status
4.	Download generated report
5.	View summary results in the UI
To stop a scan, click Stop & Reset.
________________________________________
Output
•	Excel report per scanned site
•	ZIP archive containing all reports
•	Stored locally in:
PDF_Scan_Studio/scan_results/
________________________________________
Deployment (Render.com)
Required
•	gunicorn in requirements.txt
•	start_app.py entry point
•	Mounted persistent disk for /scan_results
Start command
gunicorn start_app:app
________________________________________
Known Limitations
•	Free Render tier may sleep after inactivity
•	Large sites may take time to scan
•	Basic accessibility checks only (not full WCAG validation)
________________________________________
Roadmap
•	Live progress streaming
•	Advanced PDF accessibility checks
•	Background job queue
•	User authentication
•	Cloud storage integration
________________________________________
License
MIT License
