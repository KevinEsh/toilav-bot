---
name: toilav-dashboard-ui
description: "Skill for creating professional, modern, minimalist UI components for the toilav-bot admin dashboard. Use this skill whenever building or modifying any frontend screen, component, or layout for the dashboard — including the product catalog, order management, FAQs, metrics, modals, forms, tables, cards, or navigation. Also trigger when the user asks to 'make it look better', 'redesign', 'style', or 'beautify' any part of the dashboard. Stack: React + Vite + Tailwind CSS + shadcn/ui."
---

# Toilav Dashboard UI Skill

Build every dashboard screen and component following this guide. Read it fully before writing any frontend code.

## Design Philosophy

The dashboard is for **Tremenda Nuez**, a premium artisanal nut and snack business. The UI must feel:

- **Clean & modern** — like Shopify, Linear, or Vercel's dashboards
- **Minimalist** — every element earns its place, generous whitespace
- **Elegant** — subtle refinements that feel premium, not generic
- **Trustworthy** — a store owner should feel confident managing their business here

**Golden rule:** if it looks like a default shadcn/ui demo, it's not done yet. Every screen needs at least one intentional design touch that makes it feel custom.

## Tech Stack (non-negotiable)

| Tool | Usage |
|---|---|
| React 18+ | Component framework |
| Vite | Build tool |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Base component library |
| Lucide React | Icons (already bundled with shadcn) |
| React Router | Navigation |

**Rules:**
- Never install additional UI libraries (no MUI, Chakra, Ant Design, etc.)
- Never use inline styles — Tailwind only
- Never use generic CSS classes — leverage Tailwind's design tokens
- All components must be functional (no class components)

## Color System

Use CSS variables in `index.css` for theming. The palette is warm-neutral with a single strong accent.

```css
:root {
  /* Base */
  --background: 0 0% 98%;        /* almost white, slight warmth */
  --foreground: 20 15% 15%;      /* warm near-black */
  
  /* Card & surfaces */
  --card: 0 0% 100%;
  --card-foreground: 20 15% 15%;
  --muted: 30 10% 96%;
  --muted-foreground: 20 5% 45%;
  
  /* Primary — warm amber/walnut */
  --primary: 28 80% 52%;          /* #D4872E — walnut gold */
  --primary-foreground: 0 0% 100%;
  
  /* Secondary — soft sage */  
  --secondary: 140 15% 94%;
  --secondary-foreground: 140 10% 30%;
  
  /* Accent — for highlights and hover states */
  --accent: 30 15% 93%;
  --accent-foreground: 20 15% 15%;
  
  /* Destructive */
  --destructive: 0 72% 51%;
  --destructive-foreground: 0 0% 100%;
  
  /* Borders & inputs */
  --border: 30 10% 90%;
  --input: 30 10% 90%;
  --ring: 28 80% 52%;
  
  /* Radius */
  --radius: 0.5rem;
  
  /* Sidebar */
  --sidebar-bg: 20 15% 12%;
  --sidebar-foreground: 30 10% 85%;
  --sidebar-accent: 28 80% 52%;
}
```

**Color usage rules:**
- Background is never pure white — use `--background` (warm off-white)
- Text is never pure black — use `--foreground` (warm dark)
- Primary (walnut gold) is used sparingly: CTAs, active states, key indicators
- Borders are subtle — `border-border` not heavy gray lines
- Status colors: green for success/delivered, amber for pending, red for issues, blue for info

## Typography

```css
/* In index.css or tailwind config */
font-family: 'DM Sans', sans-serif;       /* body text */
font-family: 'Plus Jakarta Sans', sans-serif; /* headings */
```

Import from Google Fonts in `index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">
```

**Typography scale:**
- Page titles: `text-2xl font-bold` (Plus Jakarta Sans)
- Section headers: `text-lg font-semibold` (Plus Jakarta Sans)
- Body text: `text-sm font-normal` (DM Sans)
- Labels & captions: `text-xs font-medium text-muted-foreground`
- Monospace (prices, IDs): `font-mono tabular-nums`

