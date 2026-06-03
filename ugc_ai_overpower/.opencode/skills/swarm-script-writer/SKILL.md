# Script Writer Agent

## Role
Generates UGC scripts at scale using AI (Gemini/Claude via 9router). Each script follows proven viral templates with platform-specific hooks.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `generate_scripts` | orchestrator | Generate N scripts via parallel AI calls |

## Sends Messages
- `scripts_ready` → orchestrator

## Script Templates
| Template | Angle | Structure |
|----------|-------|-----------|
| `honest_review` | jujur tanpa drama | Hook → Kenalan → First Impression → Dipakai Rutin → Hasil → CTA |
| `storytelling` | cerita personal | Masalah → Ketemu Produk → Pake Pertama → Transformasi → Testimoni → CTA |
| `comparison` | sebelum-sesudah | Hook → Produk A → Produk B → Head to Head → Pemenang → CTA |
| `tutorial_hack` | tips & trik rahasia | Hook Hack → Yang Salah → Cara Bener → Hasil Maksimal → Pro Tip → CTA |
| `challenge` | tantangan X hari | Hook → Day 1 → Day 3 → Day 7 → Hasil Akhir → CTA |
| `myth_busting` | mitos vs fakta | Mitos → Fakta → Bukti → Penjelasan → Kesimpulan → CTA |
| `asmr_unboxing` | ASMR unboxing | Unboxing → Look Pertama → Tekstur → Coba → Reaction → CTA |
| `day_in_life` | daily routine | Pagi → Siang → Sore → Malam → Refleksi → CTA |

## Niche-Specific Hooks
- `skincare`, `fashion`, `food`, `general` — each with tailored hook templates

## Tools
- AI Router (via 9router) — `Gemini 2.5 Flash` or `Claude 3.5 Sonnet`
- ThreadPoolExecutor — parallel script generation (up to 10 workers)
- Regex cleaning pipeline — removes AI preamble, extracts hashtags

## Config
```yaml
max_concurrent: 5
poll_interval: 0.5
default_count: 50
max_workers: 10
fallback_script: "Halo guys! Hari ini gue mau review produk nih!"
```
