# UI refresh: design brief and changelog

Scope: visual design, appearance and motion of `apps/web`. No behaviour, data flow, routes, API calls, `types/*` or `lib/*` were changed.

## 1. Design brief

**Direction: "calm career coach".** A quiet, confident product that lowers interview anxiety. Cool, faintly indigo-tinted neutrals; one brand colour (indigo) used sparingly for action and focus; semantic colours for meaning only; generous but not wasteful spacing; motion that explains (something arrived, something is loading) and never performs.

### Principles
1. One brand accent, everything else neutral. Colour carries meaning (success / warning / danger / info), and is never the only signal (icons and text accompany it).
2. Three surface levels: canvas (`background`) < card (`card`) < raised (card + stronger shadow). Borders are subtle; inputs use a stronger border so they pass the 3:1 non-text contrast rule.
3. Type does the hierarchy: Geist Sans with tight tracking on headings (-0.02 to -0.035em), uppercase micro-labels (0.08em tracking) for eyebrows, `tabular-nums` on every number that ticks or compares.
4. Motion is short, eased out, and always optional: it is covered by `prefers-reduced-motion` (CSS block in `globals.css` plus `MotionConfig reducedMotion="user"`). The interview room has no looping decoration.
5. Build primitives once (`components/ui`), apply everywhere.

### Palette (exact values)

| Token | Light | Dark |
|---|---|---|
| `background` (canvas) | `#f7f8fc` | `#0a0c16` |
| `card` | `#ffffff` | `#111426` |
| `secondary` / `muted` (sunken) | `#eef0f8` | `#1a1e35` |
| `foreground` | `#12152a` | `#e9ebf8` |
| `muted-foreground` | `#565d78` | `#9ba2c0` |
| `primary` | `#4338ca` | `#8a93ff` |
| `primary-hover` | `#3730a3` | `#a3aaff` |
| `primary-foreground` | `#ffffff` | `#0a0c16` |
| `accent` (brand tint) / `accent-foreground` | `#eceeff` / `#3730a3` | `#1e2250` / `#b4baff` |
| `border` / `border-strong` | `#dfe3ef` / `#c5cbe0` | `#252a47` / `#353c63` |
| `input` (field border) | `#7f86a3` | `#5b6390` |
| `ring` (focus) | `#4338ca` | `#a3aaff` |
| `destructive` / `-soft` | `#b91c1c` / `#fdeaea` | `#ff8a8a` / `#341517` |
| `success` / `-soft` | `#166534` / `#e3f5ea` | `#4ade80` / `#10281c` |
| `warning` / `-soft` | `#92590a` / `#fcf1d6` | `#fbbf24` / `#2e2410` |
| `info` / `-soft` | `#1d4ed8` / `#e6eefd` | `#7db0ff` / `#14213f` |
| `success-fill` / `warning-fill` / `danger-fill` (bars, rings only) | `#16a34a` / `#d97706` / `#dc2626` | `#4ade80` / `#fbbf24` / `#ff8a8a` |

### Contrast (WCAG 2.x, computed with a script; text needs 4.5, graphics/borders 3.0)

| Pair | Light | Dark |
|---|---|---|
| foreground on canvas | 16.96 | 16.44 |
| foreground on card | 18.00 | 15.37 |
| muted-foreground on canvas | 6.12 | 7.73 |
| muted-foreground on card | 6.50 | 7.23 |
| muted-foreground on secondary (neutral badge) | 5.71 | 6.50 |
| primary-foreground on primary (buttons, user bubble) | 7.90 | 7.15 |
| primary text on card | 7.90 | 8.47 |
| accent-foreground on accent | 8.63 | 8.15 |
| destructive on card / on soft | 6.47 / 5.59 | 8.03 / 7.31 |
| success on card / on soft | 7.13 / 6.29 | 10.46 / 8.98 |
| warning on card / on soft | 5.74 / 5.11 | 10.92 / 9.14 |
| info on card / on soft | 6.70 / 5.75 | 8.27 / 7.22 |
| destructive-foreground on destructive (unread count) | 6.47 | 8.59 |
| input border on card / canvas | 3.60 / 3.39 | 3.15 / 3.37 |
| focus ring on card | 7.90 | 8.47 |
| success-fill / warning-fill / danger-fill on card (graphics) | 3.30 / 3.19 / 4.83 | 10.46 / 10.92 / 8.03 |

`border` / `border-strong` are decorative separators (1.2 to 1.4:1) and never the only boundary of a control.