**Rules:**
- Never use more than 2 font weights on the same card
- Prices always in `font-mono` for alignment
- Truncate long text with `truncate` or `line-clamp-2`, never let it wrap and break layout

## Layout Architecture

### App Shell
```
┌─────────────────────────────────────────────────┐
│  Sidebar (240px fixed)  │  Main Content Area     │
│                         │                        │
│  ┌─ Logo ─────────┐    │  ┌─ Top bar ─────────┐ │
│  │ 🥜 Tremenda    │    │  │ Page title + actions│ │
│  │    Nuez        │    │  └────────────────────┘ │
│  └────────────────┘    │                        │
│                         │  ┌─ Content ─────────┐ │
│  Nav items:             │  │                    │ │
│  📦 Catálogo           │  │  (page content)    │ │
│  📋 Órdenes            │  │                    │ │
│  💬 FAQs               │  │                    │ │
│  📊 Métricas           │  │                    │ │
│                         │  └────────────────────┘ │
│                         │                        │
│  ┌─ Store info ───┐    │                        │
│  │ Tremenda Nuez  │    │                        │
│  │ Plan Básico    │    │                        │
│  └────────────────┘    │                        │
└─────────────────────────────────────────────────┘
```

**Sidebar:**
- Dark background (`--sidebar-bg`) — warm charcoal, not cold gray
- Width: `w-60` fixed
- Nav items: icon + label, `px-3 py-2 rounded-lg`
- Active state: `bg-white/10 text-white` with left accent bar (3px, primary color)
- Hover: `bg-white/5` transition
- Logo at top, store info at bottom

**Main content:**
- Top bar: page title (left) + primary action button (right)
- Content area: `max-w-6xl mx-auto px-6 py-6`
- Never full-bleed — always padded and contained

### Spacing System
- Between sections: `space-y-6`
- Between cards in a grid: `gap-4`
- Card internal padding: `p-5` (not p-4, slightly more generous)
- Form field spacing: `space-y-4`

## Component Patterns

### Cards
```jsx
// Standard card pattern
<Card className="border border-border/50 shadow-sm hover:shadow-md transition-shadow">
  <CardHeader className="pb-3">
    <CardTitle className="text-lg font-semibold">Title</CardTitle>
    <CardDescription>Subtitle text</CardDescription>
  </CardHeader>
  <CardContent>
    {/* content */}
  </CardContent>
</Card>
```

- Always use `border-border/50` (subtle, not heavy)
- Add `hover:shadow-md transition-shadow` on interactive cards
- Never stack more than 2 levels of cards (no card inside card inside card)

### Product Cards (Catalog Screen)
Follow WhatsApp Business catalog style:
```
┌──────────────────────────────────────┐
│ [IMG 80x80]  Product Name            │
│              Description text...      │
│              $XXX.XX MXN        [⋯]  │
└──────────────────────────────────────┘
```

- Horizontal layout: image left, info right
- Image: `w-20 h-20 rounded-lg object-cover bg-muted`
- If no image: show placeholder with `ImageIcon` from Lucide in muted color
- Product name: `font-semibold text-sm`
- Description: `text-xs text-muted-foreground line-clamp-1`
- Price: `font-mono text-sm font-semibold text-primary`
- Group products by category with a subtle header
- Three-dot menu (⋯) for edit/delete actions

### Image Lightbox (Preview Grande)
Whenever a product has an image, clicking on the thumbnail debe abrir un preview grande.
Use shadcn Dialog como lightbox:

```jsx
// ImageLightbox.jsx — reusable component
<Dialog>
  <DialogTrigger asChild>
    <button className="cursor-zoom-in">
      <img src={url} className="w-20 h-20 rounded-lg object-cover" />
    </button>
  </DialogTrigger>
  <DialogContent className="max-w-2xl p-2 bg-black/95 border-none">
    <img 
      src={url} 
      alt={productName}
      className="w-full h-auto max-h-[80vh] object-contain rounded-lg"
    />
    <p className="text-center text-white/70 text-sm mt-2">{productName}</p>
  </DialogContent>
</Dialog>
```

