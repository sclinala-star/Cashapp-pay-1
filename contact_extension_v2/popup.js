// Popup script — communicates with background service worker

const statusEl = document.getElementById("status");

function showStatus(text, type = "") {
  statusEl.textContent = text;
  statusEl.className = "status " + type;
  if (type !== "loading") {
    setTimeout(() => { statusEl.textContent = ""; statusEl.className = "status"; }, 3000);
  }
}

// ─── Load current state ──────────────────────────────────────────
async function loadState() {
  // Load toggle states
  const settings = await chrome.storage.local.get(["enabled", "deepCrawlEnabled"]);
  document.getElementById("toggleCollection").checked = settings.enabled ?? true;
  document.getElementById("toggleDeepCrawl").checked = settings.deepCrawlEnabled ?? false;

  // Load contacts from background (decrypted)
  chrome.runtime.sendMessage({ type: "GET_CONTACTS" }, (response) => {
    if (response && response.success) {
      const c = response.contacts;
      document.getElementById("phoneCount").textContent = c.phones.length;
      document.getElementById("emailCount").textContent = c.emails.length;
      document.getElementById("totalCount").textContent = c.phones.length + c.emails.length;
    }
  });
}

loadState();

// ─── Toggle: Collection enabled ──────────────────────────────────
document.getElementById("toggleCollection").onchange = (e) => {
  chrome.storage.local.set({ enabled: e.target.checked });
  showStatus(e.target.checked ? "Collection enabled" : "Collection paused", "success");
};

// ─── Toggle: Deep crawl ─────────────────────────────────────────
document.getElementById("toggleDeepCrawl").onchange = (e) => {
  chrome.storage.local.set({ deepCrawlEnabled: e.target.checked });
  showStatus(e.target.checked ? "Deep crawl ON — sub-pages will be scanned" : "Deep crawl OFF", "success");
};

// ─── Export CSV ──────────────────────────────────────────────────
document.getElementById("exportCsv").onclick = () => {
  showStatus("Exporting CSV...", "loading");
  chrome.runtime.sendMessage({ type: "EXPORT_CSV" }, (response) => {
    if (response && response.success) {
      showStatus("CSV downloaded!", "success");
    } else {
      showStatus("Export failed: " + (response?.error || "Unknown error"), "error");
    }
  });
};

// ─── Export to Google Sheets ─────────────────────────────────────
document.getElementById("exportSheets").onclick = () => {
  showStatus("Connecting to Google Sheets...", "loading");
  chrome.runtime.sendMessage({ type: "EXPORT_GOOGLE_SHEETS" }, (response) => {
    if (response && response.success) {
      showStatus("Exported! Opening spreadsheet...", "success");
      chrome.tabs.create({ url: response.url });
    } else {
      showStatus("Failed: " + (response?.error || "Unknown error"), "error");
    }
  });
};

// ─── Clear all data ──────────────────────────────────────────────
document.getElementById("clearData").onclick = () => {
  if (confirm("Are you sure you want to delete all collected contacts?")) {
    showStatus("Clearing...", "loading");
    chrome.runtime.sendMessage({ type: "CLEAR_CONTACTS" }, (response) => {
      if (response && response.success) {
        document.getElementById("phoneCount").textContent = "0";
        document.getElementById("emailCount").textContent = "0";
        document.getElementById("totalCount").textContent = "0";
        showStatus("All data cleared!", "success");
      } else {
        showStatus("Failed to clear: " + (response?.error || "Unknown error"), "error");
      }
    });
  }
};
