# Cline 100 keys — LIMIT AUDIT
tanggal: 2026-10-15 · host r5-2600 · instance 9router :20133 (mibp v1.0.18)

## Inventaris
| akun | key di 9router | key di akun Cline (ours/total) |
|---|---|---|
| aster | 38 | 38 / 39 |
| abelmedika | 37 | 37 / 38 |
| belfaranet | 25 | 25 / 28 |
| **total** | **100** | **100 / 105** |

102 cline connection di :20133, semuanya isActive=1.

## Hasil uji limit (semua live, bukan asumsi)

### 1. Tidak ada cap jumlah key per akun
- `POST /api/v1/api-keys` pada abelmedika (sudah 38 key) → mint 3 key lagi **BERHASIL** (200)
- Hitungan naik 38 → 41, ketiga key probe **berhasil dihapus** (cleanup bersih)
- Artinya: mau 200, 500 key pun bisa — tidak ada plafon yang terlihat

### 2. Tidak ada rate limit yang bisa dicapai di volume normal
- **25 key probe** (sample) → 15/15 PONG sebelumnya
- **Burst per-IP**: 5 IP residential berbeda × 15 call sequential = **75 call → 100% HTTP 200, 0× 429**
- **Burst besar**: 40 call sequential pada 1 IP (125 detik) → **40/40 HTTP 200, 0× 429**
- **Paralel**: 4 IP sekaligus × 3 ronde (12 call bersamaan) → **semua 200**
- Header `x-ratelimit-*` **tidak pernah dikirim** upstream
- Kesimpulan: pada volume ini **tidak ada rate limit terukur** — baik per-key maupun per-IP

### 3. Free tier memang flaky (bukan limit kuota)
- `cline-free/mimo-v2.6-flash` → 500 `"empty response content"` ~1 dari 3 panggilan
- Ini **kualitas model**, bukan kuota. Kadang 200, kadang 500 pada key/IP yang sama
- Free models tersedia: step-5-preview, mimo-v2.6-flash, muse-spark-1.3-contributor, solar-mini4

### 4. Biaya
- 215 request tercatat di 9router: **$0.085 (notional)**, 3,35 juta prompt token
- BYOK (bring-your-own-key) → **biaya riil $0**; angka itu hanya estimasi harga Cline

### 5. Tidak ada endpoint kuota publik
`/credits`, `/usage`, `/subscription`, `/limits`, `/rate-limits`, `/me/*`, `/plan` → **semua 404**.
Tidak ada cara membaca sisa jatah — satu-satunya proxy adalah perilaku upstream (poin 2).

## ⚠️ TEMUAN TERPENTING — masalahnya bukan limit, tapi ROUTING

Dari 102 connection, **hanya 4 yang pernah melayani trafik**:

| connection | jumlah request | priority |
|---|---|---|
| `aster` | **205** | 1 |
| `abelmedika` | 4 | 2 |
| `farm-001` | 3 | 1 |
| (1 lain) | 3 | ? |

Artinya 9router memilih connection secara **priority + failover**, **bukan round-robin**:
- Semua trafik dilayani `aster` (prio 1) sampai gagal → baru pindah ke prio berikutnya
- `comboStrategy: "round-robin"` yang ada di build itu **hanya merotasi MODEL di dalam combo**,
  bukan merotasi connection — jadi tidak menyebarkan beban ke 100 key

**Konsekuensi:** 100 key saat ini = **tangga failover**, bukan 100× kapasitas paralel.
Yang bertambah adalah ketahanan (kalau 1 key mati, ada pengganti), bukan throughput.

## Rekomendasi
1. **Kalau tujuannya ketahanan** → kondisi sekarang sudah benar. 100 key = 100 lapis cadangan.
2. **Kalau tujuannya throughput paralel** → perlu mekanisme rotasi connection. Opsi:
   - buat beberapa label/priority berbeda lalu distribusikan manual, atau
   - pecah jadi beberapa combo (tiap combo = 1 akun) dan rotasi di sisi pemanggil, atau
   - pakai proxy per-connection (fitur `proxyPools` ada di build mibp) supaya tiap key keluar dari IP berbeda
3. **Untuk saat ini batas sebenarnya = fair-use Cline**, yang tidak bisa dibaca (poin 5).
   Pemantauan satu-satunya: hitung 429 di usageHistory. Sejauh ini **0 dari 215 request**.
