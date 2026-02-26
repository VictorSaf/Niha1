# Niha Carbon Platform - Design System Documentation

> **Version:** 2.0.0
> **Last Updated:** 2026-02-14
> **Live Reference:** [/design-system](http://localhost:5173/design-system)

### Tema grafică – un singur punct de intrare

**Toate caracteristicile temei grafice sunt centralizate.** Pentru „unde modific X?” și pentru fluxul temei:

- **Hub central:** `frontend/src/theme/README.md` – tabel cu fișierele temei, cum le modifici și cum stau în relație.
- **Tokeni editabili (nume variabile, config Theme Containers):** `frontend/src/theme/tokens.ts` și `frontend/src/theme/index.ts`.

Variabilele CSS sunt în `frontend/src/styles/design-tokens.css`; paleta Tailwind în `frontend/tailwind.config.js`. Păstrează-le aliniate; detaliile sunt în theme README.

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Surface Hierarchy](#surface-hierarchy) ← **NEW: 5-level depth system, container rules, spacing/radius rules**
4. [Color System](#color-system)
5. [Typography](#typography)
6. [Spacing System](#spacing-system)
7. [Border Radius](#border-radius)
8. [Shadow System](#shadow-system)
9. [Component Library](#component-library)
10. [Trading UI Patterns](#trading-ui-patterns)
11. [Animation Guidelines](#animation-guidelines)
12. [Implementation Guide](#implementation-guide)
13. [Best Practices](#best-practices)

---

## Overview

The Niha Carbon Platform Design System is a comprehensive set of design tokens, components, and patterns that ensure consistency across the entire application. It supports both **light** and **dark** modes with seamless transitions.

### Key Features

- **CSS Custom Properties** - All design tokens use CSS variables for easy theming
- **Dual Theme Support** - Light and dark modes with automatic switching
- **Component-Based** - Reusable React components with TypeScript support
- **Tailwind Integration** - Built on top of Tailwind CSS for rapid development
- **Trading-Specific** - Specialized components for financial trading interfaces
- **Responsive** - Mobile-first design with breakpoints for all screen sizes

---

## Design Principles

### 1. Professional & Trustworthy
Carbon credit trading requires a professional, trustworthy interface. Use clean layouts, clear typography, and consistent spacing.

### 2. Data-Dense Yet Readable
Trading interfaces need to display lots of information without overwhelming users. Use hierarchy, color, and spacing to create scannable layouts.

### 3. Color-Coded Trading
- **Green (Emerald)** - Buy orders, bids, positive movements
- **Red** - Sell orders, asks, negative movements
- **Blue (EUA)** - EU Allowance certificates
- **Amber (CEA)** - China Allowance certificates

### 4. Accessibility First
- Sufficient color contrast (WCAG AA minimum)
- Clear focus states on all interactive elements
- Semantic HTML structure
- Keyboard navigation support

### 5. Performance Optimized
- CSS-only animations where possible
- Framer Motion for complex interactions
- Optimized component rendering
- Minimal bundle size

---

## Surface Hierarchy

The platform uses **5 depth levels** for its dark theme, creating clear visual separation between page backgrounds, content areas, and interactive elements.

| Level | Color | Tailwind | CSS Variable | Usage |
|-------|-------|----------|-------------|-------|
| 0 — Page background | `#020617` | `navy-950` | `--page-container-dark-bg` | `.page-container-dark` — deepest page bg |
| 1 — Page content | `#0f172a` | `navy-900` | `--color-background` | `.page-bg` — standard page background |
| 2 — Card / Panel | `#1e293b` | `navy-800` | `--panel-bg` | `.panel`, `.content_wrapper` — card containers |
| 3 — Elevated | `#334155` | `navy-700` | `--color-surface-elevated` | Hover states, dropdowns, borders |
| 4 — Active | `#475569` | `navy-600` | `--color-surface-muted` | Active nav items, selected states |

### Container Rules

| Class | Purpose | Background | Padding |
|-------|---------|-----------|---------|
| `.page-container` | Max-width wrapper (1280px) | none | `px-4 sm:px-6 lg:px-8` |
| `.panel` | Canonical card/panel container | navy-800 + border navy-700 | `p-5` (20px) |
| `.panel--flush` | Panel with no padding | navy-800 + border navy-700 | `p-0` |
| `.panel--compact` | Panel with tight padding | navy-800 + border navy-700 | `p-3` (12px) |
| `.panel--hover` | Panel with lift-on-hover | navy-800 + border navy-700 | inherited |
| `.content_wrapper` | Theme-aware panel (CSS vars) | `var(--content-wrapper-bg)` | `var(--content-wrapper-padding)` |
| Modal bg | Dialog container | navy-800 + border navy-700 | Managed by Modal component |

**When to use what:**
- `.panel` — default for all card/section containers
- `.panel--flush` — when you need header/body layout with manual padding
- `.panel--compact` — stat cards, compact info displays
- `.content_wrapper` — dashboard summary cards (theme-overridable via ThemeContainers page)
- `<Card />` — React component wrapping `.panel` with variant/padding props

### Spacing Rules

| Context | Value | Tailwind |
|---------|-------|----------|
| Page content padding | 24px | `py-6` |
| Panel default padding | 20px | `p-5` (via `--panel-padding`) |
| Panel compact padding | 12px | `p-3` (via `--panel-compact-padding`) |
| Main layout grid gap | 24px | `gap-6` |
| Card-to-card gap | 16px | `gap-4` |
| Elements inside cards | 12px | `gap-3` |
| Dense rows / lists | 8px | `gap-2` |

### Border Radius Rules

| Element | Radius | Tailwind |
|---------|--------|----------|
| Inputs, buttons, badges | 8px | `rounded-lg` |
| Panels, cards | 12px | `rounded-xl` |
| Modals | 16px | `rounded-2xl` |
| Pills, avatars | 9999px | `rounded-full` |

---

## Color System

### Background Colors

#### Light Mode
```css
--color-background: #f8fafc;      /* navy-50 - Page background */
--color-surface: #ffffff;          /* Card/panel background */
--color-surface-elevated: #f1f5f9; /* navy-100 - Hover states */
--color-surface-muted: #e2e8f0;    /* navy-200 - Disabled backgrounds */
```

#### Dark Mode
```css
--color-background: #0f172a;      /* navy-900 */
--color-surface: #1e293b;          /* navy-800 */
--color-surface-elevated: #334155; /* navy-700 */
--color-surface-muted: #475569;    /* navy-600 */
```

### Text Colors

#### Light Mode
```css
--color-text-primary: #0f172a;    /* navy-900 - Main text */
--color-text-secondary: #475569;  /* navy-600 - Secondary text */
--color-text-muted: #64748b;      /* navy-500 - Placeholder text */
--color-text-inverse: #ffffff;    /* White text on dark backgrounds */
```

#### Dark Mode
```css
--color-text-primary: #ffffff;    /* White */
--color-text-secondary: #cbd5e1;  /* navy-200 */
--color-text-muted: #94a3b8;      /* navy-400 */
--color-text-inverse: #0f172a;    /* navy-900 */
```

### Brand Colors (Emerald)

Primary brand color used for buttons, links, and key actions.

```css
--color-primary: #10b981;         /* emerald-500 (light) / emerald-400 (dark) */
--color-primary-hover: #059669;   /* emerald-600 (light) / emerald-500 (dark) */
--color-primary-active: #047857;  /* emerald-700 */
--color-primary-light: #d1fae5;   /* emerald-100 (light) / rgba(16,185,129,0.2) (dark) */
```

### Certificate Colors

#### EUA (EU Allowance) - Blue
```css
--color-eua: #3b82f6;             /* blue-500 (light) / blue-400 (dark) */
--color-eua-light: #dbeafe;       /* blue-100 (light) / rgba(59,130,246,0.2) (dark) */
--color-eua-text: #1e40af;        /* blue-700 (light) / blue-400 (dark) */
```

#### CEA (China Allowance) - Amber
```css
--color-cea: #f59e0b;             /* amber-500 (light) / amber-400 (dark) */
--color-cea-light: #fef3c7;       /* amber-100 (light) / rgba(245,158,11,0.2) (dark) */
--color-cea-text: #b45309;        /* amber-700 (light) / amber-400 (dark) */
```

### Trading Colors

#### Bid/Buy Orders - Green
```css
--color-bid: #10b981;             /* emerald-500 (light) / emerald-400 (dark) */
--color-bid-hover: #34d399;       /* emerald-400 (light) / emerald-500 (dark) */
--color-bid-light: #d1fae5;       /* emerald-100 */
--color-bid-bg: rgba(16,185,129,0.1);  /* 10% opacity (light) / 15% (dark) */
```

#### Ask/Sell Orders - Red
```css
--color-ask: #ef4444;             /* red-500 (light) / red-400 (dark) */
--color-ask-hover: #f87171;       /* red-400 (light) / red-500 (dark) */
--color-ask-light: #fee2e2;       /* red-100 */
--color-ask-bg: rgba(239,68,68,0.1);   /* 10% opacity (light) / 15% (dark) */
```

### Status Colors

```css
--color-success: #10b981;         /* Emerald */
--color-warning: #f59e0b;         /* Amber */
--color-error: #ef4444;           /* Red */
--color-info: #3b82f6;            /* Blue */
```

### Usage Examples

```tsx
// Using CSS variables directly
<div style={{ backgroundColor: 'var(--color-surface)' }}>Content</div>

// Using Tailwind utility classes
<div className="bg-surface text-primary">Content</div>

// Using predefined utility classes
<div className="bg-page">
  <p className="text-primary">Primary text</p>
  <p className="text-secondary">Secondary text</p>
  <p className="text-muted">Muted text</p>
</div>
```

---

## Typography

### Font Families

```css
--font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
```

**Sans-serif (Inter)** is used for all body text, headings, and UI elements.
**Monospace (JetBrains Mono)** is used for numbers, prices, and code snippets.

### Font Size Scale

| Token | Size | Pixels | Usage |
|-------|------|--------|-------|
| `--text-xs` | 0.75rem | 12px | Labels, badges, fine print |
| `--text-sm` | 0.875rem | 14px | Secondary text, captions |
| `--text-base` | 1rem | 16px | Body text (default) |
| `--text-lg` | 1.125rem | 18px | Emphasized text |
| `--text-xl` | 1.25rem | 20px | Section headings |
| `--text-2xl` | 1.5rem | 24px | Sub-page titles |
| `--text-3xl` | 1.875rem | 30px | Page titles |
| `--text-4xl` | 2.25rem | 36px | Hero headings |
| `--text-5xl` | 3rem | 48px | Display headings |

### Font Weights

```css
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
--font-extrabold: 800;
```

### Line Heights

```css
--leading-none: 1;
--leading-tight: 1.25;
--leading-snug: 1.375;
--leading-normal: 1.5;
--leading-relaxed: 1.625;
--leading-loose: 2;
```

### Typography Utility Classes

```css
.page-title          /* 3xl, bold, tight leading */
.section-heading     /* xl, bold, tight leading */
.text-value          /* Monospace, semibold, tabular numbers */
```

### Usage Examples

```tsx
// Page title
<h1 className="page-title">Dashboard</h1>

// Section heading
<h2 className="section-heading">Recent Orders</h2>

// Numeric value
<p className="text-value">€1,234.56</p>

// Custom typography
<p style={{
  fontSize: 'var(--text-lg)',
  fontWeight: 'var(--font-semibold)',
  lineHeight: 'var(--leading-relaxed)'
}}>
  Custom text
</p>
```

---

## Spacing System

Based on a **4px base unit** for consistent, rhythmic spacing throughout the application.

### Spacing Scale

| Token | Value | Pixels | Usage |
|-------|-------|--------|-------|
| `--space-0` | 0 | 0px | No spacing |
| `--space-1` | 0.25rem | 4px | Minimal gaps |
| `--space-2` | 0.5rem | 8px | Tight spacing |
| `--space-3` | 0.75rem | 12px | Compact layouts |
| `--space-4` | 1rem | 16px | **Base unit** - Default spacing |
| `--space-5` | 1.25rem | 20px | Comfortable gaps |
| `--space-6` | 1.5rem | 24px | Card padding (small) |
| `--space-8` | 2rem | 32px | Card padding (medium) |
| `--space-10` | 2.5rem | 40px | Section spacing |
| `--space-12` | 3rem | 48px | Card padding (large) |
| `--space-16` | 4rem | 64px | Large sections |
| `--space-20` | 5rem | 80px | Hero spacing |
| `--space-24` | 6rem | 96px | Extra large sections |

### Common Patterns

```tsx
// Card padding (small, medium, large)
<div className="p-4">Small card</div>
<div className="p-6">Medium card</div>
<div className="p-8">Large card</div>

// Section spacing
<section className="py-8 md:py-10">Content</section>

// Gap between elements
<div className="flex gap-2">Tight gap</div>
<div className="flex gap-4">Normal gap</div>
<div className="flex gap-6">Comfortable gap</div>

// Container padding
<div className="px-4 sm:px-6 lg:px-8">Responsive padding</div>
```

---

## Resize Handles (ResizablePanelGroup)

When using `ResizablePanelGroup` (react-resizable-panels) for resizable layouts:

| Property | Value | Notes |
|----------|-------|-------|
| Border | `border-navy-700` | Handle background |
| Hover | `bg-navy-600` | Hover state |
| Width (vertical handle) | 4–6px | `w-1.5` (6px) for col-resize |
| Height (horizontal handle) | 4–6px | `h-1.5` for row-resize |
| Cursor | `col-resize` (vertical) / `row-resize` (horizontal) | Per orientation |
| Min panel size | 15–20% | Avoid panels collapsing completely |

**Accessibility**: Separator has `role="separator"` and `aria-orientation` from the library. Do not use slate/gray; use navy tokens only.

**Component**: `frontend/src/components/common/ResizablePanelGroup.tsx`

---

## Border Radius

Rounded corners create a modern, friendly interface.

### Radius Scale

| Token | Value | Pixels | Usage |
|-------|-------|--------|-------|
| `--radius-sm` | 0.375rem | 6px | Small elements |
| `--radius-md` | 0.5rem | 8px | Default |
| `--radius-lg` | 0.75rem | 12px | Medium elements |
| `--radius-xl` | 1rem | 16px | **Primary choice** - Buttons, inputs |
| `--radius-2xl` | 1.5rem | 24px | Cards, modals |
| `--radius-3xl` | 2rem | 32px | Large cards |
| `--radius-full` | 9999px | Circular | Pills, badges, avatars |

### Usage Examples

```tsx
// Buttons and inputs
<button className="rounded-xl">Button</button>
<input className="rounded-xl" />

// Cards
<div className="rounded-2xl">Card content</div>

// Badges and pills
<span className="rounded-full">Badge</span>

// Tables with rounded corners
<div className="rounded-xl overflow-hidden">
  <table>...</table>
</div>
```

---

## Shadow System

Shadows create depth and hierarchy in the interface.

### Shadow Scale

```css
--shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
--shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
--shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);
```

### Glow Effects

Special shadows for interactive elements and brand colors.

```css
--shadow-glow-emerald: 0 0 20px rgba(16, 185, 129, 0.25);  /* light */
                       0 0 30px rgba(52, 211, 153, 0.4);   /* dark */
--shadow-glow-blue: 0 0 20px rgba(59, 130, 246, 0.25);
--shadow-glow-amber: 0 0 20px rgba(245, 158, 11, 0.25);
```

### Usage Patterns

```tsx
// Default card shadow
<div className="shadow-lg">Card</div>

// Hover elevation
<div className="shadow-lg hover:shadow-xl transition-shadow">
  Hover me
</div>

// Primary button with glow
<button className="shadow-lg shadow-emerald-500/25">
  Primary Action
</button>

// Modal overlay
<div className="shadow-2xl">Modal content</div>
```

**Transaction confirmation modals** (e.g. CEA Cash order success): use `Modal` from `components/common`, a single primary CTA (e.g. "Inapoi la Dashboard"), and disable close on backdrop/escape so the user must click the CTA; data comes from the API response only. See CashMarketProPage order success modal.

---

## Component Library

### Page Section Headers (Subheader & SubSubHeader)

**Single source of truth:** bar styling and fixed positioning are defined in `frontend/src/styles/design-tokens.css`; components live in `frontend/src/components/common/` (`Subheader.tsx`, `SubSubHeader.tsx`, `SubheaderNavButton.tsx`). Use these everywhere for a unified page-section header theme. The subheader bar is **fixed** below the main header app-wide.

#### Purpose

- **Subheader** – Bar under the main app header: icon, title, description, and optional right-side content (e.g. nav buttons, actions). Used on Dashboard, Backoffice, Theme, Cash Market, Swap Center, Funding, Profile, Settings, etc.
- **SubSubHeader** – Optional bar directly under Subheader for page-specific content: filters, toggles (e.g. CEA|EUA), actions (Live, Refresh). Used in Backoffice (Onboarding: Contact Requests, KYC, Deposits), Market Orders, etc.

#### Theme tokens (design-tokens.css)

**Bar containers (unified look):**

| Token / class | Usage |
|---------------|--------|
| `--color-subheader-bg`, `--color-subheader-border`, `--subheader-padding-x`, `--subheader-padding-y` | Subheader bar background, border, padding |
| `--color-subsubheader-bg`, `--color-subsubheader-border`, `--subsubheader-padding-x`, `--subsubheader-padding-y`, `--subsubheader-min-height` | SubSubHeader bar |
| `.subheader-bar` | Applied by `Subheader` component – fixed below main header; do not override in pages |
| `.subheader-bar-spacer` | Spacer div rendered by `Subheader` so content starts below the fixed bar |
| `.subsubheader-bar` | Applied by `SubSubHeader` component |
| `.page-section-header-sticky` | Optional sticky wrapper for Subheader + SubSubHeader (e.g. BackofficeLayout) |

**Nav buttons (inside Subheader / SubSubHeader):** see [Subheader nav buttons](#subheader-nav-buttons-subpage-navigation) and [SubSubHeader nav buttons](#subsubheader-nav-buttons-child-level-under-subheader) below.

#### Fixed subheader bar

- The subheader bar (`.subheader-bar`) is **fixed** below the main header on all pages: `position: fixed; top: 4rem` (mobile) / `top: 5rem` (desktop); `Subheader` renders a spacer (`.subheader-bar-spacer`) so content is not hidden under the bar.
- **Subheader + SubSubHeader:** BackofficeLayout wraps both in `page-section-header-sticky` so the sub-subheader can stay with the subheader when needed.

#### Usage across the app

| Location | Subheader | SubSubHeader |
|----------|-----------|--------------|
| BackofficeLayout | Yes (Backoffice title + nav) | Yes (when `subSubHeaderLeft` / `subSubHeader` passed) |
| ThemeLayout | Yes (Theme + Sample/Containers) | No |
| DashboardPage, CashMarketPage, CeaSwapMarketPage, FundingPage, ProfilePage, SettingsPage | Yes | No |
| BackofficeOnboardingPage, MarketOrdersPage, etc. | Via BackofficeLayout | Via BackofficeLayout props |

#### Example

```tsx
// Layout with Subheader + optional SubSubHeader (BackofficeLayout)
<div className="page-section-header-sticky">
  <Subheader icon={...} title="Backoffice" description={...}>
    <nav>...</nav>
  </Subheader>
  {showSubSub && <SubSubHeader left={...}>{actions}</SubSubHeader>}
</div>

// Single Subheader (fixed bar is applied automatically)
<Subheader icon={...} title="Theme" description="Design system showcase" />
```

To change the look app-wide, edit the CSS variables and classes in `design-tokens.css`; do not hard-code bar colors or padding in pages.

---

### Buttons

#### Variants

1. **Primary** - Emerald gradient with glow effect
2. **Secondary** - Navy solid background
3. **Outline** - Border only, transparent background
4. **Ghost** - Text only, no border or background

#### Sizes

- **Small** - `px-4 py-2 text-sm`
- **Medium** - `px-6 py-3 text-base` (default)
- **Large** - `px-8 py-4 text-lg`

#### Examples

```tsx
// Primary button
<button className="rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:from-emerald-600 hover:to-emerald-700 hover:shadow-xl">
  Primary Action
</button>

// Secondary button
<button className="rounded-xl bg-navy-900 dark:bg-navy-700 px-6 py-3 text-base font-semibold text-white transition-all hover:bg-navy-800 dark:hover:bg-navy-600 hover:shadow-lg">
  Secondary Action
</button>

// Outline button
<button className="rounded-xl border-2 border-navy-300 dark:border-navy-600 px-6 py-3 text-base font-semibold text-navy-700 dark:text-navy-300 transition-all hover:border-navy-400 dark:hover:border-navy-500 hover:bg-navy-50 dark:hover:bg-navy-800">
  Outline Button
</button>

// With icon
<button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3">
  <Download className="h-4 w-4" />
  Download
</button>
```

#### Destructive / Reject actions

For reject, delete, or destructive actions use `variant="secondary"` with the error token so the button stays within the Button API (no `danger` variant). Use `text-red-500` for Error/Sell per design system:

```tsx
<Button
  variant="secondary"
  className="text-red-500 hover:bg-red-500/10 dark:hover:bg-red-500/20"
  onClick={handleReject}
>
  Reject
</Button>
```

Forms that offer both a primary and a destructive action in the same view (e.g. **Add Asset** modal: Deposit = primary, Withdraw = secondary with red tokens) use this pattern: primary for the additive/safe action, secondary + red for subtractive/destructive.

#### Subheader nav buttons (subpage navigation)

Used in backoffice and other subheader bars. States are defined in `design-tokens.css` and applied via utility classes:

- **Base**: `.subheader-nav-btn` – layout, padding, typography, radius.
- **Opened subpage (active)**: `.subheader-nav-btn-active` – current subpage; uses `--color-subheader-nav-active-bg` and `--color-subheader-nav-active-text`.
- **Default (inactive)**: `.subheader-nav-btn-inactive` – other items; uses `--color-subheader-nav-inactive-text`; hover uses `--color-subheader-nav-inactive-hover-bg` and `--color-subheader-nav-inactive-hover-text`.

Use the `SubheaderNavButton` component from `components/common`; it applies these classes based on `isActive`. Change the theme by editing the CSS variables in `design-tokens.css`.

#### SubSubHeader nav buttons (child-level under Subheader)

Used in the SubSubHeader bar (e.g. Onboarding: Contact Requests, KYC, Deposits). **Distinct from Subheader buttons**: smaller, lighter weight, different radius so they read as a subclass. States and count badge are in `design-tokens.css`:

- **Base**: `.subsubheader-nav-btn` – smaller padding and font (`text-xs`), `rounded-lg` (0.5rem).
- **Current subpage (active)**: `.subsubheader-nav-btn-active` – uses `--color-subsubheader-nav-active-bg` (navy-700), `--color-subsubheader-nav-active-text`.
- **Default (inactive)**: `.subsubheader-nav-btn-inactive` – uses `--color-subsubheader-nav-inactive-text`; hover uses `--color-subsubheader-nav-inactive-hover-bg`, `--color-subsubheader-nav-inactive-hover-text`.
- **Count badge (pending/new items)**: `.subsubheader-nav-badge` – high-visibility red pill; uses `--color-subsubheader-nav-badge-bg` (red-600), `--color-subsubheader-nav-badge-text` (white). Use for counts (e.g. contact requests, KYC queue).

Highlighting the button for the current page uses the same logic as Subheader (apply active class when route matches). Customize via the CSS variables in `design-tokens.css`.

---

### Inputs

#### States

1. **Default** - Normal state with border
2. **Focus** - Emerald ring on focus
3. **Error** - Red border and ring
4. **Disabled** - Muted colors, cursor-not-allowed

#### Examples

```tsx
// Basic input
<input
  type="text"
  placeholder="Enter text..."
  className="w-full rounded-xl border-2 border-navy-200 dark:border-navy-600 bg-white dark:bg-navy-800 px-4 py-3 text-navy-900 dark:text-white placeholder-navy-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-emerald-500"
/>

// With icon
<div className="relative">
  <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-navy-400" />
  <input
    type="text"
    placeholder="Search..."
    className="w-full rounded-xl border-2 border-navy-200 dark:border-navy-600 bg-white dark:bg-navy-800 py-3 pl-12 pr-4 focus:ring-2 focus:ring-emerald-500"
  />
</div>

// Error state
<input
  type="text"
  className="w-full rounded-xl border-2 border-red-500 bg-white dark:bg-navy-800 px-4 py-3 focus:ring-2 focus:ring-red-500"
/>
<p className="mt-1 text-xs text-red-500">This field is required</p>

// Disabled state
<input
  type="text"
  disabled
  className="w-full cursor-not-allowed rounded-xl border-2 border-navy-200 dark:border-navy-700 bg-navy-100 dark:bg-navy-800/50 px-4 py-3 text-navy-400 dark:text-navy-500"
/>
```

#### Number inputs

**Numeric fields** (amounts, quantities, prices, fees, etc.) use the shared **`NumberInput`** component from `frontend/src/components/common/NumberInput.tsx`. Do not use raw `<input type="number">`.

- **Default style**: `rounded-lg`, single `border`, `px-3 py-2`, `border-navy-300 dark:border-navy-600`, `bg-white dark:bg-navy-800`, `text-navy-900 dark:text-white`. Focus: `focus:ring-2 focus:ring-emerald-500`. Error: `border-red-500 focus:ring-red-500`.
- **Formatting**: Values are displayed with **comma as thousands separator** (e.g. `1,000.50`) via `locale="en-US"` (default). The component uses `type="text"` and `inputMode="decimal"` under the hood; `onChange` receives the raw numeric string (no commas).
- **Props**: `value` (string | number), `onChange: (value: string) => void`, `decimals?: number` (default `2`), `locale?: string` (default `'en-US'`). Optional: `label`, `error`, `icon`, `suffix`, `placeholder`, and standard input attributes (e.g. `disabled`, `required`).
- **CEA/EUA certificate quantities**: Use `decimals={0}` for inputs (whole numbers only; no fractional certificates). For display, use `formatCertificateQuantity(value)` from `utils` so certificate balances, volumes, and quantities show with zero decimal places.

```tsx
import { NumberInput } from '../common';

// Amount with 2 decimals (e.g. currency)
<NumberInput
  value={amount}
  onChange={(v) => setAmount(v)}
  decimals={2}
  placeholder="0.00"
/>

// Integer quantity (e.g. CEA/EUA certificates – whole numbers only)
<NumberInput value={quantity} onChange={(v) => setQuantity(v)} decimals={0} placeholder="0" />

// With label and error
<NumberInput
  label="Price (EUR)"
  value={price}
  onChange={(v) => setPrice(v)}
  decimals={2}
  error={priceError}
/>
```

**Amount + Max button:** In modals where the amount is bounded by a current balance (e.g. **Add Asset**, **Withdrawal Request**), place a **Max** button next to the amount input. Clicking Max sets the value to the current balance (EUR: 2 decimals; CEA/EUA: integer). Use `flex gap-2` with the input in a `flex-1` wrapper and the button with `px-3 py-2 text-sm border border-navy-600 text-navy-300 rounded-xl hover:bg-navy-700`. Reference: `AddAssetModal.tsx`, `WithdrawalRequestModal.tsx`.

#### Admin config inputs (SettingsInput pattern)

For **admin configuration panels** (e.g. Auto Trade settings) where numeric values use thousands-separator formatting and optional recommended-value hints:

- Use the same visual pattern as NumberInput: **light/dark support** with `bg-white dark:bg-navy-900`, `border-navy-300 dark:border-navy-700`, `text-navy-900 dark:text-white`, and `focus:border-emerald-500/50 dark:focus:border-emerald-500/50`.
- Raw value on focus, formatted (e.g. with commas) on blur.
- Optional "Rec: …" hint below the input; clicking the hint applies the recommended value.
- Reference: `frontend/src/pages/AutoTradePage.tsx` — `SettingsInput` component.

#### ActionsDropdown (table row actions)

For **table row actions** (Edit, Delete, Test, etc.) use a compact **ellipsis button** (e.g. `MoreHorizontal` icon) that opens a dropdown menu. The dropdown must:

- Close on **click outside** (document mousedown) and on **Escape** key.
- Render above or below the trigger as needed (e.g. `bottom-full` for last rows).
- Use design tokens only (navy background, border, emerald/red for actions).

Reference: `frontend/src/pages/SettingsPage.tsx` — `ActionsDropdown` component used in Price Scraping and Exchange Rate tables.

**Preset buttons (quick-add):** For sources or configs with well-known defaults, use a preset button that pre-fills the Add form and opens the modal. Example: **Add Trading Economics EUA** in Price Scraping (TrendingUp icon, `aria-label` for accessibility). The generic Add button resets the form to empty; the preset button sets known values.

---

### Badges

#### Variants

1. **Status** - Success, Warning, Error, Info
2. **Certificates** - EUA (blue), CEA (amber)
3. **Trading** - Bid (green), Ask (red)
4. **Count** - Notification badges

**Cash Market – Recent Trades (Ticker & ACTIVITY):** The ticker and ACTIVITY panel on Cash Market Pro share a single data source (`recentTrades` from `useCashMarket`), updated on initial load and on WebSocket `trade_executed`. Use **emerald** for BUY and **red** for SELL in both. ACTIVITY shows relative time; on hover over the time, show the full UTC timestamp (e.g. "Feb 14, 2026, 1:22:08 AM UTC"). Use `flex flex-col gap-2` for row spacing.

**CEA Price chart (Cash Market Pro):** Same container pattern as ACTIVITY: `bg-navy-900 rounded border border-navy-700 overflow-hidden`; header bar with icon (TrendingUp), title "CEA Price", `border-b border-navy-700`, `bg-navy-800`. Chart area uses **lightweight-charts** (Area series): background navy-900 (#0f172a), grid navy-800 (#1e293b), borders navy-700 (#334155), text navy-400 (#94a3b8), line/fill emerald-400 (#34d399). No slate/gray. Data: GET /cash-market/trades/CEA?limit=100 on mount; real-time via `nihao:tradeExecuted` (filter `certificateType === 'CEA'`). Resize via ResizeObserver. Component: `frontend/src/components/cash-market/CEAPriceChart.tsx`.

#### Examples

```tsx
// Status badges
<span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">
  <Check className="h-3 w-3" />
  Success
</span>

<span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-700 dark:text-amber-400">
  <AlertTriangle className="h-3 w-3" />
  Warning
</span>

// Certificate badges
<span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 dark:border-blue-500/50 bg-blue-100 dark:bg-blue-500/20 px-4 py-2 text-sm font-semibold text-blue-700 dark:text-blue-400">
  <Leaf className="h-4 w-4" />
  EUA Certificate
</span>

// Trading badges
<span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 px-4 py-2 text-sm font-bold text-emerald-700 dark:text-emerald-400">
  <TrendingUp className="h-4 w-4" />
  BID €99.50
</span>

// Count badge (notification)
<div className="relative">
  <Bell className="h-6 w-6 text-navy-600 dark:text-navy-400" />
  <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
    3
  </span>
</div>
```

#### Client status badge

Use **`ClientStatusBadge`** (`components/common`) for deposit/client role display (Onboarding Deposits tab, AML tab, Backoffice Deposits page, Users list). Single source of truth: `user_role` from API (FUNDING when user announced transfer). Uses `clientStatusVariant` (`utils/roleBadge`) for role→Badge variant mapping; design tokens only. Supported roles include onboarding flow (NDA, KYC, … EUA), **MM** (Market Maker; maps to `info` variant), and **ADMIN**.

```tsx
import { ClientStatusBadge } from '@/components/common';

// In deposit cards or table "Client" column
<ClientStatusBadge role={deposit.user_role ?? deposit.userRole} />
// Renders role (e.g. FUNDING, APPROVED) or "—" when missing
```

#### Deposit & Withdrawal History (User Detail, Assets tab)

Unified list of wire deposits and add-asset transactions. Use design tokens consistently:

- **Wire deposits**: `DollarSign` icon (emerald), Badge `variant="success"` for cleared, `variant="danger"` for rejected. Use `formatCurrency` from `utils` for amount display.
- **Add-asset deposits**: `DollarSign` icon, Badge `variant="success"`, positive amount.
- **Add-asset withdrawals**: `Minus` icon (red-500), Badge `variant="danger"`, amount with minus prefix (e.g. `-€1,000.00`). Follows "Red = sell/negative" trading semantics.

Merge and sort via `buildDepositAndWithdrawalHistory` (`utils/depositHistory.ts`); cap at 50 items.

#### Audit Logging (Backoffice)

**All Tickets** (`/backoffice/logging`, `AllTicketsTab`): Table with columns TIME, ACTOR, ACTION, DETAILS, RESULT, REF. Use design tokens only (navy, emerald, amber). For **TRADE_EXECUTED** rows, the Actor cell shows counterparties in a compact one-line format: badge (TR/INT) + **Buyer** (emerald) · **Seller** (amber); full Buyer/Seller names and Aggressor are in the cell `title` (tooltip). Row tint follows trade direction (emerald for ask, red for bid). **Ticket detail modal** (`TicketDetailModal`): For trades, a dedicated **Counterparties** section shows Buyer and Seller in two blocks (emerald/amber borders). No hard-coded colors; use `text-emerald-400/90`, `text-amber-400/90`, `border-emerald-700/40`, `border-amber-700/40`.

---

### Cards & Panels

**Panel (canonical container):** Use the `.panel` class or `<Card />` component for all card/section containers. See [Surface Hierarchy](#surface-hierarchy) for the full container system.

| Token | Value | Role |
|-------|-------|------|
| `--panel-bg` | `#1e293b` (navy-800) | Background |
| `--panel-border` | `#334155` (navy-700) | Border |
| `--panel-radius` | `0.75rem` (12px) | Corner radius (`rounded-xl`) |
| `--panel-padding` | `1.25rem` (20px) | Default padding |
| `--panel-compact-padding` | `0.75rem` (12px) | Compact variant padding |

To change the panel look globally, edit these variables in `design-tokens.css`.

**Dashboard summary cards (Portfolio):** The Cash (EUR) card follows the standard `.content_wrapper` pattern (theme-aware). For users with role **AML**, the card additionally uses an amber background at 50% opacity (`bg-amber-500/50`, `dark:bg-amber-400/50`) and displays the secondary line **"UNDER AML APPROVAL"** (with optional "Total deposited: €X · " when applicable). This indicates funds pending AML approval without introducing new tokens.

#### Variants

1. **Default** (`panel`) - Standard container with default padding (p-5)
2. **Flush** (`panel panel--flush`) - No padding, for tables/lists with header/body
3. **Compact** (`panel panel--compact`) - Tight padding (p-3), for stat cards
4. **Hover** (`panel panel--hover`) - Lift on hover, for interactive cards
5. **Glass** - Glassmorphism effect with backdrop blur (via `<Card variant="glass" />`)

#### Examples

```tsx
// Standard panel (preferred for all card containers)
<div className="panel">
  <h3 className="text-lg font-bold text-white">Card Title</h3>
  <p className="mt-2 text-sm text-navy-400">Card content goes here</p>
</div>

// Panel with header/body layout (flush + manual padding)
<div className="panel panel--flush">
  <div className="px-4 py-3 border-b border-navy-700">
    <h3 className="font-semibold text-white">Section Header</h3>
  </div>
  <div className="p-4">
    <p className="text-sm text-navy-400">Section body content</p>
  </div>
</div>

// Or with the Card component (same thing, React-style)
<Card>
  <h3 className="text-lg font-bold text-white">Card Title</h3>
  <p className="mt-2 text-sm text-navy-400">Card content goes here</p>
</Card>

// Compact stat card
<div className="panel panel--compact">
  <p className="text-xs text-navy-400">Total Revenue</p>
  <p className="text-2xl font-bold text-white font-mono">€12,543</p>
</div>

// Settings sections use the same panel pattern per section.
<div className="panel">
  <h2>Mail & Authentication</h2>
  {/* Form fields */}
</div>

// Compact list row (e.g. Contact Requests: Entitate, Nume, Data + actions). Class in index.css.
<div className="card_contact_request_list">
  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
    <span><Typography variant="sectionLabel" color="muted">Entitate:</Typography> <Typography variant="bodySmall" color="primary">{entity}</Typography></span>
    <span><Typography variant="sectionLabel" color="muted">Nume:</Typography> <Typography variant="bodySmall" color="primary">{name}</Typography></span>
    <span><Typography variant="sectionLabel" color="muted">Data:</Typography> <Typography variant="bodySmall" color="primary">{date}</Typography></span>
  </div>
  <div className="flex items-center gap-1.5 shrink-0">{/* View, Approve, Reject, Delete */}</div>
</div>

// Glass card (glassmorphism)
<div className="rounded-2xl border border-white/20 dark:border-navy-700/50 bg-white/80 dark:bg-navy-800/80 p-6 shadow-lg backdrop-blur-lg">
  <h3 className="text-lg font-bold">Glass Card</h3>
  <p className="mt-2 text-sm">Frosted glass effect</p>
</div>

// Stat card
<div className="rounded-2xl border border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800 p-6">
  <div className="flex items-start justify-between">
    <div>
      <p className="text-sm font-medium text-navy-600 dark:text-navy-400">
        Total Revenue
      </p>
      <p className="mt-2 font-mono text-3xl font-bold text-navy-900 dark:text-white">
        €12,543
      </p>
      <div className="mt-2 flex items-center gap-1 text-sm font-semibold text-emerald-500">
        <TrendingUp className="h-4 w-4" />
        +12.5%
      </div>
    </div>
    <div className="rounded-xl bg-emerald-100 dark:bg-emerald-500/20 p-3">
      <Euro className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
    </div>
  </div>
</div>
```

#### Admin overlay (role simulation floater)

The **RoleSimulationFloater** (`frontend/src/components/admin/RoleSimulationFloater.tsx`) is shown only when `user?.role === 'ADMIN'`. Use fixed positioning (e.g. `fixed bottom-4 right-4`), `z-40` so it sits below modals. Style with design tokens only: navy for background/border/text, emerald for focus ring on the select. Support light and dark via `dark:` variants. Provide `aria-label` on the group and on the select. See `app_truth.md` §8–9 and `docs/commands/interface.md`.

---

## Trading UI Patterns

### Order Book Rows

```tsx
// Bid row (buy order) - Green theme
<div className="rounded-lg p-3 transition-colors hover:bg-emerald-50 dark:hover:bg-emerald-500/10">
  <div className="flex items-center justify-between">
    <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
      €99.50
    </span>
    <span className="font-mono text-sm text-navy-700 dark:text-navy-300">
      1,234
    </span>
    <span className="text-xs text-navy-600 dark:text-navy-400">
      5 orders
    </span>
  </div>
</div>

// Ask row (sell order) - Red theme
<div className="rounded-lg p-3 transition-colors hover:bg-red-50 dark:hover:bg-red-500/10">
  <div className="flex items-center justify-between">
    <span className="text-sm font-semibold text-red-600 dark:text-red-400">
      €99.55
    </span>
    <span className="font-mono text-sm text-navy-700 dark:text-navy-300">
      3,421
    </span>
    <span className="text-xs text-navy-600 dark:text-navy-400">
      6 orders
    </span>
  </div>
</div>

// Spread indicator
<div className="border-t border-b border-navy-200 dark:border-navy-700 py-3">
  <div className="flex items-center justify-center gap-2">
    <span className="text-xs font-medium text-navy-600 dark:text-navy-400">
      Spread:
    </span>
    <span className="font-mono text-sm font-bold text-navy-900 dark:text-white">
      €0.10
    </span>
  </div>
</div>
```

### Price Movement Indicators

```tsx
// Positive price movement
<div className="rounded-xl border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 p-4">
  <div className="flex items-center gap-2">
    <TrendingUp className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
    <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
      Positive
    </span>
  </div>
  <p className="mt-2 font-mono text-2xl font-bold text-emerald-600 dark:text-emerald-400">
    +€2.50
  </p>
  <p className="text-xs text-emerald-600/70 dark:text-emerald-400/70">
    +2.57% today
  </p>
</div>

// Negative price movement
<div className="rounded-xl border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 p-4">
  <div className="flex items-center gap-2">
    <TrendingDown className="h-5 w-5 text-red-600 dark:text-red-400" />
    <span className="text-sm font-medium text-red-700 dark:text-red-400">
      Negative
    </span>
  </div>
  <p className="mt-2 font-mono text-2xl font-bold text-red-600 dark:text-red-400">
    -€1.25
  </p>
  <p className="text-xs text-red-600/70 dark:text-red-400/70">
    -1.28% today
  </p>
</div>
```

---

## Animation Guidelines

### CSS Animations

```css
/* Fade in */
.animate-fade-in {
  animation: fadeIn 0.5s ease-out;
}

/* Slide up */
.animate-slide-up {
  animation: slideUp 0.5s ease-out;
}

/* Pulse (loading) */
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Spin (loading indicator) */
.animate-spin {
  animation: spin 1s linear infinite;
}
```

### Framer Motion

```tsx
// Fade in
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  transition={{ duration: 0.5 }}
>
  Content
</motion.div>

// Slide up
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  Content
</motion.div>

// Scale in
<motion.div
  initial={{ opacity: 0, scale: 0.9 }}
  animate={{ opacity: 1, scale: 1 }}
  transition={{ duration: 0.3 }}
>
  Content
</motion.div>

// Modal animation
<motion.div
  initial={{ opacity: 0, scale: 0.95, y: 20 }}
  animate={{ opacity: 1, scale: 1, y: 0 }}
  exit={{ opacity: 0, scale: 0.95, y: 20 }}
  transition={{ type: 'spring', duration: 0.3 }}
>
  Modal content
</motion.div>
```

### Transition Timing

```css
--duration-fast: 100ms;
--duration-normal: 200ms;
--duration-slow: 300ms;
--duration-slower: 500ms;

--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
```

---

## Implementation Guide

### Using Design Tokens

#### Method 1: CSS Variables
```tsx
<div style={{
  backgroundColor: 'var(--color-surface)',
  padding: 'var(--space-6)',
  borderRadius: 'var(--radius-2xl)'
}}>
  Content
</div>
```

#### Method 2: Tailwind Classes
```tsx
<div className="bg-white dark:bg-navy-800 p-6 rounded-2xl">
  Content
</div>
```

#### Method 3: Utility Classes
```tsx
<div className="bg-surface p-6 rounded-2xl">
  Content
</div>
```

### Dark Mode Implementation

The design system uses Tailwind's `dark:` variant for dark mode styling.

```tsx
// Add dark class to root element
<html className="dark">

// Or use a state/store for theme toggle
const [theme, setTheme] = useState('light');

useEffect(() => {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}, [theme]);

// Component styling
<div className="bg-white dark:bg-navy-800 text-navy-900 dark:text-white">
  This adapts to light/dark mode
</div>
```

### Responsive Design

Use Tailwind's responsive prefixes:

```tsx
<div className="
  grid
  grid-cols-1
  md:grid-cols-2
  lg:grid-cols-3
  gap-4
  md:gap-6
  lg:gap-8
">
  <div>Card 1</div>
  <div>Card 2</div>
  <div>Card 3</div>
</div>
```

Breakpoints:
- **sm:** 640px (tablet)
- **md:** 768px (desktop)
- **lg:** 1024px (large desktop)
- **xl:** 1280px (extra large)

---

## Best Practices

### 1. Consistency

✅ **DO**: Use design tokens consistently
```tsx
<div style={{ padding: 'var(--space-6)' }}>
  <p style={{ fontSize: 'var(--text-lg)' }}>Text</p>
</div>
```

❌ **DON'T**: Use arbitrary values
```tsx
<div style={{ padding: '23px' }}>
  <p style={{ fontSize: '17px' }}>Text</p>
</div>
```

### 2. Accessibility

✅ **DO**: Ensure sufficient contrast
```tsx
<p className="text-navy-900 dark:text-white">
  High contrast text
</p>
```

✅ **DO**: Add focus states
```tsx
<button className="focus:ring-2 focus:ring-emerald-500">
  Button
</button>
```

### 3. Performance

✅ **DO**: Use CSS transitions for simple animations
```tsx
<div className="transition-colors duration-200 hover:bg-navy-100">
  Hover me
</div>
```

✅ **DO**: Use Framer Motion for complex animations
```tsx
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
>
  Content
</motion.div>
```

### 4. Reusability

✅ **DO**: Use the standard `.card_back` class or `<Card />` for section/card wrappers
```tsx
// Prefer the shared component or utility class
<Card>{children}</Card>
// or
<div className="card_back">{children}</div>
```

### 5. Semantic HTML

✅ **DO**: Use appropriate HTML elements
```tsx
<button type="button" onClick={handleClick}>
  Click me
</button>
```

❌ **DON'T**: Use divs for interactive elements
```tsx
<div onClick={handleClick}>
  Click me
</div>
```

---

## Resources

- **Live Reference:** [/design-system](http://localhost:5173/design-system)
- **Design Tokens:** `/src/styles/design-tokens.css`
- **Tailwind Config:** `/tailwind.config.js`
- **Component Library:** `/src/components/common/`
- **Lucide Icons:** [lucide.dev](https://lucide.dev)
- **Framer Motion:** [framer.com/motion](https://www.framer.com/motion/)

---

## Changelog

### Version 2.0.0 (2026-02-14)
- **Surface hierarchy**: formalized 5-level depth system (navy-950 → navy-600)
- **Panel system**: new `.panel` class as canonical container, replacing `content_wrapper_last` and `card_back`
  - Variants: `--flush` (p-0), `--compact` (p-3), `--hover` (interactive)
  - CSS variable tokens: `--panel-bg`, `--panel-border`, `--panel-radius`, `--panel-padding`
- **Spacing rules**: standardized card padding (p-5), section gap (gap-6), element gap (gap-3), dense gap (gap-2)
- **Border radius rules**: formalized usage — lg for elements, xl for panels, 2xl for modals, full for pills
- **Typography formalization**: documented usage per size level
- **Shadow system fix**: removed global `box-shadow: none !important` that was disabling the entire shadow system
- **Color cleanup**: migrated all `gray-*` and `slate-*` references to `navy-*` palette
- **Deprecated**: `content_wrapper_last` (alias kept for compat, use `.panel` instead), `.card_back`

### Version 1.0.0 (2026-01-22)
- Initial design system documentation
- Comprehensive color system with light/dark modes
- Typography scale and guidelines
- Spacing system based on 4px base unit
- Border radius and shadow scales
- Component library patterns
- Trading-specific UI components
- Animation guidelines
- Implementation guide and best practices

---

**Questions or feedback?** Contact the design team or open an issue on GitHub.
