# Upgrade & compatibility — make a fresh install behave correctly

This file documents the problems we hit running the **mibp** 9router fork
(`mhiqrambg/9router-mibp-version`, v1.0.18) with **per-connection residential
proxies**, and the fix path that makes a new installation work out of the box.

Short version: **on the old build you must patch the code, otherwise a failing
proxy silently leaks requests out of the server's own IP.** Newer builds accept
`strictProxy` directly on a proxy pool; use the route selectable at the bottom to
avoid patching entirely.

---

## 1. Symptom

Everything looks configured: each connection has its own proxy URL, requests
succeed, dashboards are green. But when a proxy dies you see this in the logs and
the request still returns HTTP 200:

```
[ProxyFetch] Proxy failed, falling back to direct: fetch failed
```

That "direct" is the **server's own IP**. The proxy layer you paid for is
bypassed, and (if you rotate IPs to avoid per-IP rate limits) every failure
quietly spends budget on the one IP you were trying to protect.

## 2. Root cause

`src/lib/network/connectionProxy.js`, legacy per-connection branch:

```js
if (legacy.connectionProxyEnabled && legacy.connectionProxyUrl) {
  return {
    source: "legacy",
    proxyPoolId: proxyPoolIdRaw || null,
    proxyPool: null,
    strictProxy: poolStrictProxy,   // <-- always false here
    ...legacy,
  };
}
```

`poolStrictProxy` is only ever true for the **proxy-pool** branch. On the
per-connection ("legacy") branch it is `false`, so the `strictProxy` value stored
in `providerSpecificData` is **discarded**. Because `strictProxy === false`, the
fetch layer treats a proxy failure as recoverable and falls back to a direct
connection instead of failing the request.

Secondary trap: the PUT handler does not read `strictProxy` as a top-level body
field — it is only accepted inside `providerSpecificData` (which is merged, so
other fields survive).

## 3. Fix — option A: patch the code (old builds)

```bash
git clone https://github.com/mhiqrambg/9router-mibp-version.git
cd 9router-mibp-version
git apply /path/to/0001-strict-proxy-legacy-connections.patch
```

The patch changes exactly one line:

```diff
-        strictProxy: poolStrictProxy,
+        strictProxy: providerSpecificData?.strictProxy === true || poolStrictProxy,
```

### ⚠️ In a built/containerised deployment you must patch the compiled bundle too

Next.js duplicates this module across several chunks. Patching only the source
tree is **inert** for a running container. Find every copy and patch it:

```bash
docker exec <container> sh -c "grep -rlF 'strictProxy:o' /app/.next/server --include='*.js' | grep -v '\.orig$'"
# expected on 1.0.18: chunks/5092.js, 2549.js, 8416.js, 4252.js
```

Then replace the minified expression in **each** file (back up first):

```
old: strictProxy:o,...l}
new: strictProxy:!0===a.strictProxy||o,...l}
```

(here `a` is the minifier's name for `providerSpecificData` in that scope — verify
with `grep -o '.\{80\}strictProxy:o,...l}' <chunk>` before editing.)

Then restart the container. Verify it took effect — a broken proxy must produce a
**502**, not a 200:

```
[502] [ProxyFetch] Proxy required but failed (strictProxy=true): fetch failed
[FALLBACK] <conn> UNAVAILABLE (502) -> NEXT ACCOUNT
```

**This patch does not survive an image rebuild.** Keep it in your deploy script
or use option B.

## 4. Fix — option B: use a proxy pool (canonical, no patching)

The pool branch already honours its own flag:

```js
return {
  source: "pool",
  proxyPoolId: selectedPoolId,
  proxyPool,
  connectionProxyEnabled: true,
  connectionProxyUrl: proxyUrl,
  connectionNoProxy: noProxy,
  strictProxy: proxyPool.strictProxy === true,   // works as intended
};
```

So instead of editing code, register proxies as **pools** and point connections at
them:

```bash
# 1) create a pool with strictProxy set on the pool itself
POST /api/proxy-pools
{ "name": "residential-01", "proxyUrl": "http://user:pass@host:port",
  "type": "http", "isActive": true, "strictProxy": true }

# 2) attach it to a connection
PUT /api/providers/{connectionId}
{ "proxyPoolIds": ["<poolId>"], "proxyRotationStrategy": "none" }
```

`proxyRotationStrategy` accepts `none` or `smart` (`smart` is used for a special
freebuff scope). Multi-pool rotation exists via `proxyPoolIds[]` — verify behaviour
on your build before relying on it.

Trade-off: pools are shared objects, so "one proxy per connection" becomes
"many small pools", and per-connection identity (one sticky session id per
connection) must be modelled as separate pools.

## 5. Verify either fix

```bash
# a broken proxy must fail closed, never escape to the host IP
docker logs --since 5m <container> | grep -c "falling back to direct"   # expect: 0

# during a load test, every dispatch line must carry the proxy
docker logs --since 5m <container> | grep "\[PROXY\]" | head
# [PROXY] CLINE | <model> | conn=<name> | pool=none | url=http://<proxy-host>:443
```

`scripts/` in this repo contains sanitized helpers for the whole setup
(`proxy_rollout.py`, `proxy_strict_all.py`, `rotation_enable.py`,
`loadtest_100.py`).

## 6. Other incompatibilities observed on the old build

| # | Symptom on old install | Cause | Fix |
|---|---|---|---|
| 1 | Strict proxy silently ignored; requests leak to host IP | `strictProxy` dropped on the legacy per-connection branch | Patch (option A) or use pools (option B) |
| 2 | `strictProxy: true` saved but has no effect | PUT handler only accepts it inside `providerSpecificData` (merged) | Send it nested, e.g. `{"providerSpecificData":{"strictProxy":true}}` |
| 3 | Patch applied to source but behaviour unchanged | Next.js duplicates the module across several `.next/server/chunks/*.js` | Patch **all** copies, then restart |
| 4 | All traffic served by one connection; 100 keys idle | Default selection strategy is `fill-first` (`availableConnections[0]`) | `PATCH /api/settings` → `{"providerStrategies":{"<provider>":{"fallbackStrategy":"round-robin","stickyRoundRobinLimit":1}}}` |
| 5 | Strategy set but ignored | Written to `providerOverrides` — that setting only carries **headers**; the runtime reads `providerStrategies` | Use `providerStrategies` |
| 6 | Fixed at runtime but broken again after deploy | Compiled-chunk patches are not part of the image | Keep patch in the build, or use option B |

## 7. Reference deployment (what "normal" looked like here)

- 102 Cline connections, each with its own sticky residential proxy
- `strictProxy: true` on all 102
- `providerStrategies.<provider>.fallbackStrategy = round-robin`, `stickyRoundRobinLimit: 1`
- 100 parallel requests → **100/100 HTTP 200 · 100 distinct connections · 100 distinct proxies · 0 direct-IP fallbacks**
- throughput 2.72 req/s, latency p50 5.0s / p95 10.9s

See `docs/` for the individual reports and the full measurements.
