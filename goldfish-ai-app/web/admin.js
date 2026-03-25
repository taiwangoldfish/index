async function loadSummary() {
  const res = await fetch('/api/admin/summary');
  if (!res.ok) {
    throw new Error('summary api failed');
  }
  return res.json();
}

async function loadCases(mode) {
  const res = await fetch(`/api/admin/cases?mode=${encodeURIComponent(mode)}&limit=80`);
  if (!res.ok) {
    throw new Error('cases api failed');
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

function renderCaseRows(items) {
  const body = document.getElementById('case-table-body');
  body.innerHTML = '';

  if (!items.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = '目前無案例資料';
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement('tr');

    const c1 = document.createElement('td');
    c1.textContent = (item.timestamp || '').replace('T', ' ').slice(0, 19);
    row.appendChild(c1);

    const c2 = document.createElement('td');
    c2.textContent = item.question || '';
    row.appendChild(c2);

    const c3 = document.createElement('td');
    c3.textContent = Number(item.confidence || 0).toFixed(2);
    row.appendChild(c3);

    const c4 = document.createElement('td');
    c4.textContent = item.rating || '-';
    row.appendChild(c4);

    const c5 = document.createElement('td');
    c5.textContent = item.conclusion || '';
    row.appendChild(c5);

    body.appendChild(row);
  });
}

async function refreshCases() {
  const modeEl = document.getElementById('case-mode');
  const mode = modeEl.value || 'all';
  const csvLink = document.getElementById('download-csv');
  csvLink.href = `/api/admin/cases.csv?mode=${encodeURIComponent(mode)}&limit=200`;

  const data = await loadCases(mode);
  renderCaseRows(data.items || []);
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
    await refreshCases();
  } catch (err) {
    document.getElementById('summary-panel').textContent = '讀取摘要失敗';
  }
}

document.getElementById('refresh-cases').addEventListener('click', () => {
  refreshCases().catch(() => {
    document.getElementById('summary-panel').textContent = '更新案例失敗';
  });
});

render();
