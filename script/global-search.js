/* ======================================================
   🌐 全站搜尋控制器
   ⚠️ 功能：子頁搜尋 → 導回首頁
   ⚠️ 不干擾首頁的搜尋功能
====================================================== */

document.addEventListener("DOMContentLoaded", () => {

  // 判斷是否在首頁
  const isHome = window.location.pathname.includes("/index");

  // 首頁不處理（讓 index.html 的搜尋邏輯負責）
  if (isHome) return;

  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  // 子頁沒有搜尋欄就不處理
  if (!btn || !input) return;

  function goSearch() {
    const keyword = input.value.trim();
    if (keyword) {
      window.location.href = `https://taiwangoldfish.github.io/index/?q=${encodeURIComponent(keyword)}`;
    }
  }

  btn.addEventListener("click", goSearch);

  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") goSearch();
  });

});
