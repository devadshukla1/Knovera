# Knovera — UI/UX Design Brief

| Field | Value |
|---|---|
| Product | **Knovera** |
| Version | 1.0 |
| Status | Baseline design system direction |
| Last updated | 5 November 2026 |
| Tagline | **Turn Information into Intelligence.** |

> **Purpose:** Establish a consistent visual language and interaction system. Knovera should feel like a premium research and knowledge workspace: focused, calm, precise, and capable. Avoid generic AI gradients, excessive glow, decorative dashboards, and oversized empty application screens.

---

## 1. Brand and visual direction

### 1.1 Brand attributes

- Intelligent, but not intimidating.
- Research-oriented, yet welcoming to students.
- Precise, calm, and evidence-first.
- Modern and technical without looking like a developer-only admin panel.
- Focused on connected ideas and trustworthy sources.

### 1.2 Brand line

**Knovera — Turn Information into Intelligence.**

### 1.3 Visual metaphor

Use connected points, linked source references, and layered knowledge panels as subtle recurring motifs. The identity can suggest a network of ideas without turning every card or background into a node graph.

### 1.4 Aesthetic direction

- Dark-first application experience.
- Deep ink/navy foundations with violet as primary brand accent.
- Muted teal for secondary data/knowledge emphasis.
- Clean typography and clear information hierarchy.
- Fine borders, restrained elevation, and efficient spacing.
- Dense data views remain readable and structured.

Avoid:
- Large neon glows around every component.
- Rainbow gradients.
- Generic AI brain/robot imagery.
- Excessive glassmorphism that harms contrast.
- Decorative charts with no meaningful data.
- Constant animations or animated background particles.

---

## 2. Colour system

Use semantic tokens rather than hardcoding hex values inside components. Values are the initial design baseline and must be checked for contrast during implementation.

### 2.1 Dark theme (default)

| Token | Hex | Usage |
|---|---|---|
| `--background` | `#0B0D14` | Main application background |
| `--surface` | `#121625` | Sidebar, panels, cards |
| `--surface-elevated` | `#191F31` | Dialogs, popovers, elevated cards |
| `--surface-muted` | `#20283B` | Inputs, hover surfaces, secondary wells |
| `--border` | `#2A3348` | Dividers and card outlines |
| `--text-primary` | `#F4F5FB` | Main text |
| `--text-secondary` | `#B1B9CC` | Supporting text |
| `--text-muted` | `#8791A8` | Metadata/disabled text; verify contrast per use |
| `--primary` | `#8B7CFF` | Primary actions and active navigation |
| `--primary-hover` | `#A095FF` | Primary hover |
| `--primary-soft` | `#282343` | Subtle primary background |
| `--primary-foreground` | `#100D27` | Text/icons on primary fill |
| `--accent` | `#58D6C7` | Knowledge/data accent |
| `--success` | `#42C98A` | Completed/ready/success |
| `--warning` | `#F2B35B` | Caution/partial evidence |
| `--danger` | `#F06F83` | Error/destructive actions |
| `--info` | `#62B6F5` | Informational status |

### 2.2 Light theme

| Token | Hex | Usage |
|---|---|---|
| `--background` | `#F7F8FC` | Main background |
| `--surface` | `#FFFFFF` | Cards/sidebar/panels |
| `--surface-elevated` | `#FFFFFF` | Dialogs/elevated surfaces |
| `--surface-muted` | `#EEF0F7` | Inputs/secondary surfaces |
| `--border` | `#DDE1EC` | Dividers/outlines |
| `--text-primary` | `#171A27` | Main text |
| `--text-secondary` | `#535C70` | Supporting text |
| `--text-muted` | `#70798D` | Metadata; verify contrast per use |
| `--primary` | `#6556E8` | Primary actions |
| `--primary-hover` | `#5545D7` | Primary hover |
| `--primary-soft` | `#ECEAFF` | Subtle primary surface |
| `--primary-foreground` | `#FFFFFF` | Text/icons on primary fill |
| `--accent` | `#087F78` | Knowledge/data accent |
| `--success` | `#18794E` | Completed/ready/success |
| `--warning` | `#9A5B00` | Caution/partial evidence |
| `--danger` | `#B4233D` | Error/destructive actions |
| `--info` | `#1769AA` | Informational status |

### 2.3 Colour rules

- Colour is never the only way to communicate status; add text or an icon.
- Violet is the primary action colour, not a background colour for every section.
- Teal is secondary and must not compete with primary actions.
- Warning amber is for incomplete/uncertain evidence, not decoration.
- Verify text and control contrast against WCAG AA targets wherever feasible.
- Do not use status colours as arbitrary chart series colours without semantic meaning.

---

## 3. Typography

### 3.1 Typeface

