# Notion Dashboard — UGC Empire

## Arsitektur

7 Notion database dengan relasi:

```
Campaigns ──relation──→ Content ──relation──→ Analytics
Gallery       (standalone, slug-based routing)
Inbox         (standalone, platform filter)
Brands        (standalone, active flag)
Approvals     (standalone, status filter)
```

## Endpoints untuk Notion Buttons

Notion Buttons → External URL → API server:

| Button Label | Endpoint | Fungsi |
|---|---|---|
| Sync All Data | `POST /api/v1/notion/sync` | Sync semua database ke Notion |
| Run Campaign | `POST /api/v1/notion/campaign` | Jalanin DAG pipeline campaign |
| Approve Pending | `POST /api/v1/notion/approve-all` | Auto-approve semua pending |
| Generate Trends | `POST /api/v1/notion/trends` | Analisis trending hooks |

## View Layout per Database

| Database | View Type | Default Filter | Sort |
|---|---|---|---|
| Campaigns | Table | Status ≠ Completed | Last Run DESC |
| Content | Gallery | Status ≠ failed | Created DESC |
| Analytics | Table | Date = Today | Engagement Rate DESC |
| Gallery | Gallery | - | Views DESC |
| Inbox | List | Is Read = unchecked | Created DESC |
| Brands | Board | Group by Tone | Active first |
| Approvals | Table | Status = pending_review | Created ASC |

## Formula KPI (Notion Formula)

Dibuat manual di Notion, bukan kode:
- Total views (rollup dari Analytics)
- Approval rate (% approved / total)
- Active campaigns count
- Content generated today
