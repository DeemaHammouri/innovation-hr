# Design research

Method: six web searches (16 Nov 2026). Most results were third-party write-ups, not first-party documentation, so claims are marked
where they are secondhand. We extract **principles only**; no layouts, assets or code are copied, and the brand stays as it is
(IA mark, navy and iOS blue, Manrope, IBM Plex Sans Arabic, Phosphor icons, calm and spacious).

**Not researched this round:** Mercury, Ramp, Attio, Pitch, Notion, Apple Health/Settings, onboarding checklists and empty states
(the one empty-state search returned nothing usable). The decisions below do not lean on them.

## 1. Linear: keyboard-first speed

- **What works:** every major action has a shortcut with mnemonic keys; the command menu (Cmd/Ctrl+K) is the hub for navigation
  and actions; the menu opens near the element that called it (Linear changelog, 2019). Sources:
  [Linear: level up](https://linear.app/features/level-up), [Linear: command menu changelog](https://linear.app/changelog/2019-10-07-contextual-command-menu),
  [Blake Crosley guide](https://blakecrosley.com/guides/design/linear) (secondhand), [Gunpowder Labs](https://gunpowderlabs.com/2024/12/22/linear-delightful-patterns) (secondhand).
- **Principle:** the mouse path and the keyboard path are the same feature; speed is a design value, not a bonus.
- **For us:** a palette that does things ("Add lead", "Request quotation for…"), `g` then a letter to navigate, `?` for a sheet of
  shortcuts, hints shown in tooltips. Arabic keeps Latin shortcut letters, laid out LTR inside the RTL page.
- Speed figures quoted online ("under 200 ms") are unverified; we set our own budget (120 to 320 ms, transform and opacity only).

## 2. Stripe Dashboard: numbers first, colour for status

- **What works (secondhand, no official Stripe source):** dense but breathable tables; large, high-contrast figures with tabular
  numerals; monochrome sparklines for trends, with colour kept for status. Sources:
  [925 Studios breakdown](https://www.925studios.co/blog/stripe-dashboard-design-breakdown), [AdminLTE dashboard examples](https://adminlte.io/blog/25-best-dashboard-design-examples-for-2026-real-products-principles/).
- **Principle:** a figure is the hero, its trend is a quiet whisper, and colour is spent only where something needs a decision.
- **For us:** tabular numerals on every amount and count, single-hue sparklines (navy/blue), red/amber/green reserved for overdue,
  due-soon and done. Charts always come with a table alternative (already built).

## 3. Arabic and RTL

- **What works:** mirror direction-bearing icons (back, forward, progress arrows) and layout; leave symmetric or non-directional
  icons, logos and play controls alone; numerals run LTR inside RTL text; the font must shape Arabic properly; a native
  speaker should proofread. Sources: [Material bidirectionality](https://m2.material.io/go/design-bidirectionality),
  [Saudisoft RTL checklist](https://localization.saudisoft.com/?p=38918), [Exadel RTL testing](https://exadel.com/news/localization-testing-tips-and-tricks-for-rtl-language-websites-and-apps),
  [YourStory](https://yourstory.com/mystory/right-to-left-website-development-dvice-on-design-bzxofurswg).
- **Principle:** RTL is a second first-class design, not a flipped copy.
- **For us:** keep Western digits (the product already uses them), wrap phone numbers and references in the LTR helper, check
  every new icon for "does it point?", and review Arabic wording as copy (done this round: see QA_MATRIX).

## 4. View Transitions API

- **What works:** `document.startViewTransition` animates a DOM change between two states with a cross-fade by default; shared
  elements get a `view-transition-name`. Sources: [Chrome guidance](https://developer.chrome.com/docs/modern-web-guidance/guides/ui-behaviors/same-document-transitions),
  [WebKit](https://webkit.org/blog/16967/two-lines-of-cross-document-view-transitions-code-you-can-use-on-every-website-today/).
- **Caveat:** sources disagree on whether the browser honours `prefers-reduced-motion` by itself. We do not rely on it: check the media
  query before calling the API and call the update directly when reduced motion is requested.
- **Principle:** progressive enhancement. Where the API is missing the page still works, with no animation.
- **For us:** route changes cross-fade; a list row's company name shares a transition name with the detail header.

## 5. Accessible kanban

- **What works:** WCAG 2.5.7 needs a single-pointer alternative to dragging. The W3C's own example is a task board with a menu on each
  card to pick the destination column. Sources: [W3C Understanding 2.5.7](https://www.w3.org/WAI/WCAG22/Understanding/dragging.html),
  [EZUD](https://ezud.com/accessible-drag-drop-alternatives/).
- **Principle:** drag is a shortcut, never the only way.
- **For us:** the pipeline already has "Move to…" on every card; keep it as the primary path on touch and screen readers, and announce
  the result in a live region.

## 6. Optimistic UI and undo

- **What works:** for reversible, low-risk actions, act at once and offer Undo for about five seconds rather than asking first; keep a
  confirmation for payments, irreversible and financial actions and wait for the server. Always roll back on error.
  Sources: [Optimistic UI guide](https://camoa.github.io/dev-guides/js/interaction-craft/optimistic-ui), [Optimistic Update pattern](https://skill-wiki.github.io/atom/frontend-design/pattern-optimistic-update).
- **Principle:** confirm what cannot be undone; undo what can.
- **For us:** undo toast for archive, lead moves and notification read; no optimistic payments, payroll or signatures.

## Design decisions

1. **Home is a "today" page, not a tile wall:** greeting, date, and the one to three things that need this person now, each with a direct button.
2. **Figures are heroes:** large tabular numerals, one quiet sparkline, no decorative colour.
3. **Colour means status only:** danger for overdue, warning for due soon, success for done; everything else navy or blue.
4. **A pipeline funnel strip** (Leads, Contacted, Qualified, Quotation, Contract, Active) with clickable counts that filter the list.
5. **"Needs attention" feed ordered by urgency,** built from the data My Work already returns, so it cannot disagree with the server.
6. **Command palette that acts:** verbs first, recent items, scoped search (`clients: acme`), create-from-search.
7. **Keyboard layer:** `g` then `h l q c p` to go, `c` to create, `/` to search, `?` for the sheet; always shown in tooltips.
8. **View Transitions with a reduced-motion guard** on route changes; fallback is no animation.
9. **Motion budget:** transform and opacity only, 120 to 320 ms, ease-out, one count-up and one chart draw-in per load, all disabled under reduced motion.
10. **Undo over confirm** for reversible actions; confirmation remains for money, signatures and anything the server cannot reverse.
