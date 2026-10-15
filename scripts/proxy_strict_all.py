#!/usr/bin/env python3
"""Sanitized helper from the Cline-farm / 9router work.
Credentials removed — supply your own via env or /tmp files as noted in README.
"""
"""Enable strictProxy on ALL 100 proxied farm connections (no host-IP leak possible)."""
import json, sqlite3, sys, urllib.error, urllib.request

MI = "http://127.0.0.1:20133"
DB = "/home/belfara/9router-mibp/data/db/data.sqlite"
COOKIE = open("/tmp/mibp_cookie.txt").read().strip()
APPLY = "--apply" in sys.argv


def api(method, path, payload=None, timeout=40):
    h = {"Content-Type": "application/json", "Cookie": COOKIE}
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(MI + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:180]
    except Exception as e:
        return 0, str(e)[:120]


con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
targets = []
for cid, name, d in con.execute(
        "SELECT id, name, data FROM providerConnections WHERE provider='cline' AND name LIKE 'farm-%' ORDER BY name"):
    p = json.loads(d).get("providerSpecificData", {})
    if p.get("connectionProxyUrl") and p.get("strictProxy") is not True:
        targets.append((cid, name))
con.close()
print("need strictProxy:", len(targets))
if not APPLY:
    print("(dry-run; pass --apply)")
    raise SystemExit(0)

ok = fail = 0
for cid, name in targets:
    st, b = api("PUT", "/api/providers/%s" % cid, {"providerSpecificData": {"strictProxy": True}})
    if st == 200:
        ok += 1
    else:
        fail += 1
        print("  FAIL %s -> %s %s" % (name, st, b[:90]))
print("applied strict: ok=%d fail=%d" % (ok, fail))

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
n = 0
for (d,) in con.execute("SELECT data FROM providerConnections WHERE provider='cline' AND name LIKE 'farm-%'"):
    p = json.loads(d).get("providerSpecificData", {})
    if p.get("connectionProxyUrl") and p.get("strictProxy") is True:
        n += 1
con.close()
print("VERIFY: farm conns with proxy AND strictProxy = %d / 100" % n)
