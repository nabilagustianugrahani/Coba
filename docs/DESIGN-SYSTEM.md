# UGC AI Empire — Design System

Generated via [ui-ux-pro-max skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) v2.5.0

## Two Surfaces

### 1. Landing / Marketing Pages
**Pattern:** Video-First Hero
**Style:** Vibrant & Block-based (Bold, energetic, playful)

**Colors:**
| Role | Hex |
|------|-----|
| Primary | #E11D48 |
| Secondary | #FB7185 |
| CTA | #2563EB |
| Background | #FFF1F2 |
| Text | #881337 |

### 2. Analytics Dashboard (web/dashboard.py)
**Style:** Data-Dense Dashboard (KPI cards, charts, data tables)

**Colors:**
| Role | Hex |
|------|-----|
| Primary | #1E40AF |
| Secondary | #3B82F6 |
| CTA | #F59E0B |
| Background | #F8FAFC |
| Text | #1E3A8A |

## Typography (both surfaces)
- **Headings:** Fira Code (data, code, technical, precise)
- **Body:** Fira Sans

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

## Effects
- Landing: 48px+ gaps, animated patterns, bold hover, scroll-snap, 32px+ type, 200-300ms transitions
- Dashboard: hover tooltips, chart zoom, row highlighting, smooth filter animations

## Avoid (Anti-patterns)
- Heavy skeuomorphism, ornate design, no filtering
- AI purple/pink gradients, bright neon on white
- Emojis as icons (use SVG: Heroicons/Lucide)
- Inaccessible color combinations

## Pre-Delivery Checklist
- [ ] No emojis as icons (use SVG)
- [ ] cursor-pointer on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard nav
- [ ] prefers-reduced-motion respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] Loading states (skeleton, not just spinners)
- [ ] Error states with retry
- [ ] Empty states with helpful guidance

## Notion Dashboard Specific
- **Status colors:** Red #E11D48, Yellow #F59E0B, Green #10B981, Blue #3B82F6
- **Emoji prefix:** Only for category tags, not for visual decoration
- **Page icons:** First letter of category, no emoji
- **Column types:** Status, Date, Number (with formatting), URL, Relation
- **Card density:** Compact view, no decorative dividers
