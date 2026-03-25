from fastapi.testclient import TestClient
from src.api import create_app

c = TestClient(create_app())

r1 = c.post('/api/ask', json={'question':'換水要怎麼做?','top_k':5})
j1 = r1.json()
print('[ASK] status=', r1.status_code)
print('[ASK] confidence=', round(j1.get('confidence', 0), 3))
print('[ASK] conclusion=', j1.get('conclusion', '')[:120])
print('[ASK] sources=', len(j1.get('sources', [])))

r2 = c.get('/api/admin/summary')
j2 = r2.json()
print('[SUMMARY] status=', r2.status_code)
print('[SUMMARY] total_asks=', j2.get('total_asks'))
print('[SUMMARY] avg_confidence=', j2.get('avg_confidence'))
print('[SUMMARY] down_count=', j2.get('down_count'))
print('[SUMMARY] top_questions=', j2.get('top_questions', [])[:3])

r3 = c.get('/api/admin/cases?mode=all')
j3 = r3.json()
items = j3.get('cases', [])
print('[CASES] status=', r3.status_code)
print('[CASES] total=', j3.get('total'))
print('[CASES] has_templates=', bool(items and items[0].get('suggested_templates')))
print('[CASES] first_keywords=', (items[0].get('suggested_keywords') if items else [])[:5])
