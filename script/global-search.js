/* ======================================================
   🌐 全站搜尋控制器（子頁按搜尋 → 回首頁顯示結果）
   放在：https://taiwangoldfish.github.io/script/global-search.js
====================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  // 子頁沒有搜尋欄就不處理
  if (!btn || !input) return;

  /* ------------------------------------------------------
     🔍 子頁搜尋動作 → 導回首頁 & 帶搜尋關鍵字
  ------------------------------------------------------ */
  function goSearch() {
    const keyword = input.value.trim();
    if (keyword) {
      // 跳回首頁並將關鍵字放入 URL
      window.location.href = `https://taiwangoldfish.github.io/index/?q=${encodeURIComponent(keyword)}`;
    }
  }

  // 點按鈕搜尋
  btn.addEventListener("click", goSearch);

  // 按 Enter 搜尋
  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") goSearch();
  });

});
