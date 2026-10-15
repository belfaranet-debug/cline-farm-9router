# Cline farm — proxy per-connection + STRICT (final)
tanggal: 2026-10-15 · 9router :20133 (mibp v1.0.18, container `9router-mibp`)

## Ringkasan
100 `farm-NNN` connection punya **proxy residential sendiri** (1:1, sid 278377050–278377149)
**dan** `strictProxy=true`, sehingga request **tidak mungkin bocor ke IP host** kalau proxy mati.

## Bug yang ditemukan & diperbaiki (penting)
**`strictProxy` dibuang untuk proxy per-connection (jalur "legacy").**

- `src/lib/network/connectionProxy.js` baris ~235 mengembalikan `strictProxy: poolStrictProxy`
  (variabel yang **selalu false** untuk proxy per-connection, hanya true untuk proxy-pool).
- Akibatnya request yang proxy-nya gagal **jatuh ke IP langsung host**:
  log `[ProxyFetch] Proxy failed, falling back to direct: fetch failed`.
- Dua jalur perbaikan:
  1. **Data**: PUT `/api/providers/{id}` dengan `{"providerSpecificData":{"strictProxy":true}}`
     — body di-merge, jadi `strictProxy` bisa disimpan tanpa menyentuh field lain.
     (Catatan: `strictProxy` **tidak** dibaca sebagai field tingkat-atas oleh handler PUT.)
  2. **Kode**: patch baris legacy agar menghormati flag:
     `strictProxy: providerSpecificData?.strictProxy === true || poolStrictProxy`
     → compiled chunk: `strictProxy:o` → `strictProxy:!0===a.strictProxy||o`
     (build mibp menduplikasi modul ini di **4 chunk**: 5092, 2549, 8416, 4252 — semuanya dipatch,
     backup `.orig` dibuat per file)

## Hasil verifikasi
| uji | hasil |
|---|---|
| strictProxy di 100 farm conn | **100/100** (3 → 1 → 99 di-apply, `ok=99 fail=0`) |
| Proxy terpasang | **100** sid unik, 1:1 |
| Load 12 paralel (strict ON) | **12/12 HTTP 200**, wall 13,8s |
| `falling back to direct` saat load | **0 kali** |
| Semua baris `[PROXY]` pakai proxy | **ya** (`gw.proxyrise.com`) |
| Proxy sengaja dirusak + strict | **502** `Proxy required but failed (strictProxy=true)` → **TIDAK bocor** |
| Setelah 502 | `[FALLBACK] farm-001 UNAVAILABLE (502) → NEXT ACCOUNT` → dilayani connection lain |

## Efeknya
Sebelum patch: 1 proxy mati = request keluar dari **IP host r5-2600** (bisa memicu rate-limit/ban IP
dan mengkhianati tujuan "residential relay").
Sesudah patch: proxy mati = **request gagal** → 9router **cascade ke connection lain** (proxy lain).
Jadi failover sekarang = **pindah IP juga**, bukan bocor.

## ⚠️ Catatan
- Masih **priority + failover**, bukan 100 paralel. Beban paralel tetap menumpuk di connection
  prioritas pertama (terbukti: 12/12 dilayani `farm-001`).
- Patch **tidak hilang saat restart** container (bukan image, langsung di file chunk), tapi
  **hilang kalau image di-rebuild/pull ulang**. Simpan catatan ini untuk re-apply.
- Backup: `chunks/<n>.js.orig` di dalam container; state DB: `backup-cline-state-2026-10-15.json`.
- Proxy residential **bayar per GB** — 100 conn aktif = kuota terpakai lebih cepat.

## Rollback
- Kode: `docker exec 9router-mibp cp /app/.next/server/chunks/<n>.js.orig /app/.next/server/chunks/<n>.js` → restart
- Data: PUT `{"connectionProxyEnabled": false}` per connection, atau restore dari backup JSON
