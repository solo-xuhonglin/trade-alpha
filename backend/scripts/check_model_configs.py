"""Check model configs API response."""
import requests

resp = requests.get("http://localhost:8000/api/model-configs")
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Count: {len(data)}")
    for c in data[:3]:
        print(f"  id={c.get('id')}, name={c.get('name')}, type(id)={type(c.get('id'))}")
    if data:
        print(f"\nFull first item: {data[0]}")
