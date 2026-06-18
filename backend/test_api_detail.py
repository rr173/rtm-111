import requests

response = requests.post(
    "http://localhost:8000/api/compliance-reports/generate",
    headers={
        "Content-Type": "application/json",
        "X-User": "test_user"
    },
    json={
        "start_time": "2026-06-17T00:00:00",
        "end_time": "2026-06-18T23:59:59"
    }
)

print(f"Status: {response.status_code}")
data = response.json()
print(f"Report ID: {data.get('id')}")
print(f"Probe coverage keys: {list(data.get('probe_coverage', {}).keys())}")
print(f"Probe coverage: {data.get('probe_coverage')}")