Primary typeface: **Inter**. Use a system fallback if unavailable. Do not block rendering on a remote font request. If self-hosting the font, include the correct licence; do not fetch fonts at runtime from an unapproved source.

```css
font-family: Inter, ui-sans-serif, system-ui, -apple-system,
             BlinkMacSystemFont, "Segoe UI", sans-serif;
```

### 3.2 Type scale

| Token | Size | Weight | Usage |
|---|---:|---:|---|
| Display | 36–40 px | 650–700 | Marketing hero only |
| H1 | 28–32 px | 650 | Page title |
| H2 | 22–24 px | 600 | Major section title |
| H3 | 18–20 px | 600 | Card/panel title |
| Body large | 16 px | 400–500 | Introductory copy |
| Body | 14–15 px | 400 | Main UI text |
| Label | 13 px | 500–600 | Input labels/controls |
| Caption | 12 px | 400–500 | Metadata/timestamps |
| Code/data | 12–14 px | 450 | IDs and technical values; monospace |

Body line height should generally be 1.45–1.6. Dense tables may use 1.35 if readability remains acceptable.

---

## 4. Spacing, layout, and shape

### 4.1 Spacing scale

Use a 4 px base scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80 px`.

Prefer consistent tokens over arbitrary values. Standard cards use about 16 px internal padding; dense panels may use 12 px and larger feature panels 24 px.

### 4.2 Layout grid

- App shell: fixed/collapsible left navigation on desktop; compact drawer on small screens.
- Main content: fluid width with readable maximum width for text-heavy pages.
- Chat: central conversation column with collapsible citation/source side panel.
- Research comparison: horizontally scrollable table on narrow screens rather than compressed unreadable columns.
- Knowledge graph: graph canvas with adjacent detail panel; panels may stack on mobile.

### 4.3 Breakpoints

| Breakpoint | Width | Behaviour |
|---|---:|---|
| `sm` | 640 px | Small device layout adjustments |
| `md` | 768 px | Tablet navigation/layout |
| `lg` | 1024 px | Desktop navigation and split panels |
| `xl` | 1280 px | Full workspace layout |
| `2xl` | 1536 px | Wider content without excessive line length |

### 4.4 Radius and borders

- Small controls: 8 px radius.
- Standard cards/inputs: 10–12 px radius.
- Large panels/dialogs: 14–16 px radius.
- Pills: fully rounded only for compact labels/status chips.
- Borders: 1 px semantic border; avoid nested outlines around every element.

### 4.5 Elevation

- Default cards: border, no obvious shadow.
- Popovers/dialogs: modest shadow.
- Selected/active panel: subtle border/accent, not a large glow.

---

## 5. Component system

### 5.1 Library

Use **shadcn/ui** components built on Radix UI primitives and styled with Tailwind CSS. Keep component source in the repository for project-specific styling and accessibility control.

Recommended primitives:
- Button, Input, Textarea, Label, Select, Checkbox, Radio Group, Switch.
- Dialog, Sheet, Dropdown Menu, Popover, Tooltip.
- Tabs, Accordion, Separator, Scroll Area.
- Table, Badge, Skeleton, Alert, Progress, Toast/Sonner.
- Command/combobox for searchable document and concept selection.

Use Lucide icons with consistent stroke width and size. Avoid mixing icon libraries.

### 5.2 Shared product components

`AppSidebar`, `TopBar`, `WorkspaceSwitcher`, `Breadcrumbs`, `PageHeader`, `EmptyState`, `ErrorState`, `LoadingSkeleton`, `StatusBadge`, `DocumentRow`, `UploadDropzone`, `CitationMarker`, `SourceViewer`, `MessageBubble`, `ChatComposer`, `EvidencePanel`, `TopicCard`, `ConceptDetailPanel`, `QuizQuestionCard`, and `MetricCard`.

These are component concepts, not a requirement to create all of them in Phase 0. Implement each when its feature phase begins.

### 5.3 Button hierarchy

- **Primary:** one visually dominant action per view/modal (Upload, Send, Generate).
- **Secondary:** supporting actions (Cancel, Filter, Open).
- **Ghost/tertiary:** low-emphasis navigation/inline actions.
- **Destructive:** deletion and other irreversible actions; require confirmation.

Do not put multiple competing primary buttons in one compact panel.

---

## 6. Screen-specific design direction

### 6.1 Landing page

- Clear product name and tagline.
- Explain the document → evidence → connected knowledge → learning story.
- One primary CTA and one secondary CTA.
- Product visuals must reflect real capabilities.
- Never create fake analytics or fake AI responses for decoration.

### 6.2 App overview

- Compact welcome/header region.
- Workspace cards and recent documents.
- Clear onboarding empty state.
- Metrics only when backed by API data.

### 6.3 Workspace/document library

- Prioritise file name, type, processing status, and last update.
- Use clear status text, not coloured dots alone.
- Upload area should not dominate once files exist.
- Keep list/table density readable.

### 6.4 Research chat

- Conversation occupies the main width.
- User and assistant messages are distinct but not bubble-heavy.
- Citations are compact, inline, keyboard-accessible source controls.
- Source panel displays a readable passage and source metadata.
- Markdown answer rendering sanitises unsafe HTML and links.
- Partial/insufficient evidence uses clear neutral/warning callouts.

### 6.5 Topic Explorer

- Responsive 1-col / 2-col / 3-col topic card grid displaying topic labels, cluster key badge, synthesis description, ranked keyword chips with score percentages, and chunk/document provenance badges.
- Metric cards bar displaying discovered topics, clustered chunks, contributing documents, and active K-Means K value.
- Historical run selector dropdown with active run indicator and completion timestamp.
- Real-time search and sorting toolbar (by chunk count, document count, alphabetical, and cluster key).
- Deep Topic Detail view presenting comprehensive topic metadata, keyword cloud, and paginated assigned chunk list with links directly into the source document viewer.
- Polished empty states for workspaces without topics and empty search results.

### 6.6 Knowledge Explorer

- Quiet graph background; restrained node/edge colours.
- Selected node/edge has a clear focus treatment.
- Support zoom, pan, fit, and filtering.
- Source evidence appears in a side panel, not a hover-only tooltip.
- Provide a list/table alternative to the graph view.

### 6.6 Study Studio

- Separate generation controls from generated content.
- Show source scope and material type before generation.
- Quiz controls need selected, correct, incorrect, and unanswered states.
- Do not reveal correct answers before submission unless practice mode explicitly allows it.

### 6.7 Research Intelligence

- Structured comparison tables with clear document headers.
- Missing information reads “Not stated in selected source(s).”
- Citation controls are available in evidence-bearing cells.
- NLI flags are described as model signals, not final verdicts.

### 6.8 Learning Analytics

- Avoid gamification overload.
- Show attempt count, trend, and recommendation reason.
- Label BKT values as estimated mastery and show when data is insufficient.
- Use plain-language explanations and accessible chart alternatives.

---

## 7. Dark/light mode rules

- Dark mode is the default first-run theme.
- User can choose System, Dark, or Light in Settings.
- Persist preference per user after authentication; before login, use browser preference only if needed.
- Avoid hardcoded dark-only chart colours.
- Dialogs, graph labels, code blocks, and source panels work in both themes.
- Respect `prefers-reduced-motion` and high-contrast preferences where supported.

---

## 8. Motion and feedback

- Short transitions for hover, focus, selected states, and panel opening.
- Most micro-interactions around 120–200 ms.
- No animation that delays access to content.
- Skeletons for expected page structure; progress indicators for background jobs.
- Toasts for concise confirmations; persistent errors stay inline.
- Disable duplicate submissions while processing.
- Respect reduced-motion settings.

---

## 9. Accessibility requirements

Target WCAG 2.2 AA where feasible:

- Keyboard-operable navigation, forms, dialogs, menus, and graph alternatives.
- Visible focus ring with sufficient contrast.
- Semantic headings and landmarks.
- Labels/instructions programmatically associated with controls.
- Error messages announced and associated with inputs.
- No colour-only status or chart encoding.
- Sufficient contrast for text and controls.
- Practical touch target around 44 × 44 CSS px where layout allows.
- Tables have proper header associations.
- Graph data has a list/table alternative.

---

## 10. Responsive behaviour

- **Desktop:** persistent/collapsible sidebar and multi-panel workspace layout.
- **Tablet:** compact sidebar/drawer; source panels may overlay or stack.
- **Mobile browser:** single column, full-width dialogs, horizontal table scrolling, usable chat composer above virtual keyboard.
- No essential action requires hover.
- Avoid fixed widths that cause filenames, citations, or controls to overflow.

---

## 11. Content and microcopy principles

- Use direct, descriptive language.
- Say “No supporting evidence found in the selected documents” rather than “AI failed.”
- Say “Estimated concept mastery” rather than “Your intelligence score.”
- Say “Coverage gap in this workspace” rather than “Research gap discovered.”
- Say “Not stated in selected sources” instead of guessing missing comparison cells.
- Explain what an action will do, especially destructive actions.
- Avoid fake progress percentages and inflated AI claims.

---

## 12. Design acceptance checklist

- [ ] Dark and light semantic tokens implemented.
- [ ] Typography scale and spacing consistent.
- [ ] Primary/secondary/destructive actions visually distinct.
- [ ] Loading, empty, success, and error states designed.
- [ ] Citation/source interaction clear and keyboard accessible.
- [ ] Graph view has a non-graph alternative.
- [ ] Tables remain usable on mobile.
- [ ] Reduced motion and focus states supported.
- [ ] Text/control contrast checked.
- [ ] No decorative data presented as real product activity.
