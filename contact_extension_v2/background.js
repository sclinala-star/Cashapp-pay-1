// Background Service Worker for Contact Collector v2
// Handles contact processing, encryption, and Google Sheets export centrally

// ─── Encryption helpers (AES-GCM) ───────────────────────────────

const ENCRYPTION_KEY_NAME = "contact_collector_key";

async function getOrCreateKey() {
  const stored = await chrome.storage.local.get([ENCRYPTION_KEY_NAME]);
  if (stored[ENCRYPTION_KEY_NAME]) {
    const raw = Uint8Array.from(atob(stored[ENCRYPTION_KEY_NAME]), c => c.charCodeAt(0));
    return crypto.subtle.importKey("raw", raw, "AES-GCM", true, ["encrypt", "decrypt"]);
  }
  const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
  const exported = await crypto.subtle.exportKey("raw", key);
  const b64 = btoa(String.fromCharCode(...new Uint8Array(exported)));
  await chrome.storage.local.set({ [ENCRYPTION_KEY_NAME]: b64 });
  return key;
}

async function encryptData(plaintext) {
  const key = await getOrCreateKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, encoded);
  return {
    iv: btoa(String.fromCharCode(...iv)),
    data: btoa(String.fromCharCode(...new Uint8Array(ciphertext)))
  };
}

async function decryptData(encrypted) {
  if (!encrypted || !encrypted.iv || !encrypted.data) return null;
  try {
    const key = await getOrCreateKey();
    const iv = Uint8Array.from(atob(encrypted.iv), c => c.charCodeAt(0));
    const data = Uint8Array.from(atob(encrypted.data), c => c.charCodeAt(0));
    const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, data);
    return new TextDecoder().decode(decrypted);
  } catch (e) {
    console.error("Decryption failed:", e);
    return null;
  }
}

// ─── Contact storage (encrypted) ────────────────────────────────

async function loadContacts() {
  const stored = await chrome.storage.local.get(["contacts_encrypted"]);
  if (stored.contacts_encrypted) {
    const json = await decryptData(stored.contacts_encrypted);
    if (json) return JSON.parse(json);
  }
  // Migration: check for old unencrypted contacts
  const old = await chrome.storage.local.get(["contacts"]);
  if (old.contacts) {
    await saveContacts(old.contacts);
    await chrome.storage.local.remove(["contacts"]);
    return old.contacts;
  }
  return { emails: [], phones: [] };
}

async function saveContacts(contacts) {
  const json = JSON.stringify(contacts);
  const encrypted = await encryptData(json);
  await chrome.storage.local.set({ contacts_encrypted: encrypted });
}

// ─── Badge update ────────────────────────────────────────────────

async function updateBadge() {
  const contacts = await loadContacts();
  const total = contacts.emails.length + contacts.phones.length;
  chrome.action.setBadgeText({ text: total > 0 ? String(total) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
}

// ─── Google Sheets export ────────────────────────────────────────

async function getAuthToken() {
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive: true }, (token) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(token);
      }
    });
  });
}

async function createSpreadsheet(token, contacts) {
  // Create a new spreadsheet
  const createRes = await fetch("https://sheets.googleapis.com/v4/spreadsheets", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      properties: {
        title: `Contacts - ${new Date().toLocaleDateString()}`
      },
      sheets: [{
        properties: { title: "Contacts" }
      }]
    })
  });

  if (!createRes.ok) {
    const err = await createRes.text();
    throw new Error(`Failed to create spreadsheet: ${err}`);
  }

  const spreadsheet = await createRes.json();
  const spreadsheetId = spreadsheet.spreadsheetId;

  // Prepare rows
  const rows = [["Type", "Value", "Collected Date"]];
  contacts.phones.forEach(p => rows.push(["Phone", p, new Date().toISOString()]));
  contacts.emails.forEach(e => rows.push(["Email", e, new Date().toISOString()]));

  // Write data
  await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/Contacts!A1:C${rows.length}?valueInputOption=RAW`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ values: rows })
    }
  );

  // Format header row (bold)
  await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}:batchUpdate`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        requests: [{
          repeatCell: {
            range: { sheetId: 0, startRowIndex: 0, endRowIndex: 1 },
            cell: {
              userEnteredFormat: {
                textFormat: { bold: true },
                backgroundColor: { red: 0.2, green: 0.66, blue: 0.33, alpha: 1 }
              }
            },
            fields: "userEnteredFormat(textFormat,backgroundColor)"
          }
        }, {
          autoResizeDimensions: {
            dimensions: { sheetId: 0, dimension: "COLUMNS", startIndex: 0, endIndex: 3 }
          }
        }]
      })
    }
  );

  return spreadsheet.spreadsheetUrl;
}

// ─── Message handling ────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ADD_CONTACTS") {
    (async () => {
      try {
        const contacts = await loadContacts();
        const newEmails = message.emails || [];
        const newPhones = message.phones || [];

        contacts.emails = [...new Set([...contacts.emails, ...newEmails])];
        contacts.phones = [...new Set([...contacts.phones, ...newPhones])];

        await saveContacts(contacts);
        await updateBadge();
        sendResponse({ success: true, contacts });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true; // async response
  }

  if (message.type === "GET_CONTACTS") {
    (async () => {
      try {
        const contacts = await loadContacts();
        sendResponse({ success: true, contacts });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (message.type === "CLEAR_CONTACTS") {
    (async () => {
      try {
        await saveContacts({ emails: [], phones: [] });
        await updateBadge();
        sendResponse({ success: true });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (message.type === "EXPORT_GOOGLE_SHEETS") {
    (async () => {
      try {
        const token = await getAuthToken();
        const contacts = await loadContacts();
        const url = await createSpreadsheet(token, contacts);
        sendResponse({ success: true, url });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (message.type === "EXPORT_CSV") {
    (async () => {
      try {
        const contacts = await loadContacts();
        let csv = "Type,Value\n";
        contacts.phones.forEach(x => csv += `Phone,"${x}"\n`);
        contacts.emails.forEach(x => csv += `Email,"${x}"\n`);

        const blob = new Blob([csv], { type: "text/csv" });
        const reader = new FileReader();
        reader.onload = () => {
          chrome.downloads.download({
            url: reader.result,
            filename: "contacts.csv"
          });
          sendResponse({ success: true });
        };
        reader.readAsDataURL(blob);
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }
});

// Initialize badge on install/startup
chrome.runtime.onInstalled.addListener(updateBadge);
chrome.runtime.onStartup.addListener(updateBadge);
