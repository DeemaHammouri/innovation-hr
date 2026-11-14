# Innovation: design system

Calm, confident, Apple-like, in blue. An iOS-style kit translated to a serious accounting back office.
Light theme only. Every value below is a token in `src/app/globals.css` (`@theme`). Components use the token
classes (`bg-surface`, `text-ink-2`, `rounded-card`, `text-body`). No hex, px or ms literals in components.

## Colour (60-30-10)

Neutrals dominate (60), navy gives structure (30), blue is only for primary actions, active states, links and the focus ring (10).
No purple, no rainbow, no decorative gradients, no glassmorphism on cards.

| Token | Value | Use |
|---|---|---|
| `primary` | #007AFF | iOS system blue: focus ring, active indicator, language thumb, fill icons, chart bars |
| `primary-strong` | #0A6BE0 | Button fill and link text (see contrast note) |
| `primary-hover` / `primary-press` | #0958BD / #084A9E | Hover / pressed for `primary-strong` |
| `primary-tint` / `primary-line` | #E8F1FF / #CFE2FF | Selected rows, tinted chips, tint borders |
| `navy` / `navy-2` | #0B1F44 / #12295A | Sidebar, login panel / hover and active on navy |
| `on-navy` / `on-navy-muted` | #E6ECF7 / #9FB0CC | Text on navy |
| `canvas` / `surface` / `line` | #F4F6FA / #FFFFFF / #E3E8F0 | App background, cards, hairline borders |
| `ink` / `ink-2` / `ink-3` | #0F1B33 / #5B6B85 / #8A97AD | Primary, secondary, tertiary text (`ink-3` is decorative only: icons, disabled) |
| `success` `warning` `danger` `neutral` | #1F9D55 #B7791F #D92D20 #5B6B85 | Status dots, icons |
| `*-bg` | #E6F6EC #FFF4DB #FDECEA #EEF1F6 | Status pill backgrounds |
| `*-ink` | #17753F #8F5B0F #B42318 #5B6B85 | Status pill text (see contrast note) |

### Contrast notes (WCAG AA, measured)

- White on `#007AFF` is 4.0:1, below 4.5 for 15px text. So buttons and link text use `primary-strong` #0A6BE0 (5.0:1). `#007AFF` stays on non-text UI (ring, indicator, thumb, 3:1 is enough).
- Status text on the brief's tints is 3.1 to 4.2:1, so pill text uses the darker `*-ink` values (5.2 to 6.1:1). The brief's colours are kept for dots, icons and backgrounds.
- `ink-3` is 2.9:1. It is never used for text a person must read; hints use `ink-2`.

## Shape and depth

| Token | Value | Use |
|---|---|---|
| `rounded-control` | 12px | Inputs, buttons, menu items |
| `rounded-card` | 16px | Cards, inset lists |
| `rounded-sheet` | 20px | Sheets, modals, palette |
| `rounded-full` | pill | Avatars, pills, segmented control |

Elevation: hairline border first (`border border-line`). `shadow-float` (0 1px 2px rgba(15,27,51,.06), 0 8px 24px rgba(15,27,51,.06)) only on floating layers: menus, sheets, palette, toasts.
The sticky top bar uses a light backdrop blur. Cards and panels never do.

## Typography

Manrope (Latin, 400/500/600/700) and IBM Plex Sans Arabic (arabic subset only, 400/500/600/700) through `next/font`.
`lang=en`: Manrope, system-ui. `lang=ar`: IBM Plex Sans Arabic, then Manrope (so emails and names in Latin use Manrope), system-ui.
Numerals are Western (0-9) in both languages, with tabular figures in tables and figures (`.tnum`).

| Class | English | Arabic (+1px, 1.7 body line height) | Weight |
|---|---|---|---|
| `text-large-title` | 32/40 | 33/44 | 700 |
| `text-title` | 24/32 | 25/36 | 700 |
| `text-section` | 18/26 | 19/30 | 600 |
| `text-body` | 15/24 | 16/27 | 400 |
| `text-label` | 13/20 | 14/22 | 600 |
| `text-caption` | 12/16 | 13/20 | 500 |

At most two weights per screen region. No letter-spacing on Arabic.

## Spacing