**Rules:**
- Thumbnail cursor: `cursor-zoom-in` to signal clickability
- Lightbox background: near-black (`bg-black/95`) to focus attention on image
- Image inside lightbox: `object-contain` (never crop), max height `80vh`
- Show product name below image as caption
- Close with X button or clicking outside (shadcn Dialog handles this)
- Smooth open/close animation (Dialog default transition is fine)
- Use this same component everywhere images appear: catalog cards, order detail, etc.

### Tables (Orders, FAQs)
Use shadcn Table component with these tweaks:
- Header row: `bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground`
- Row hover: `hover:bg-muted/30`
- No heavy borders between rows — use `divide-y divide-border/50`
- Status badges: use shadcn Badge with custom variants
- Align prices/numbers to the right
- Empty state: centered illustration or icon + message + CTA

### Status Badges
```jsx
// Order statuses
const statusConfig = {
  PENDING_APPROVAL:     { label: 'Pendiente',    variant: 'outline',     className: 'border-amber-300 text-amber-700 bg-amber-50' },
  APPROVED:             { label: 'Aprobada',     variant: 'outline',     className: 'border-blue-300 text-blue-700 bg-blue-50' },
  PENDING_PAYMENT:      { label: 'Por pagar',    variant: 'outline',     className: 'border-orange-300 text-orange-700 bg-orange-50' },
  PENDING_DELIVERY:     { label: 'Por entregar', variant: 'outline',     className: 'border-purple-300 text-purple-700 bg-purple-50' },
  DELIVERY_IN_COURSE:   { label: 'En camino',    variant: 'outline',     className: 'border-cyan-300 text-cyan-700 bg-cyan-50' },
  COMPLETED:            { label: 'Completada',   variant: 'outline',     className: 'border-green-300 text-green-700 bg-green-50' },
  CANCELLED:            { label: 'Cancelada',    variant: 'outline',     className: 'border-red-300 text-red-700 bg-red-50' },
};
```

### Forms & Modals
- Use shadcn Dialog for modals
- Modal max-width: `max-w-lg` for simple forms, `max-w-2xl` for complex ones
- Form layout: single column, labels above inputs
- Required fields: red asterisk after label
- Image upload: drag-and-drop zone with dashed border, preview thumbnail after upload. Clicking the preview opens ImageLightbox to verify the image looks correct before saving.
- Submit buttons: primary color, full width at bottom of modal
- Cancel: ghost variant, left of submit

### Buttons
- Primary CTA: `bg-primary text-primary-foreground hover:bg-primary/90`
- Secondary: `bg-secondary text-secondary-foreground`
- Destructive: only for delete confirmations
- Ghost: for secondary actions in toolbars
- Icon buttons: `size="icon" variant="ghost"` with tooltip
- Always add `transition-colors` for smooth hover

### Empty States
Every screen needs a beautiful empty state:
```
     [Relevant Lucide icon, 48px, muted color]
     
     No hay [items] aún
     Descripción breve de qué hacer
     
     [+ Agregar primer item]  (primary button)
```

Center vertically and horizontally in the content area.

## Screen-Specific Guidelines

### 1. Catálogo de Productos
- Top bar: "Catálogo" + search input + "Agregar producto" button
- Filter by category (tabs or dropdown)
- Product list grouped by category
- Each product is a horizontal card (WhatsApp style)
- Click card → edit modal
- Three-dot menu → edit / delete
- Image upload in create/edit modal connects to MinIO endpoint

### 2. Gestión de Órdenes
- Top bar: "Órdenes" + filter dropdown (status) + date range picker
- Table layout with columns: ID, Cliente, Items (summary), Total, Estado, Fecha
- Click row → order detail drawer or modal
- Order detail shows: customer info, items list, delivery details, status timeline
- Status timeline: vertical steps showing the order's journey through phases

