# Cline farm — 102 connection FULL PROXY ✅ FINAL
tanggal: 2026-10-15 · 9router mibp :20133 · provider `cline`

## Target tercapai
**102/102 connection cline punya proxy sendiri + strictProxy**, dan rotasi aktif.

| metrik | nilai |
|---|---|
| connection cline total | **102** |
| punya proxy | **102 (100%)** |
| `strictProxy=true` | **102 (100%)** |
| sid unik dipakai | **102** (278377050–278377151, tanpa dobel) |
| strategi rotasi | `round-robin`, `stickyRoundRobinLimit=1` |

Dua connection lama (**`aster`**, **`abelmedika`**) yang tadinya tanpa proxy sekarang juga punya:
- `aster` → sid-278377150
- `abelmedika` → sid-278377151

## 🏆 Hasil uji beban pamungkas
**100 request paralel** (workers=20, model `cl/anthropic/claude-sonnet-4.6`):

| metrik | hasil |
|---|---|
| HTTP status | **100/100 → 200** (100% sukses) |
| **connection berbeda** | **100** (tidak ada yang melayani >1) |
| **proxy berbeda** | **100 (100% unik)** |
| wall | 36,8 s |
| throughput | 2,72 req/s |
| latency | p50 **5,0s** · p95 **10,9s** · max 13,4s |
| `falling back to direct` (kebocoran IP) | **0** ✅ |
| blokir strict 502 | **0** ✅ |

Distribusi merata sempurna: `farm-001 … farm-100` + `aster` + `abelmedika`, masing-masing **1 request**.

## Arsitektur akhir (3 lapis)
1. **Proxy unik** — tiap connection keluar dari IP residential berbeda (102 sid)
2. **strictProxy** — proxy mati = 502, **mustahil bocor ke IP host**
3. **Round-robin** — beban paralel menyebar ke seluruh pool

## Efek praktis
- 100 permintaan serentak = **100 key Cline + 100 IP residential berbeda**
- Kalau satu proxy/key mati → 502 (strict) → failover ke connection lain (IP lain)
- Throughput terukur ~2,7 req/s pada 20 worker; latensi naik tipis karena relay proxy

## Catatan & batas
- Round-robin memilih connection **tanpa melihat status model-lock** secara proaktif — kalau
  banyak connection terkunci untuk 1 model, rotasi akan jatuh ke failover berantai (tetap benar,
  hanya lebih lambat).
- Biaya proxy **per GB**: 100 IP paralel = kuota terpakai jauh lebih cepat daripada 1 IP.
- Patch kode `strictProxy` di 4 chunk tetap berlaku; **hilang kalau image di-rebuild**.
  Re-apply: lihat `PROXY-STRICT-2026-10-15.md`.

## Rollback
```bash
# matikan rotasi (kembali fill-first)
curl -X PATCH :20133/api/settings -d '{"providerStrategies":{}}'

# lepas proxy 2 connection tambahan
PUT /api/providers/{aster_id | abelmedika_id}  {"connectionProxyEnabled": false}
```

## File terkait
- `PROXY-ROLLOUT-2026-10-15.md` — pemasangan proxy 1:1
- `PROXY-STRICT-2026-10-15.md` — bug strictProxy + patch
- `ROTATION-2026-10-15.md` — aktivasi round-robin
- `LIMIT-AUDIT-2026-10-15.md` — uji limit key/rate
