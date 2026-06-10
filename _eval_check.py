import urllib.request, json

def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8021" + path) as r:
        return json.load(r)

print("=== TARGETS ===")
for t in get("/api/targets"):
    print(f"id={t['id']} name={t['name'][:20]:22} status={t['status']:9} cascade={t['cascade_affected']} src={t['cascade_source_name']} paused={t['paused']}")

print("=== DEPS ===")
for d in get("/api/dependencies"):
    print(f"id={d['id']} {d['upstream_id']}->{d['downstream_id']} {d['description']}")
