async function loadSummary() {
  const res = await fetch('/api/admin/summary');
  if (!res.ok) {
    throw new Error('summary api failed');
  }
  return res.json();
}

function fillList(el, items, ordered = false) {
  el.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '目前無資料';
    el.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    el.appendChild(li);
  });
}

async function render() {
  try {
    const data = await loadSummary();
    document.getElementById('total-asks').textContent = String(data.total_asks);
    document.getElementById('total-feedback').textContent = String(data.total_feedback);
    document.getElementById('up-count').textContent = String(data.up_count);
    document.getElementById('down-count').textContent = String(data.down_count);
    document.getElementById('avg-confidence').textContent = Number(data.avg_confidence).toFixed(2);

    fillList(document.getElementById('top-questions'), data.top_questions, true);
    fillList(document.getElementById('low-confidence'), data.low_confidence_questions);
  } catch (err) {
    document.getElementById('summary-panel').textContent = '讀取摘要失敗';
  }
}

render();
