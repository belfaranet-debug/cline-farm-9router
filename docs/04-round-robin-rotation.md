# Cline farm — ROTASI CONNECTION (round-robin) ✅ SELESAI
tanggal: 2026-10-15 · 9router :20133 (mibp v1.0.18) · provider `cline`

## Masalah yang diselesaikan
Sebelumnya strategi default **`fill-first`**: semua request dilayani connection **prioritas pertama**
(`farm-001` → 12/12 request). Jadi 100 key itu **tangga failover**, bukan kapasitas paralel.

## Akar masalah (dari source)
`src/sse/services/auth.js`:
```js
const strategy = providerOverride.fallbackStrategy || settings.fallbackStrategy || "fill-first";
...
} else {
  // Default: fill-first (already sorted by priority in getProviderConnections)
  connection = availableConnections[0];
}
```
Setting disimpan di **`providerStrategies`** (`settings` id=1, JSON), dibaca sebagai
`(settings.providerStrategies || {})[providerId]`.

## Cara mengaktifkan (tanpa UI)
```bash
PATCH /api/settings
{"providerStrategies": {"cline": {"fallbackStrategy": "round-robin", "stickyRoundRobinLimit": 1}}}
```
Catatan penting:
- Kunci yang dibaca runtime = **`providerStrategies`** (bukan `providerOverrides` — itu khusus header).
- `stickyRoundRobinLimit: 1` = ganti connection **setiap request**. Nilai lebih besar = bertahan
  sekian request sebelum pindah (mis. 3 = seperti default UI).
- UI memakai path yang sama (`ConnectionsCard.js` → `PATCH /api/settings`).

## Hasil verifikasi
| uji | sebelum (fill-first) | sesudah (round-robin) |
|---|---|---|
| 12 paralel | 1 connection (farm-001), 1 IP | **12 connection, 11 proxy berbeda** |
| 30 paralel | — | **30 connection, 30 proxy unik (100%)** |
| status HTTP | 12/12 → 200 | 12/12 & 30/30 → **200** |
| throughput 30 req | — | wall ~? detik, semua sukses |

⚠️ Dua connection lama (**`aster`** & **`abelmedika`**) tidak punya proxy → ikut terpilih dalam rotasi
(tanpa pelanggaran strict, karena memang tanpa proxy). Kalau mau 100% egress residential,
nonaktifkan keduanya atau beri proxy juga.

## Efek kumulatif (proxy + strict + rotasi)
1. Tiap request keluar dari **IP residential berbeda** (rotasi connection).
2. Kalau proxy connection itu mati → **502 (strict)** → tidak bocor → rotasi/failover lanjut ke
   connection berikutnya (IP lain lagi).
3. Beban paralel benar-benar **menyebar ke banyak key** (30 paralel = 30 key), selama kuota
   per-akun mengizinkan.

## Rollback
```bash
PATCH /api/settings {"providerStrategies": {}}     # kembali ke fill-first global
```
atau `{"cline": {"fallbackStrategy": "fill-first"}}`.

## Catatan
- Setting ini **persisten di DB**, aman lewat restart.
- Semua perubahan kode (strictProxy patch di 4 chunk) tetap berlaku.
- Biaya: 30 IP residential paralel = 30× pemakaian bandwidth per gelombang.
