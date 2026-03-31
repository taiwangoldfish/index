const API_BASE = (window.GOLDFISH_API_BASE || '').replace(/\/$/, '');

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

async function loadSummary() {
  const res = await fetch(apiUrl('/api/admin/summary'));
  if (!res.ok) {
    throw new Error('summary api failed');
  }
  return res.json();
}

async function loadCases(mode = 'all') {
  const res = await fetch(apiUrl(`/api/admin/cases?mode=${encodeURIComponent(mode)}`));
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

function renderTemplates(templates) {
  if (!templates || templates.length === 0) {
    return '<p style="color: #999;">無建議補充</p>';
  }
  
  let html = '<div class="templates-list">';
  templates.forEach((tpl, idx) => {
    html += `
      <details class="template-item" ${idx === 0 ? 'open' : ''}>
        <summary class="template-header">
          <span class="page-label">${tpl.page_title}</span>
          <span class="keywords">${tpl.keywords.join('、')}</span>
        </summary>
        <div class="template-content">
          <pre>${escapeHtml(tpl.template)}</pre>
          <a href="${tpl.page_url}" target="_blank" class="page-link">編輯頁面 →</a>
        </div>
      </details>
    `;
  });
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

function renderCaseItem(caseData) {
  const timestamp = new Date(caseData.timestamp).toLocaleString('zh-TW');
  const confidenceColor = caseData.confidence < 0.35 ? '#e74c3c' : '#27ae60';
  const ratingIcon = caseData.rating === 'up' ? '👍' : caseData.rating === 'down' ? '👎' : '—';
  
  return `
    <article class="case-item">
      <div class="case-header">
        <div class="case-meta">
          <strong>${escapeHtml(caseData.question)}</strong>
          <span class="timestamp">${timestamp}</span>
        </div>
        <div class="case-stats">
          <span class="confidence" style="border-color: ${confidenceColor}; color: ${confidenceColor};">
            信心: ${(caseData.confidence * 100).toFixed(0)}%
          </span>
          <span class="rating">${ratingIcon}</span>
        </div>
      </div>
      
      <div class="case-keywords">
        <strong>抽取關鍵詞：</strong>
        ${caseData.suggested_keywords.length > 0 
          ? caseData.suggested_keywords.map(k => `<span class="keyword-tag">${k}</span>`).join('')
          : '<span style="color:#999;">無</span>'}
      </div>
      
      <div class="case-templates">
        <strong>建議補強段落：</strong>
        ${renderTemplates(caseData.suggested_templates)}
      </div>
      
      ${caseData.comment ? `<div class="case-comment"><strong>編輯備註：</strong> ${escapeHtml(caseData.comment)}</div>` : ''}
    </article>
  `;
}

async function renderCases(mode = 'all') {
  const container = document.getElementById('cases-container');
  try {
    const data = await loadCases(mode);
    if (data.total === 0) {
      container.innerHTML = '<p style="padding: 20px; color: #999; text-align: center;">無資料</p>';
      return;
    }
    
    container.innerHTML = data.cases.map(c => renderCaseItem(c)).join('');
  } catch (err) {
    container.innerHTML = `<p style="padding: 20px; color: #e74c3c;">讀取失敗: ${err.message}</p>`;
  }
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
    
    // Load cases with default mode
    await renderCases('all');
  } catch (err) {
    document.getElementById('summary-panel').textContent = '讀取摘要失敗';
  }
}

// Setup filter buttons
document.addEventListener('DOMContentLoaded', () => {
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', async (e) => {
      // Update active state
      filterBtns.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      
      // Load cases with new mode
      const mode = e.target.dataset.mode;
      await renderCases(mode);
    });
  });
  
  render();
});
