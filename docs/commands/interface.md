# Interface & Design System

Your task is to maintain UI/UX consistency, create centralized design systems that enable one-command theme changes, manage themes and components, and ensure all features integrate seamlessly into the application's user interface.

## Core Principle

The design system MUST be centralized so that changing a theme or design token in ONE place automatically updates ALL components across the entire application. Components must NEVER use hard-coded colors, spacing, or typography—they MUST reference design tokens.

## Steps

1. Analyze the current UI/UX state:
   - Check `app-truth.md` for existing UI/UX standards
   - Review existing component structure and styling approach
   - Identify current design tokens (if any)
   - Note any hard-coded values that need refactoring

2. Create or maintain centralized design tokens in a single source file (e.g., `src/design-system/tokens.ts`):
   - Colors (primary, secondary, text, background, etc.)
   - Typography (font families, sizes, weights, line heights)
   - Spacing scale
   - Shadows, border radius, transitions
   - Breakpoints and z-index values

3. Set up theme system:
   - Create theme configuration (light, dark, custom themes)
   - Set up theme provider for the application
   - Ensure all components access tokens through theme provider

4. For feature UI integration:
   - Review feature requirements from plan
   - Identify required UI components
   - Create UI specifications if needed
   - Ensure components use design tokens
   - Verify accessibility and responsive behavior

5. For research requests:
   - Research modern UI libraries and design systems
   - Compare options and provide recommendations
   - Include implementation guidance

## Rules

1. Components must NEVER use hard-coded design values (colors, spacing, typography, shadows, etc.)
2. All design values must live in the centralized tokens file
3. Components must reference tokens through theme provider
4. All components must support theme switching (light/dark/custom)
5. Maintain consistency with existing project style and patterns
6. Follow accessibility standards (WCAG guidelines, keyboard navigation, ARIA attributes)
7. Ensure responsive design works on all screen sizes
8. Document design system in `docs/design-system/` if it exists

## Component Requirements

When creating or reviewing components, verify:

- Uses design tokens (no hex colors, no px spacing, no hard-coded fonts)
- Form inputs and focusable elements use **emerald** for focus ring (e.g. `focus:ring-emerald-500`); see `frontend/docs/DESIGN_SYSTEM.md` § Forms/Inputs.
- Supports all theme variants
- Keyboard navigable and screen reader friendly
- Proper ARIA attributes
- Responsive on mobile, tablet, and desktop
- Handles loading, error, and empty states
- **Client status badge:** Use `ClientStatusBadge` (or `clientStatusVariant` from `utils/roleBadge`) for deposit/client role display in cards and tables; design tokens only. See `frontend/docs/DESIGN_SYSTEM.md` § Badges → Client status badge. **Client state rule:** use ONLY `user.role` (users) or `request.user_role` (contact requests); never `request_type` or `request.status`. See `app_truth.md` §8.
- **Dashboard Cash (EUR) card (AML):** When `user?.role === 'AML'`, the Cash (EUR) summary card must show an amber background at 50% opacity (`bg-amber-500/50`, `dark:bg-amber-400/50`) and the secondary line text "UNDER AML APPROVAL" (optionally with "Total deposited: €X · " when `totalDeposited > 0`). Use design tokens only. See `frontend/docs/DESIGN_SYSTEM.md` § Cards and `app_truth.md` §8.
- **CEA/EUA quantities:** Display certificate amounts (CEA/EUA balance, volume, order quantity) with `formatCertificateQuantity` from `utils`; use `decimals={0}` on `NumberInput` for CEA/EUA amount/quantity inputs. API payloads must send whole numbers only. See `app_truth.md` §5.
- **Custom modal overlays (Backoffice):** For non-`Modal` overlays, use `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` referencing the title `id`; see `frontend/docs/DESIGN_SYSTEM.md` (custom overlay dialogs) and `CreateUserModal.tsx`.

**Backoffice nav levels:** Subheader nav uses `.subheader-nav-btn`, `.subheader-nav-btn-active`, `.subheader-nav-btn-inactive` from `frontend/src/styles/design-tokens.css`. SubSubHeader nav (child-level, e.g. Onboarding subpages) uses `.subsubheader-nav-btn*` and count badge `.subsubheader-nav-badge`; customize via CSS variables in the same file. See `frontend/docs/DESIGN_SYSTEM.md` and `app_truth.md` §8–9.

**Admin role simulation floater:** Fixed bottom-right, z-index below modals (e.g. `z-40`). Design tokens only (navy, emerald focus); light/dark support. `aria-label` on the control group and on the select. See `app_truth.md` §8–9 and `frontend/src/components/admin/RoleSimulationFloater.tsx`.

**Settings pages:** Platform Settings (e.g. Price Scraping Sources, Mail & Authentication) use the same Card/Input patterns and design tokens; each section is wrapped in `.card_back` or `<Card />`. No hard-coded colors; use navy/emerald/amber/blue/red tokens per the design system. For table row actions (Edit, Delete, Test, etc.) use an **ActionsDropdown** (ellipsis button opening a menu); the dropdown must close on click-outside and on Escape. See `frontend/docs/DESIGN_SYSTEM.md` § Inputs → ActionsDropdown.

**Cash Market – Recent Trades (Ticker & ACTIVITY):** Both use the same list (`recentTrades` from `useCashMarket`). Use **emerald** for BUY and **red** for SELL (no slate/gray). In ACTIVITY, show relative time with full UTC timestamp on hover (e.g. via `formatFullTimestamp`). Use `flex flex-col gap-2` for consistent spacing between activity rows.

**Scroll on route change:** The app scrolls the window to top on every navigation (pathname change) so each new page opens at the top. Implemented in `App.tsx` via the `ScrollToTop` component (`useLocation` + `useEffect`). See `app_truth.md` §9.

**Charts & SVG:** Chart components (e.g. CEA price chart, CEALineChart) must use design-token CSS variables for stroke, fill, and grid colors—e.g. `var(--color-primary)`, `var(--color-text-muted)`, `var(--color-border)`, `var(--color-surface)`—instead of hex or rgb. This keeps charts consistent with the theme and passes lint rules.

**Cash Market Pro layout & CEA Price chart:** Page order: Ticker → InlineOrderForm → Order book → grid (ACTIVITY | CEA Price chart). Chart container uses the same pattern as ACTIVITY: `bg-navy-900 rounded border border-navy-700 overflow-hidden`, header with icon (e.g. TrendingUp) and title. CEA Price chart (CEAPriceChart) uses **lightweight-charts** (navy background, emerald series, grid); fetches GET /cash-market/trades/CEA?limit=100 and updates on `nihao:tradeExecuted`, applying only trades with `certificateType === 'CEA'`. See `frontend/docs/DESIGN_SYSTEM.md` and `app_truth.md` §8.

## Output

1. **Design System Documentation**: Update `docs/design-system/` with tokens, themes, and components
2. **UI Specifications**: Create `docs/features/<N>_UI_SPEC.md` for feature UI requirements
3. **Component Implementation**: Create components following project structure, using tokens
4. **Research Reports**: Create `docs/ui-research/UI_RESEARCH_<topic>_<date>.md` for research findings
5. **app-truth.md Updates**: Update UI/UX section with design system location, patterns, and standards

Prioritize being concise and actionable. Focus on creating a centralized system that enables one-command theme changes.
