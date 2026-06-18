import requests
import json

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
if response.status_code == 200:
    data = response.json()
    print(f"Title: {data.get('title')}")
    cov = data.get('probe_coverage', {})
    print(f"Coverage rate: {cov.get('coverage_rate')}%")
    print(f"Total targets: {cov.get('total_targets')}")
    print(f"Active targets: {cov.get('active_targets')}")
    print(f"Fully covered: {cov.get('fully_covered')}")
    print(f"Partially covered: {cov.get('partially_covered')}")
    print(f"Not covered: {cov.get('not_covered')}")
    print(f"Paused targets: {cov.get('paused_targets')}")
else:
    print(f"Error: {response.text}")
