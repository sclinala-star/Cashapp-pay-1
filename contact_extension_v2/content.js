// Content Script — Collects contacts from current page + deep crawls links

(async () => {
  const data = await chrome.storage.local.get(["enabled"]);
  const enabled = data.enabled ?? true;
  if (!enabled) return;

  // ─── Regex patterns ────────────────────────────────────────────
  const EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/gi;
  // USA phone: optional +1 or 1 prefix, then 3-3-4 digit pattern
  // (?<!\d) and (?!\d) prevent matching inside longer digit sequences
  const USA_PHONE_RE = /(?<!\d)(?:\+?1[-.\/\s]?)?(?:\(?\d{3}\)?[-.\/\s]?)\d{3}[-.\/\s]?\d{4}(?!\d)/g;

  // Clean phone number to digits only, normalize to USA format
  function cleanUSAPhone(raw) {
    const digits = raw.replace(/\D/g, "");
    let areaCode;
    if (digits.length === 10) {
      areaCode = digits.substring(0, 3);
    } else if (digits.length === 11 && digits.startsWith("1")) {
      areaCode = digits.substring(1, 4);
    } else {
      return null;
    }
    // US area codes never start with 0 or 1
    if (areaCode[0] === "0" || areaCode[0] === "1") return null;
    const normalized = digits.length === 10 ? "+1" + digits : "+" + digits;
    return normalized;
  }

  // ─── Extract contacts from text ────────────────────────────────
  function extractContacts(text) {
    // Deobfuscate common email hiding patterns
    let cleanText = text
      .replace(/\s*\[at\]\s*/gi, "@")
      .replace(/\s*\(at\)\s*/gi, "@")
      .replace(/\s*\[dot\]\s*/gi, ".")
      .replace(/\s*\(dot\)\s*/gi, ".");

    const emails = [...new Set((cleanText.match(EMAIL_RE) || []))];

    // Extract USA phone numbers
    const rawPhones = cleanText.match(USA_PHONE_RE) || [];
    const phones = [];
    rawPhones.forEach(p => {
      const cleaned = cleanUSAPhone(p);
      if (cleaned) phones.push(cleaned);
    });

    // Also extract WhatsApp USA numbers from wa.me links
    const waRe = /wa\.me\/(\+?1?\d{10,11})/g;
    let match;
    while ((match = waRe.exec(cleanText)) !== null) {
      const cleaned = cleanUSAPhone(match[1]);
      if (cleaned) phones.push(cleaned);
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

    // Also extract from meta tags and input fields
    const metaTags = document.querySelectorAll('meta[content]');
    metaTags.forEach(meta => {
      const content = meta.getAttribute('content') || '';
      if (content.includes('@') || /\d{3}/.test(content)) {
        extraText += ' ' + content;
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
