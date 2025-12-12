// -------------------------------
// DOM ELEMENTS
// -------------------------------
const urlInput = document.getElementById("urlInput");
const startBtn = document.getElementById("startBtn");
const resetBtn = document.getElementById("resetBtn");
const resultsDiv = document.getElementById("results");

// Status boxes
const statusIdle    = document.getElementById("status-idle");
const statusRunning = document.getElementById("status-running");
const statusSuccess = document.getElementById("status-success");
const statusWarning = document.getElementById("status-warning");
const statusError   = document.getElementById("status-error");

// -------------------------------
// HELPERS
// -------------------------------
function parseUrls(text) {
    return text
        .split(/[\s,]+/)
        .map(u => u.trim())
        .filter(Boolean);
}

function hideAllStatuses() {
    statusIdle.classList.add("hidden");
    statusRunning.classList.add("hidden");
    statusSuccess.classList.add("hidden");
    statusWarning.classList.add("hidden");
    statusError.classList.add("hidden");
}

function showStatus(type) {
    hideAllStatuses();

    switch (type) {
        case "idle":
            statusIdle.classList.remove("hidden");
            break;
        case "running":
            statusRunning.classList.remove("hidden");
            break;
        case "success":
            statusSuccess.classList.remove("hidden");
            break;
        case "warning":
            statusWarning.classList.remove("hidden");
            break;
        case "error":
            statusError.classList.remove("hidden");
            break;
    }
}

// -------------------------------
// SCAN
// -------------------------------
async function startScan() {
    const raw = urlInput.value.trim();
    const urls = parseUrls(raw);

    if (!urls.length) {
        alert("Please enter at least one URL to scan.");
        return;
    }

    showStatus("running");
    startBtn.disabled = true;
    resetBtn.disabled = false;
    resultsDiv.innerHTML = "";

    try {
        const resp = await fetch("/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ urls })
        });

        if (!resp.ok) {
            showStatus("error");
            return;
        }

        const data = await resp.json();

        data.results.forEach(r => {
            const card = document.createElement("div");
            card.className = "result-card";

            const statusClass =
                r.pdf_count === 0
                    ? "result-warning"
                    : "result-success";

            card.classList.add(statusClass);

            card.innerHTML = `
                <div class="result-header">
                    <div class="result-icon">
                        ${r.pdf_count === 0 ? "⚠️" : "📄"}
                    </div>
                    <div class="result-title">
                        ${r.base_url}
                    </div>
                </div>

                <div class="result-body">
                    <div><span>Pages crawled:</span> ${r.pages_crawled}</div>
                    <div><span>PDFs found:</span> ${r.pdf_count}</div>
                    <div><span>Accessible:</span> ${r.count_accessible}</div>
                    <div><span>Likely inaccessible:</span> ${r.count_likely}</div>
                    <div><span>Inaccessible:</span> ${r.count_inaccessible}</div>
                </div>
            `;

            resultsDiv.appendChild(card);
        });


        // ⛔ STOPPED
        if (data.status === "stopped") {
            showStatus("idle");
            return;
        }

        if (!data.zip_file) {
            showStatus("warning");
            return;
        }

        // Trigger download
        const a = document.createElement("a");
        a.href = data.zip_file;
        document.body.appendChild(a);
        a.click();
        a.remove();

        const hasAnyPdf =
            data.results &&
            data.results.some(r => r.pdf_count > 0 && r.pages_crawled > 1);

        showStatus(hasAnyPdf ? "success" : "warning");

    } catch (err) {
        console.error(err);
        showStatus("error");
    } finally {
        startBtn.disabled = false;
    }
}

// -------------------------------
// STOP & RESET
// -------------------------------
async function stopAndReset() {
    try {
        await fetch("/stop", { method: "POST" });
    } catch (e) {}

    urlInput.value = "";
    resultsDiv.innerHTML = "";
    startBtn.disabled = false;
    resetBtn.disabled = true;
    showStatus("idle");
}

// -------------------------------
// EVENTS
// -------------------------------
startBtn.addEventListener("click", startScan);
resetBtn.addEventListener("click", stopAndReset);

// Initial state
resetBtn.disabled = true;
showStatus("idle");
