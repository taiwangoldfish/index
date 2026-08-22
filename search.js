(() => {
  "use strict";

  const SYNONYM_GROUPS = [
    ["混濁", "水霧", "白霧", "霧水", "白濁", "水濁"],
    ["換水", "換缸水", "更換水"],
    ["底吸", "底吸沉馬", "底吸沉水馬達", "沉水馬達", "沉馬"],
    ["打氣", "增氧", "供氧", "氧氣"],
    ["過濾", "濾材", "濾槽", "濾盒"],
    ["硝化菌", "益菌", "菌相"],
    ["白點", "白點病", "小瓜蟲"],
    ["腸炎", "腸胃炎", "拖便", "白便"],
    ["檢疫", "隔離", "新魚入缸"],
    ["餵食", "餵魚", "飼料", "吃食"],
    ["魚缸", "缸子", "水槽"],
    ["金魚", "蘭壽", "泰獅"],
  ];

  let indexPromise;

  function normalize(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFKC")
      .replace(/[，。！？、；：,.!?;:()（）【】「」『』\-_\/\\]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function compact(value) {
    return normalize(value).replace(/\s/g, "");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"
    })[character]);
  }

  function editDistance(left, right) {
    if (Math.abs(left.length - right.length) > 1) return 2;
    const row = Array.from({ length: right.length + 1 }, (_, index) => index);
    for (let i = 1; i <= left.length; i += 1) {
      let diagonal = row[0];
      row[0] = i;
      let best = row[0];
      for (let j = 1; j <= right.length; j += 1) {
        const previous = row[j];
        row[j] = Math.min(row[j] + 1, row[j - 1] + 1, diagonal + (left[i - 1] === right[j - 1] ? 0 : 1));
        diagonal = previous;
        best = Math.min(best, row[j]);
      }
      if (best > 1) return 2;
    }
    return row[right.length];
  }

  function approximatelyIncludes(text, term) {
    if (term.length < 2 || text.length < term.length - 1) return false;
    for (let index = 0; index <= text.length - term.length; index += 1) {
      if (editDistance(term, text.slice(index, index + term.length)) <= 1) return true;
    }
    return false;
  }

  function queryTerms(query) {
    const original = normalize(query).split(" ").filter(Boolean);
    return original.flatMap((term) => {
      const group = SYNONYM_GROUPS.find((items) => items.some((item) => compact(item) === compact(term)));
      return [{ value: compact(term), original: true }].concat(
        (group || []).filter((item) => compact(item) !== compact(term)).map((item) => ({ value: compact(item), original: false }))
      );
    });
  }

  async function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch("./search-index.json", { cache: "force-cache" }).then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      });
    }
    return indexPromise;
  }

  function scorePage(page, query) {
    const exact = compact(query);
    const terms = queryTerms(query);
    const title = compact(page.title);
    const headings = compact((page.headings || []).join(" "));
    const description = compact(page.description);
    const body = compact(page.content);
    let score = 0;
    const matched = [];

    if (title === exact) score += 1000;
    else if (title.includes(exact)) score += 620;
    if (headings.includes(exact)) score += 360;
    if (description.includes(exact)) score += 260;
    if (body.includes(exact)) score += 160;

    const originalTerms = terms.filter((term) => term.original);
    for (const term of originalTerms) {
      let termScore = 0;
      if (title.includes(term.value)) termScore = 240;
      else if (headings.includes(term.value)) termScore = 150;
      else if (description.includes(term.value)) termScore = 100;
      else if (body.includes(term.value)) termScore = 55;
      if (termScore) matched.push(term.value);
      score += termScore;
    }

    if (originalTerms.length > 1 && matched.length < originalTerms.length) return null;

    if (!score) {
      const synonym = terms.find((term) => !term.original && (title.includes(term.value) || headings.includes(term.value) || description.includes(term.value) || body.includes(term.value)));
      if (synonym) {
        score = title.includes(synonym.value) ? 185 : headings.includes(synonym.value) ? 120 : 65;
        matched.push(synonym.value);
      }
    }

    if (!score && exact.length >= 2) {
      const importantText = compact(`${page.title} ${(page.headings || []).join(" ")}`);
      if (approximatelyIncludes(importantText, exact)) score = 75;
    }

    return score ? { ...page, score, matched: [...new Set([...originalTerms.map((term) => term.value), ...matched])] } : null;
  }

  function createSnippet(page, terms) {
    const source = page.description || page.content || "";
    const normalizedSource = compact(source);
    const matchedTerm = terms.find((term) => normalizedSource.includes(term));
    const rawIndex = matchedTerm ? normalize(source).indexOf(matchedTerm) : 0;
    const start = Math.max(0, rawIndex - 38);
    let snippet = source.slice(start, start + 115).trim();
    if (start > 0) snippet = `…${snippet}`;
    if (start + 115 < source.length) snippet += "…";
    let highlighted = escapeHtml(snippet);
    for (const term of [...terms].sort((left, right) => right.length - left.length)) {
      const escapedTerm = escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (escapedTerm) highlighted = highlighted.replace(new RegExp(escapedTerm, "gi"), (match) => `<mark>${match}</mark>`);
    }
    return highlighted;
  }

  function renderResults(area, query, results) {
    if (!results.length) {
      area.innerHTML = `<div class="search-summary"><h2>找不到「${escapeHtml(query)}」</h2><p>可以縮短關鍵字，或試試「換水」、「白點」、「過濾」、「檢疫」。</p></div>`;
      return;
    }

    area.innerHTML = `
      <div class="search-summary">
        <div><span class="search-kicker">知識庫搜尋</span><h2>「${escapeHtml(query)}」找到 ${results.length} 筆</h2></div>
        <button class="search-clear" type="button">清除結果</button>
      </div>
      <ul class="search-list">
        ${results.slice(0, 30).map((page) => `
          <li>
            <a href="${escapeHtml(page.url)}">
              <span class="search-category">${escapeHtml(page.category)}</span>
              <strong>${escapeHtml(page.title)}</strong>
              <span class="search-snippet">${createSnippet(page, page.matched)}</span>
              <span class="search-open">閱讀文章 →</span>
            </a>
          </li>`).join("")}
      </ul>`;
    area.querySelector(".search-clear")?.addEventListener("click", () => {
      area.style.display = "none";
      area.innerHTML = "";
      document.getElementById("searchInput")?.focus();
      history.replaceState(null, "", window.location.pathname);
    });
  }

  async function runSearch() {
    const input = document.getElementById("searchInput");
    const area = document.getElementById("searchResults");
    const query = input?.value.trim();
    if (!input || !area || !query) return;

    area.style.display = "block";
    area.setAttribute("aria-live", "polite");
    area.innerHTML = '<p class="search-loading">🔍 正在搜尋金魚知識…</p>';
    document.getElementById("sidebar")?.classList.remove("active");

    try {
      const pages = await loadIndex();
      const results = pages.map((page) => scorePage(page, query)).filter(Boolean)
        .sort((left, right) => right.score - left.score || left.title.length - right.title.length);
      renderResults(area, query, results);
      history.replaceState(null, "", `${window.location.pathname}?q=${encodeURIComponent(query)}`);
    } catch (error) {
      area.innerHTML = '<p class="search-error">搜尋資料暫時無法載入，請重新整理後再試一次。</p>';
      console.error("Search index error:", error);
    }
    area.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("searchInput");
    const button = document.getElementById("searchBtn");
    if (!input || !button) return;

    button.addEventListener("click", runSearch);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearch();
      }
    });

    const query = new URLSearchParams(window.location.search).get("q");
    if (query) {
      input.value = query;
      runSearch();
    }
  });
})();
