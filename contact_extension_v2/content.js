// Content Script — Collects contacts from current page + deep crawls links

(async () => {
  const data = await chrome.storage.local.get(["enabled"]);
  const enabled = data.enabled ?? true;
  if (!enabled) return;

  // ─── Regex patterns ────────────────────────────────────────────
  const EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g;
  const PHONE_RE = /(\+?\d[\d\s()\-]{7,}\d)/g;

  // ─── Extract contacts from text ────────────────────────────────
  function extractContacts(text) {
    const emails = [...new Set((text.match(EMAIL_RE) || []))];
    const phones = [...new Set((text.match(PHONE_RE) || []).map(p => p.trim()))];

    // Also extract WhatsApp numbers from wa.me links
    const waRe = /wa\.me\/(\+?\d[\d]{7,})/g;
    let match;
    while ((match = waRe.exec(text)) !== null) {
      phones.push(match[1]);
    }

    return {
      emails: [...new Set(emails)],
      phones: [...new Set(phones)]
    };
  }

  // ─── Extract contacts from current page ────────────────────────
  function extractFromPage() {
    const text = document.body ? document.body.innerText : "";
    const links = document.querySelectorAll("a[href]");
    let extraText = "";
    links.forEach(link => {
      const href = link.href || "";
      if (href.startsWith("mailto:")) {
        extraText += " " + href.replace("mailto:", "").split("?")[0];
      }
      if (href.startsWith("tel:")) {
        extraText += " " + href.replace("tel:", "");
      }
      if (href.includes("wa.me/")) {
        extraText += " " + href;
      }
    });
    return extractContacts(text + extraText);
  }

  // ─── Get same-domain links for deep crawling ───────────────────
  function getSameDomainLinks() {
    const currentDomain = window.location.hostname;
    const currentUrl = window.location.href;
    const links = document.querySelectorAll("a[href]");
    const urls = new Set();

    links.forEach(link => {
      try {
        const url = new URL(link.href, window.location.origin);
        if (
          url.hostname === currentDomain &&
          url.href !== currentUrl &&
          !url.href.includes("#") &&
          !url.href.match(/\.(jpg|jpeg|png|gif|svg|pdf|zip|mp4|mp3|css|js)$/i)
        ) {
          urls.add(url.href);
        }
      } catch (e) { /* invalid URL, skip */ }
    });

    return [...urls];
  }

  // ─── Deep crawl: fetch sub-pages and extract contacts ──────────
  async function deepCrawl(urls, maxPages = 20) {
    const allEmails = [];
    const allPhones = [];
    const crawled = urls.slice(0, maxPages);

    const results = await Promise.allSettled(
      crawled.map(async (url) => {
        try {
          const res = await fetch(url, {
            credentials: "same-origin",
            headers: { "Accept": "text/html" }
          });
          if (!res.ok) return null;
          const contentType = res.headers.get("content-type") || "";
          if (!contentType.includes("text/html")) return null;
          const html = await res.text();

          const parser = new DOMParser();
          const doc = parser.parseFromString(html, "text/html");
          const text = doc.body ? doc.body.innerText : "";

          let extraText = "";
          const pageLinks = doc.querySelectorAll("a[href]");
          pageLinks.forEach(link => {
            const href = link.getAttribute("href") || "";
            if (href.startsWith("mailto:")) {
              extraText += " " + href.replace("mailto:", "").split("?")[0];
            }
            if (href.startsWith("tel:")) {
              extraText += " " + href.replace("tel:", "");
            }
          });

          return extractContacts(text + extraText);
        } catch (e) {
          return null;
        }
      })
    );

    results.forEach(r => {
      if (r.status === "fulfilled" && r.value) {
        allEmails.push(...r.value.emails);
        allPhones.push(...r.value.phones);
      }
    });

    return {
      emails: [...new Set(allEmails)],
      phones: [...new Set(allPhones)]
    };
  }

  // ─── Main: collect from current page ───────────────────────────
  const currentPageContacts = extractFromPage();

  chrome.runtime.sendMessage({
    type: "ADD_CONTACTS",
    emails: currentPageContacts.emails,
    phones: currentPageContacts.phones,
    source: window.location.href
  });

  // ─── Deep crawl: collect from linked sub-pages ─────────────────
  const crawlSettings = await chrome.storage.local.get(["deepCrawlEnabled"]);
  const deepCrawlEnabled = crawlSettings.deepCrawlEnabled ?? false;

  if (deepCrawlEnabled) {
    const subLinks = getSameDomainLinks();
    if (subLinks.length > 0) {
      const deepContacts = await deepCrawl(subLinks);
      if (deepContacts.emails.length > 0 || deepContacts.phones.length > 0) {
        chrome.runtime.sendMessage({
          type: "ADD_CONTACTS",
          emails: deepContacts.emails,
          phones: deepContacts.phones,
          source: window.location.href + " (deep crawl)"
        });
      }
    }
  }
})();
