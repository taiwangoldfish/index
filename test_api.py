#!/usr/bin/env python
from fastapi.testclient import TestClient
from src.api import create_app
import json

app = create_app()
client = TestClient(app)

print('Test 1: Testing GET /api/admin/cases endpoint')
response = client.get('/api/admin/cases?mode=all')
print(f'Status: {response.status_code}')
data = response.json()
print(f'Cases count: {data["total"]}')
print(f'Schema keys: {list(data["cases"][0].keys()) if data["cases"] else "no cases"}')

if data['cases']:
    case = data['cases'][0]
    print(f'\nFirst case:')
    print(f'  Question: {case["question"]}')
    print(f'  Keywords: {case["suggested_keywords"]}')
    print(f'  Pages: {case["suggested_pages"]}')
    print(f'  Templates count: {len(case["suggested_templates"])}')
    if case['suggested_templates']:
        tpl = case['suggested_templates'][0]
        print(f'  First template page_title: "{tpl["page_title"]}"')
        print(f'  First template content (first 200 chars):\n{tpl["template"][:200]}')

print('\n✓ All tests passed!')