### 3. FAQs / Base de Conocimiento
- Top bar: "Base de Conocimiento" + search + "Agregar FAQ" button
- Card grid or list of Q&A pairs
- Each card: question as title, answer preview, category tag
- Edit in-place or via modal
- Show indicator if FAQ came from owner intervention (auto-learned)

### 4. Métricas / Analytics
- Top bar: "Métricas" + date range selector
- KPI cards row at top: Total órdenes, Ingresos, Ticket promedio, Tasa de completado
- KPI cards: large number + small trend indicator (↑ ↓) + sparkline
- Charts below: orders over time (line), orders by status (donut), top products (horizontal bar)
- Use Recharts (already available in the project)

## Micro-interactions & Polish

- **Page transitions:** fade-in on route change (`opacity-0 → opacity-100`, 150ms)
- **Card hover:** subtle shadow elevation (`shadow-sm → shadow-md`)
- **Button press:** slight scale down (`active:scale-[0.98]`)
- **Loading states:** use shadcn Skeleton, never a spinning wheel alone
- **Toast notifications:** use shadcn Toast, position top-right
- **Sidebar nav:** smooth background transition on hover (200ms)

## Anti-patterns (never do these)

- ❌ Pure white (#fff) backgrounds — always use the warm off-white
- ❌ Pure black (#000) text — use warm dark
- ❌ Heavy drop shadows — keep shadows subtle (shadow-sm, shadow-md max)
- ❌ Rounded corners larger than `rounded-xl` — keep it refined
- ❌ More than 3 font sizes on one screen
- ❌ Neon or saturated accent colors — keep the palette warm and muted
- ❌ Generic placeholder text ("Lorem ipsum") — use realistic Mexican Spanish
- ❌ Console.log statements in production code
- ❌ Hardcoded colors — always use CSS variables or Tailwind theme
- ❌ Default browser focus rings — style with `ring-ring` from theme

## File Structure

```
app/services/frontend/src/
├── components/
│   ├── ui/              ← shadcn components (don't modify these)
│   ├── layout/
│   │   ├── Sidebar.jsx
│   │   ├── TopBar.jsx
│   │   └── AppShell.jsx
│   ├── shared/
│   │   └── ImageLightbox.jsx  ← reusable image preview
│   ├── catalog/
│   │   ├── ProductCard.jsx
│   │   ├── ProductForm.jsx
│   │   ├── ProductList.jsx
│   │   └── CategoryGroup.jsx
│   ├── orders/
│   │   ├── OrderTable.jsx
│   │   ├── OrderDetail.jsx
│   │   ├── StatusBadge.jsx
│   │   └── StatusTimeline.jsx
│   ├── faqs/
│   │   ├── FaqCard.jsx
│   │   ├── FaqForm.jsx
│   │   └── FaqList.jsx
│   └── metrics/
│       ├── KpiCard.jsx
│       ├── OrdersChart.jsx
│       └── TopProducts.jsx
├── pages/
│   ├── CatalogPage.jsx
│   ├── OrdersPage.jsx
│   ├── FaqsPage.jsx
│   └── MetricsPage.jsx
├── lib/
│   └── api.js           ← API client (fetch wrapper)
├── hooks/
│   └── useApi.js        ← data fetching hook
└── App.jsx
```

**Rules:**
- One component per file
- Components go in feature folders, not a flat `components/` dump
- Pages are thin — they compose components, don't contain logic
- API calls live in `lib/api.js`, never directly in components

## Checklist Before Delivering Any Screen

Before considering a screen done, verify:

- [ ] Colors use CSS variables, no hardcoded values
- [ ] Typography follows the scale (no random sizes)
- [ ] Empty state exists and looks good
- [ ] Loading state uses Skeleton components
- [ ] Error state shows a friendly message with retry option
- [ ] All interactive elements have hover/focus states
- [ ] Spacing is consistent (follows the spacing system)
- [ ] Text in Spanish (Mexican), realistic sample data
- [ ] No console errors or warnings
- [ ] Connects to real API endpoints (not mock data)