4/8pt rhythm: Tailwind's default scale (1 = 4px). Page gutter 16px (mobile) / 32px (desktop). Card padding 20px (`p-5`), 24px on desktop. Gap between cards 16 to 24px. Icon-to-text gap 8px (`gap-2`).
Touch targets 44px on mobile, controls 40px on desktop (`h-10`; inputs 44px).

## Icons

Phosphor (`@phosphor-icons/react`). `regular` when idle, `fill` when active or selected (SF Symbols behaviour).
Sizes: 20px in nav and buttons, 16px inline, 24px in empty states. Icon-only buttons are 40px square (44px on touch) with tooltip and `aria-label`.
Only directional icons flip in RTL (arrows, chevrons, back): `rtl:-scale-x-100`. Never search, gear, user, globe, check, plus.

## Motion

| Token | Value | Use |
|---|---|---|
| `--dur-fast` | 120ms | Hover, press |
| `--dur-base` | 180ms | Toggles, language thumb |
| `--dur-slow` | 240ms | Sheets, sidebar mirroring |
| `--ease-out` / `--ease-in` | cubic-bezier(.2,.8,.2,1) / (.4,0,1,1) | Entry / exit |
| `--ease-spring` | cubic-bezier(.34,1.3,.64,1) | Language thumb and sheets only, very subtle |

Animate only `transform` and `opacity`. Buttons press to 0.98. List rows fade in staggered (max 8 rows, 20ms apart).
Loaders: none under 100ms, inline spinner up to 1s, skeletons beyond (skeletons match the final layout).
`prefers-reduced-motion`: every animation and transition is removed, the language swap is instant, figures do not count up.

## Layout

- Desktop (1024px and up): 256px navy sidebar at the inline start (right in RTL), 64px sticky top bar.
- Tablet (768 to 1023px): 72px icon rail with tooltips.
- Mobile (under 768px): no hamburger. Bottom tab bar (Home, Users or Clients, Search, Profile), safe-area padding, 44px targets. Filters and forms open as bottom sheets with a grabber. Tables become card lists.
- Large title on each page, condensing into the top bar on scroll.
- Page patterns (vectorlab `page-patterns`): dashboard (Home), list (Users, Clients), detail (user, client), form (add/edit), settings (Profile).

## Components

`Button` (primary, secondary, danger, ghost; `IconButton` with tooltip) · `Input`, `Select`, `Textarea`, `PasswordInput` (visible label, error replaces hint, logical padding) ·
`Card`, `InsetList` + `InsetRow` · `Avatar` (colour from name within blue/navy/teal-gray) · `StatusPill` · `Segmented` (sliding thumb) · `LanguageSwitcher` ·
`Sheet` (centred modal on desktop, bottom sheet on mobile, focus trap and restore) · `Menu` (kebab dropdown) · `Tooltip` · `Toast` ·
`EmptyState` · `ErrorState` · `Skeleton` · `Pagination` · `PasswordChecklist` (live requirements and strength bar) · `CountUp` · `PageHeader` (large title) ·
`CommandPalette` · `AppShell` (`Sidebar`, `TopBar`, `TabBar`, `ProfileMenu`).

## RTL

Logical utilities only (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`, `border-s`, `rounded-s`). Email, phone, password and URL inputs are `dir="ltr"`, aligned to the inline start. Temporary passwords and phone numbers render in `<Ltr>`.
Keyboard hints (Ctrl K) stay LTR.


## Workflow additions (Phase 1)

- **Notification bell** (top bar, before the language switch): `IconButton` + `Popover`, count badge `bg-primary` with a canvas ring, latest 8 only (the popover closes on scroll, so it has no inner scroll area). Unread rows have a primary dot; read rows drop to `text-ink-2`.
- **Nav badge** (`Badge` in `navIcons.tsx`): `bg-primary`, white text, capped at 99+, always `dir="ltr"`. A 2px dot on the 72px rail and the tab bar.
- **More sheet**: when a role has more than three destinations, the phone tab bar shows three, Search and More. More lists the rest plus Profile in the standard `Sheet`.
- **Record tabs** (`components/records/RecordTabs`): `Segmented` in tablist mode: Overview | Activity | Files | Comments. Activity, Comments and Files are cards of divided rows with an `Avatar`, never custom list styles.
- **Settings lists**: a card of divided rows (name in the page language, the other language beneath in `text-ink-2`), `Switch off` text button, edit `IconButton`, and a `Sheet` form with both names required.
- Buttons are never disabled for "no changes". An unchanged form saves as a no-op.
