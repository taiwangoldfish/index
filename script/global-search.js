/* ======================================================
   🌐 子頁搜尋控制器
   在子頁按搜尋 → 導回首頁(index)並附帶 ?q=keyword
====================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  // 子頁無搜尋欄 → 不動作
  if (!btn || !input) return;

  function goSearch() {
    const keyword = input.value.trim();
    if (!keyword) return;

    // 導回首頁 + 帶搜尋參數
    window.location.href =
      `https://taiwangoldfish.github.io/index/?q=${encodeURIComponent(keyword)}`;
  }

  btn.addEventListener("click", goSearch);
  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") goSearch();
  });

});
