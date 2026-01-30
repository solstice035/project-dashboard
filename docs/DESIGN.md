# Project Dashboard - Design Documentation

> UI/UX design principles, visual system, and component specifications.

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Visual Design System](#visual-design-system)
3. [Component Library](#component-library)
4. [Layout Patterns](#layout-patterns)
5. [Interaction Design](#interaction-design)
6. [Accessibility](#accessibility)
7. [Responsive Design](#responsive-design)

---

## Design Philosophy

### Core Principles

1. **Information Density**: Show maximum useful data without overwhelming
2. **Dark Mode First**: Optimized for developer environments and reduced eye strain
3. **Glanceable**: Key metrics visible within 2 seconds
4. **Actionable**: Every piece of information leads to potential action
5. **Consistent**: Unified visual language across all components

### Design Goals

| Goal | Implementation |
|------|----------------|
| Quick scanning | Status indicators, color coding, counts |
| Focus support | Clean layout, minimal distractions |
| Context awareness | Tabs for different mental modes |
| Progressive disclosure | Summary → Detail on demand |

---

## Visual Design System

### Color Palette

```css
/* Base Colors */
--bg-primary: #0f0f1a;      /* Deep space - main background */
--bg-secondary: #1a1a2e;    /* Midnight - secondary surfaces */
--bg-card: #16213e;         /* Card backgrounds */
--border: #2d3748;          /* Subtle borders */

/* Text Hierarchy */
--text-primary: #e2e8f0;    /* Primary text - high contrast */
--text-secondary: #a0aec0;  /* Secondary text */
--text-muted: #718096;      /* Muted/disabled text */

/* Accent Colors */
--accent-teal: #38b2ac;     /* Primary accent - actions, links */
--accent-cyan: #0bc5ea;     /* In progress, active states */
--accent-coral: #fc8181;    /* Warnings, overdue, errors */
--accent-orange: #f6ad55;   /* Medium priority, warnings */
--accent-green: #68d391;    /* Success, healthy, complete */
--accent-purple: #b794f4;   /* Code, commits, technical */
```

### Color Usage Matrix

```
┌─────────────────┬──────────────┬─────────────────────────────┐
│ Context         │ Color        │ Usage                       │
├─────────────────┼──────────────┼─────────────────────────────┤
│ Primary Action  │ Teal         │ Buttons, links, focus       │
│ In Progress     │ Cyan         │ Active items, current task  │
│ Overdue/Error   │ Coral        │ Urgent items, errors        │
│ Warning         │ Orange       │ Attention needed            │
│ Success         │ Green        │ Completed, healthy          │
│ Code/Technical  │ Purple       │ Commit hashes, code refs    │
│ High Priority   │ Coral        │ P1 tasks                    │
│ Medium Priority │ Orange       │ P2 tasks                    │
│ Low Priority    │ Yellow       │ P3 tasks                    │
│ Normal Priority │ White/None   │ P4 tasks                    │
└─────────────────┴──────────────┴─────────────────────────────┘
```

### Typography

```css
/* Font Stack */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Monospace (code) */
font-family: 'SF Mono', Monaco, 'Fira Code', monospace;

/* Scale */
--text-xs: 0.7rem;    /* Tags, timestamps */
--text-sm: 0.75rem;   /* Meta info, labels */
--text-base: 0.875rem; /* Body text */
--text-lg: 1rem;      /* Card titles */
--text-xl: 1.75rem;   /* Page title */
--text-2xl: 2rem;     /* Large stats */

/* Line Height */
line-height: 1.5;     /* Body text */
line-height: 1.2;     /* Headings */
```

### Spacing System

```css
/* Base unit: 0.25rem (4px) */
--space-1: 0.25rem;   /* 4px  - Tight */
--space-2: 0.5rem;    /* 8px  - Compact */
--space-3: 0.75rem;   /* 12px - Default */
--space-4: 1rem;      /* 16px - Comfortable */
--space-5: 1.25rem;   /* 20px - Relaxed */
--space-6: 1.5rem;    /* 24px - Spacious */
```

### Border Radius

```css
--radius-sm: 4px;     /* Tags, small elements */
--radius-md: 6px;     /* Buttons, inputs */
--radius-lg: 8px;     /* Items, smaller cards */
--radius-xl: 12px;    /* Cards, modals */
--radius-full: 9999px; /* Pills, badges */
```

### Shadows & Depth

```css
/* Minimal shadows for dark theme */
/* Depth achieved through background color variations */

/* Hover glow effect */
box-shadow: 0 0 0 1px var(--accent-teal);
```

---

## Component Library

### Cards

```
┌─────────────────────────────────────────┐
│ Card Header                    [Badge]  │
├─────────────────────────────────────────┤
│                                         │
│  Card Content                           │
│                                         │
│  • Item 1                               │
│  • Item 2                               │
│  • Item 3                               │
│                                         │
└─────────────────────────────────────────┘

Specs:
- Background: var(--bg-card)
- Border: 1px solid var(--border)
- Border radius: 12px
- Padding: 1.25rem
- Min height: 300px (dashboard), auto (detail)
- Header border-bottom: 1px solid var(--border)
```

### Status Dots

```
 ⚫ Loading (pulsing animation)
 🟢 OK / Connected
 🟡 Warning / Not configured
 🔴 Error / Failed

Specs:
- Size: 10px × 10px
- Border radius: 50%
- Animation: pulse 1s infinite (loading state)
```

### Buttons

```
┌─────────────────┐
│  ↻ Refresh      │  Primary action
└─────────────────┘

┌─────────────────┐
│  Start Session  │  Accent button
└─────────────────┘

┌─────────────────┐
│  🎯 Focus       │  Quick action (pill)
└─────────────────┘

Specs:
- Primary: bg-card, border, hover:border-teal
- Accent: bg-teal, color:bg-primary
- Pill: bg-secondary, border, radius-full
- Padding: 0.5rem 1rem (standard), 0.375rem 0.75rem (small)
- Disabled: opacity 0.5, cursor not-allowed
```

### Items (List entries)

```
┌─────────────────────────────────────────┐
│▌ 🔴 Task title goes here               │
│  project-name · due: 2026-01-30        │
└─────────────────────────────────────────┘

Specs:
- Background: var(--bg-secondary)
- Border radius: 8px
- Padding: 0.75rem
- Margin bottom: 0.5rem
- Left border: 3px solid (context color)
  - Overdue: coral
  - Today: teal
  - In progress: cyan
  - Default: transparent
```

### Tags / Badges

```
┌─────────┐  ┌─────────────┐
│ project │  │ 3 overdue   │
└─────────┘  └─────────────┘

Specs:
- Background: var(--bg-primary)
- Border radius: 4px (tag), 9999px (badge)
- Padding: 0.125rem 0.375rem (tag), 0.125rem 0.5rem (badge)
- Font size: 0.7rem (tag), 0.75rem (badge)
```

### Chat Messages

```
User message:                          ┌─────────────────────┐
                                       │ What should I do?   │
                                       │ ───────────         │
                                       │         07:15       │
                                       └─────────────────────┘

┌─────────────────────────────┐
│ Based on your tasks, I'd    │  Assistant message
│ recommend focusing on...    │
│ ───────────                 │
│ 07:15                       │
└─────────────────────────────┘

        Session started          System message

Specs:
- Max width: 85%
- User: bg-teal, color:bg-primary, align:right, radius:12px 12px 4px 12px
- Assistant: bg-secondary, align:left, radius:12px 12px 12px 4px
- System: transparent, centered, italic, muted
- Padding: 0.75rem 1rem
- Timestamp: 0.7rem, muted
```

### Tabs

```
[☀️ Standup] [💬 Plan] [📊 Dashboard] [📈 Analytics]
                        ▔▔▔▔▔▔▔▔▔▔▔▔▔

Specs:
- Background: transparent (default), bg-card (active)
- Color: text-secondary (default), accent-teal (active)
- Border bottom: 2px solid teal (active)
- Padding: 0.75rem 1.5rem
- Border radius: 6px 6px 0 0
```

### Input Fields

```
┌─────────────────────────────────────────┐
│ What should I focus on today?           │
└─────────────────────────────────────────┘

Specs:
- Background: var(--bg-secondary)
- Border: 1px solid var(--border)
- Border radius: 8px
- Padding: 0.75rem 1rem
- Focus: border-color: var(--accent-teal)
```

---

## Layout Patterns

### Grid System

```css
/* Dashboard grid - 2 columns */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}

/* Full width card */
.card.full-width {
  grid-column: 1 / -1;
}

/* Plan split view */
.plan-container {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 1.5rem;
}

/* Stats grid - 4 columns */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
```

### Page Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Header                                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Title                          Status | Refresh | Time  ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  Navigation Tabs                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [Tab1] [Tab2] [Tab3] [Tab4] [Tab5]                      ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  Content Area                                                │
│  ┌───────────────────────┐  ┌───────────────────────┐      │
│  │                       │  │                       │      │
│  │       Card 1          │  │       Card 2          │      │
│  │                       │  │                       │      │
│  └───────────────────────┘  └───────────────────────┘      │
│  ┌───────────────────────┐  ┌───────────────────────┐      │
│  │                       │  │                       │      │
│  │       Card 3          │  │       Card 4          │      │
│  │                       │  │                       │      │
│  └───────────────────────┘  └───────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Plan Tab Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Context Panel (350px)        │  Chat Panel (flex: 1)       │
│ ┌───────────────────────────┐ │ ┌─────────────────────────┐ │
│ │ Section Title             │ │ │ Header          [End]  │ │
│ │ ┌───────────────────────┐ │ │ ├─────────────────────────┤ │
│ │ │ Item                  │ │ │ │                         │ │
│ │ │ Item                  │ │ │ │  Messages               │ │
│ │ │ Item                  │ │ │ │  (flex: 1, scroll)      │ │
│ │ └───────────────────────┘ │ │ │                         │ │
│ │                           │ │ │                         │ │
│ │ Section Title             │ │ ├─────────────────────────┤ │
│ │ ┌───────────────────────┐ │ │ │ Input + Send            │ │
│ │ │ Item                  │ │ │ │ [Quick] [Actions]       │ │
│ │ └───────────────────────┘ │ │ └─────────────────────────┘ │
│ └───────────────────────────┘ │                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Interaction Design

### States

| State | Visual Indicator |
|-------|------------------|
| Default | Base styling |
| Hover | Border color change, subtle glow |
| Active | Pressed appearance |
| Disabled | 50% opacity, no pointer |
| Loading | Pulse animation, skeleton |
| Error | Red border, error message |
| Success | Green accent, checkmark |

### Animations

```css
/* Smooth transitions */
transition: all 0.2s ease;

/* Loading pulse */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Skeleton shimmer */
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Spinner rotation */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Typing dots */
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}
```

### Feedback Patterns

| Action | Feedback |
|--------|----------|
| Refresh clicked | Button disabled, spinner, dots pulse |
| Data loaded | Status dot green, timestamp updates |
| Error occurred | Status dot red, error message shown |
| Message sent | Message appears in chat, typing indicator |
| Session started | Status text updates, input enabled |

---

## Accessibility

### Color Contrast

All text combinations meet WCAG AA standards:
- Primary text on bg-primary: 11.5:1
- Secondary text on bg-card: 7.2:1
- Muted text on bg-secondary: 4.8:1

### Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move between interactive elements |
| Enter | Activate button, send message |
| Escape | Close modal, cancel action |

### Screen Reader Support

- Semantic HTML structure
- ARIA labels on icons
- Status announcements
- Focus management

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Responsive Design

### Breakpoints

```css
/* Mobile: < 600px */
/* Tablet: 600px - 900px */
/* Desktop: > 900px */

@media (max-width: 900px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .plan-container {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

### Mobile Considerations

- Touch targets: minimum 44px × 44px
- Larger tap areas for buttons
- Simplified navigation
- Stack layout for cards
- Full-width chat interface

---

## Design Tokens (CSS Custom Properties)

```css
:root {
  /* Colors */
  --bg-primary: #0f0f1a;
  --bg-secondary: #1a1a2e;
  --bg-card: #16213e;
  --border: #2d3748;
  --text-primary: #e2e8f0;
  --text-secondary: #a0aec0;
  --text-muted: #718096;
  --accent-teal: #38b2ac;
  --accent-cyan: #0bc5ea;
  --accent-coral: #fc8181;
  --accent-orange: #f6ad55;
  --accent-green: #68d391;
  --accent-purple: #b794f4;
  
  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'SF Mono', Monaco, 'Fira Code', monospace;
  
  /* Spacing */
  --space-unit: 0.25rem;
  
  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  
  /* Transitions */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.2s ease;
  --transition-slow: 0.3s ease;
}
```

---

*Last updated: 2026-01-30*
