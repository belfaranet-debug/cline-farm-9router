# Cline farm — PROXY PER-CONNECTION (opsi 2)
tanggal: 2026-10-15 16:24 · 9router :20133 (mibp v1.0.18)

## Apa yang dikerjakan
Setiap `farm-NNN` connection di 9router diberi **1 proxy residential sendiri** (sticky sid),
supaya tiap key keluar dari **IP berbeda** — bukan menumpuk di IP host r5-2600.

## Mekanisme (dari source mibp, bukan tebakan)
- Field yang dibaca runtime: `providerSpecificData.{connectionProxyEnabled, connectionProxyUrl,
  connectionNoProxy}` + `strictProxy` (`open-sse/handlers/chatCore.js:352-360`)
- Dibangun sebagai undici `ProxyAgent` di `open-sse/utils/proxyFetch.js`
- Diatur lewat `PUT /api/providers/{id}` dengan body `{connectionProxyEnabled, connectionProxyUrl,
  connectionNoProxy, strictProxy}` — nilai di-merge ke `providerSpecificData` (tidak menimpa field lain)
- Ada juga jalur `proxyPoolIds` + `proxyRotationStrategy: round-robin|smart` di build ini (belum dipakai)

## Hasil
| item | hasil |
|---|---|
| Connection cline total | 102 |
| Connection dengan proxy aktif | **100** |
| Proxy unik terpakai | **100** (sid 278377050–278377149, 1:1) |
| Terpasang | `applied: ok=100 fail=0` |
| Bukti di log 9router | `[PROXY] CLINE \| <model> \| conn=farm-001 \| url=http://gw.proxyrise.com:443` |
| Request nyata lewat proxy | **HTTP 200 `PROXYOK`** (farm-001, 2,7s) |
| Request tanpa proxy (aster) | HTTP 200 `PROXYOK` (1,6s) — pembanding |
| Egress berbeda per connection | 4 IP berbeda dari 4 sample |

Sample egress:
- `farm-001` → `103.51.44.105`
- `farm-026` → `180.243.0.184`
- `farm-051` → `103.247.15.146`
- `farm-100` → `182.253.217.84`

## Efek samping yang terbukti dari log
9router **cascade lintas connection** saat satu gagal — log menunjukkan
`farm-002 → farm-031 → farm-032 → farm-033 → farm-034 → farm-035` dicoba berurutan.
Jadi kombinasi proxy-per-connection + cascade = **failover yang juga berganti IP**.

## Catatan jujur
- **Yang berubah:** jalur keluar (egress IP) tiap request. Yang **tidak** berubah: pilihan
  connection tetap **priority + failover** — 100 key bukan 100 permintaan paralel.
- Proxy residential **berbayar per GB** — 100 connection yang semua aktif akan membakar kuota
  bandwidth. Pertimbangkan `--limit` kalau mau sebagian saja.
- Backup state sebelum perubahan: `backup-cline-state-2026-10-15.json` (102 conn, mode 600).
- Rollback: script `proxy_rollout.py` bisa dijalankan ulang; untuk membersihkan, PUT
  `{connectionProxyEnabled: false}` per connection (atau restore dari backup).