### Type scale
Geist Sans (body), Geist Mono (code). Page title 1.65rem (1.9rem from `sm`) / 600 / -0.025em; hero 2.6rem / -0.035em; card title 15 to 16px / 600; UI text 14px (`text-sm`) / 1.5 to 1.6; helper text 12px; eyebrow 11 to 12px uppercase 0.08em. Body line-height 1.6, `text-wrap: balance` on headings and `pretty` on paragraphs.

### Space, radius, shadow
Spacing on Tailwind's 4px grid (cards `p-5`, page gutter 16/24px, section gaps 16 to 40px). Radii: controls 10px (`rounded-lg`), cards 14px (`rounded-xl`), large surfaces 18px (`rounded-2xl`), pills full. Elevation `shadow-xs/sm` (cards), `shadow-md` (raised, hover), `shadow-lg` (menus). In dark mode shadows are deeper plus a 1px inner highlight so cards separate from the canvas.

### Motion
Easing `--ease-out: cubic-bezier(0.22, 1, 0.36, 1)`. Durations: hover/press 150 ms, small pops 160 ms, entrances 360 to 440 ms, bars 800 ms, rings 1000 ms. Only `opacity` and `transform` (plus bar width / ring dash) animate. All CSS motion is neutralised by the global reduced-motion block; framer-motion transforms are disabled by `MotionConfig`; the few non-transform framer animations (`CountUp`) check `useReducedMotion()`.

## 2. Changelog

### Design system (new / rewritten)
- `app/globals.css`: tokens (`:root`, `:root.dark`, `@theme inline` mapping, radii, shadows, easing, keyframes in `@theme static`), base typography and a global `:focus-visible` ring, `.field` form-control class (incl. select chevron for both themes), `.skeleton` shimmer, `.stagger` CSS stagger, `.brand-wash`, `.fill-screen` (viewport minus shell chrome), `bar-fill` / `ring-stroke` animations, extended reduced-motion block, print block (no animation or shadows, forced colour printing, `break-inside: avoid` on report sections).
- New primitives in `components/ui`: `Spinner`, `Badge`, `Skeleton` (+ `ListSkeleton`, `FormSkeleton`), `EmptyState`, `PageHeader`, `Alert`, `ProgressBar`, `ScoreRing`, `CountUp`, `score.ts` (tone helpers), `icons.tsx` (inline SVG set), `Logo`, `NavLinks` (active-page highlight, `aria-current`), `AuthShell`.
- Upgraded `Button` (variants: primary, secondary, outline, ghost, danger; sizes sm/md/lg; `loading` with spinner and `aria-busy`), `Card` (`interactive` hover lift, `tone`), `ThemeToggle` (View Transitions cross-fade with a 300 ms safety net, skipped for reduced motion), `NotificationsBell` (SVG bell, pop-in panel), `SignOutButton`, `ServerWakingBanner`, `StubPage`.

### Screens
- Shell: sticky sidebar with logo, icons and active state; sticky blurred header with avatar chip; mobile nav bar with active pill; route entrance via `app/(dashboard)/template.tsx` (fade and rise, 380 ms, CSS only).
- Sign-in / sign-up / account setup / onboarding: new `AuthShell` (brand panel with value props on large screens, centred card, Google icon, divider, step indicator on onboarding). Email fields now carry aria-labels.
- Dashboard home: hero with three quick-start steps and a feature grid (cards now link to their pages).
- Chat list / thread / window: skeletons, empty states, bubbles with avatars and sender labels, typing dots, composer with send icon.
- ATS: form card with real labels, animated composite ring with count-up, tone-coloured sub-score bars, badge chips, requirement list with check/cross icons and an animated disclosure chevron.
- Interviews list, setup (labels, card, themed 3D scene colours, status line), room (single bordered surface, phase and time header with progress bar, "who has the floor" badge, typing bubble while the interviewer replies, calmer voice bar dot, composer, editor panel slides in beside the chat and stacks under it on small screens; Monaco follows the app theme).
- Reports list (mini ring per report) and detail (large ring, tone-coloured skill bars, good/improve cards with markers; print layout unchanged apart from forced colours).
- Resumes (icon rows, status badges, button actions), API keys (provider monogram, connection badge, icons on validation messages, usage card with relative token bars), Team stub, Question Bank (field class, badges, ghost actions, labels on bare selects), Privacy (card sections, logo, theme toggle).

### Deliberately not changed
Everything under `lib/`, `types/`, `app/api/`, all data fetching and handlers, route paths, existing button/aria-label texts. The 3D scene still lazy-loads and still shows nothing for reduced motion.
