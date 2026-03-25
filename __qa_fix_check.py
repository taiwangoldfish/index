from fastapi.testclient import TestClient
from src.api import create_app

c = TestClient(create_app())
for q in ['換水', '換水要怎麼做', '要不要換水']:
    r = c.post('/api/ask', json={'question': q, 'top_k': 5})
    j = r.json()
    print(q, '|', round(j.get('confidence', 0), 3), '|', j.get('conclusion', '')[:70], '| sources', len(j.get('sources', [])))
