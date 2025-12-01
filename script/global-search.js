/* ======================================================
   🌐 全站搜尋控制器（SPA 版本）
   📌 無論你在哪一個載入的子頁，搜尋都會跳回首頁
====================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  // 沒有搜尋欄 → 不處理
  if (!btn || !input) return;

  function goSearch() {
    const keyword = input.value.trim();
    if (keyword) {
      // ⭐ 永遠跳回首頁（不管現在是不是 index/#/）
      window.location.href = `https://taiwangoldfish.github.io/index/?q=${encodeURIComponent(keyword)}`;
    }
  }

  btn.addEventListener("click", goSearch);
  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") goSearch();
  });
});
