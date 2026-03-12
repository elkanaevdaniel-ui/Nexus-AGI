# AI SDR OS — UX/UI Design

## Design System

### Style: Clean & Minimal (Linear-inspired)

- **Background**: White (#FFFFFF) / Light gray (#F9FAFB)
- **Surface**: White cards with subtle border (#E5E7EB)
- **Text**: Dark gray (#111827) / Medium gray (#6B7280)
- **Primary accent**: Blue (#3B82F6)
- **Success**: Green (#10B981)
- **Warning**: Amber (#F59E0B)
- **Error**: Red (#EF4444)
- **Font**: Inter (system font stack)
- **Border radius**: 8px (cards), 6px (buttons/inputs)
- **Shadows**: Subtle, only on hover (0 1px 3px rgba(0,0,0,0.1))

### No Animations
Only basic CSS transitions: hover states, focus rings. No framer-motion, no glow effects.

---

## Layout

```
┌─────────┬──────────────────────────────────────┐
│         │  Breadcrumb / Page Title              │
│  Side   │──────────────────────────────────────│
│  bar    │                                      │
│         │  Page Content                        │
│  Logo   │                                      │
│  ────── │                                      │
│  Home   │                                      │
│  ────── │                                      │
│  Camps  │                                      │
│         │                                      │
│         │                                      │
│         │                                      │
└─────────┴──────────────────────────────────────┘
```

- **Sidebar**: Fixed left, 240px wide, white bg, bottom-aligned settings link
- **Content area**: Max-width 1200px, centered, 32px padding

---

## Pages

### 1. Campaign Dashboard (`/`)

```
┌──────────────────────────────────────────────┐
│  Campaigns                    [+ New Campaign] │
│                                                │
│  ┌────────────────────┐ ┌────────────────────┐ │
│  │ Cyber MSSPs Israel │ │ SaaS CTOs US West  │ │
│  │ 142 leads          │ │ 89 leads           │ │
│  │ ●●●●○ Scoring      │ │ ●●●●● Complete     │ │
│  │ Active              │ │ Completed           │ │
│  └────────────────────┘ └────────────────────┘ │
│                                                │
│  ┌────────────────────┐                        │
│  │ DevOps VPs EMEA    │                        │
│  │ 0 leads            │                        │
│  │ ○○○○○ Idle         │                        │
│  │ Active              │                        │
│  └────────────────────┘                        │
└────────────────────────────────────────────────┘
```

**Components:**
- `CampaignCard`: Name, lead count, pipeline progress dots, status badge
- Grid layout: 2 columns on desktop, 1 on mobile
- Empty state: "No campaigns yet. Create your first one."

### 2. New Campaign (`/campaigns/new`)

```
┌──────────────────────────────────────────────┐
│  Create Campaign                              │
│                                                │
│  Campaign Name                                 │
│  ┌────────────────────────────────────────┐    │
│  │ Cybersecurity MSSPs Israel            │    │
│  └────────────────────────────────────────┘    │
│                                                │
│  Describe your ideal customer:                 │
│  ┌────────────────────────────────────────┐    │
│  │ Find cybersecurity MSSPs and resellers│    │
│  │ in Israel with 10-200 employees.      │    │
│  │ Prefer founders, CEOs, channel        │    │
│  │ managers, and sales directors.        │    │
│  └────────────────────────────────────────┘    │
│                                 [Parse ICP →]  │
│                                                │
│  ── Parsed Filters (editable) ──────────────  │
│  Titles: [CEO] [CTO] [Founder] [+ Add]       │
│  Seniority: [c_suite] [founder] [+ Add]      │
│  Locations: [Israel] [+ Add]                  │
│  Employees: [10] - [200]                      │
│  Industries: [cybersecurity] [+ Add]          │
│  Keywords: [MSSP] [reseller] [+ Add]          │
│                                                │
│              [Create & Run Pipeline]           │
└────────────────────────────────────────────────┘
```

**Flow:**
1. User types campaign name + ICP text
2. Clicks "Parse ICP" → calls backend → shows structured filters
3. User can edit filters (add/remove tags, change ranges)
4. Clicks "Create & Run Pipeline" → creates campaign + starts pipeline

### 3. Campaign Detail (`/campaigns/[id]`)

```
┌──────────────────────────────────────────────┐
│  ← Campaigns   Cyber MSSPs Israel    [Active]│
│                                                │
│  Pipeline Progress                             │
│  [Search ✓] → [Score ✓] → [Enrich ●] → [Draft] → [Review] │
│                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │   142    │ │   78.5   │ │    20    │ │    15    │ │
│  │  Leads   │ │ Avg Score│ │ Enriched │ │  Drafts  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                │
│  ICP: "Find cybersecurity MSSPs..."           │
│                                                │
│  [View Prospects]  [View Drafts]  [Export CSV] │
└────────────────────────────────────────────────┘
```

### 4. Prospect Table (`/campaigns/[id]/prospects`)

```
┌──────────────────────────────────────────────────────────┐
│  ← Campaign   Prospects (142)     [Bulk Actions ▾]      │
│                                                          │
│  Filters: [All Status ▾] [Min Score: 60] [Search...]    │
│                                                          │
│  ┌──┬───────────┬────────────┬──────────┬───┬──────┬───┐│
│  │☐ │ Name      │ Company    │ Title    │Sc │Email │St ││
│  ├──┼───────────┼────────────┼──────────┼───┼──────┼───┤│
│  │☐ │ John Doe  │ CyberCo   │ CEO      │95 │  ✓   │ E ││
│  │☐ │ Jane Roe  │ SecureNet  │ Founder  │88 │  ✓   │ S ││
│  │☐ │ Bob Smith │ ShieldTech │ VP Sales │72 │  ~   │ N ││
│  └──┴───────────┴────────────┴──────────┴───┴──────┴───┘│
│                                                          │
│  ← 1 2 3 ... 6 →                                       │
└──────────────────────────────────────────────────────────┘
```

**Features:**
- Sortable columns (click header)
- Status badges: N=new, E=enriched, S=scored, C=contacted
- Email icons: ✓=verified, ~=guessed, ✕=none
- Checkbox for bulk actions (enrich, score, generate drafts)
- Click row → side panel with full detail

### 5. Prospect Detail (Side Panel)

```
┌──────────────────────────────────┐
│  John Doe                    [×] │
│  CEO at CyberCo                  │
│  📍 Tel Aviv, Israel             │
│  ✉ john@cyberco.com (verified)  │
│  📱 +972-50-xxx-xxxx            │
│                                  │
│  Score: 95/100                   │
│  ├── Title & Seniority: 28/30   │
│  ├── Company Fit: 27/30         │
│  ├── Contact Quality: 20/20     │
│  └── Engagement: 20/20          │
│                                  │
│  "Strong C-suite match with      │
│   verified contact in target     │
│   cybersecurity industry."       │
│                                  │
│  ── Outreach Drafts ──          │
│  Email: [View/Edit]              │
│  LinkedIn: [View/Edit]           │
│                                  │
│  [Approve] [Suppress Lead]       │
└──────────────────────────────────┘
```

### 6. Draft Review (`/campaigns/[id]/drafts`)

```
┌──────────────────────────────────────────────┐
│  ← Campaign   Drafts (15)   [Bulk Approve]   │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ To: John Doe (CEO, CyberCo)             │ │
│  │ Channel: Email                Score: 95  │ │
│  │                                          │ │
│  │ Subject:                                 │ │
│  │ ┌──────────────────────────────────────┐ │ │
│  │ │ Partnership opportunity for CyberCo │ │ │
│  │ └──────────────────────────────────────┘ │ │
│  │                                          │ │
│  │ Body:                                    │ │
│  │ ┌──────────────────────────────────────┐ │ │
│  │ │ Hi John,                            │ │ │
│  │ │                                      │ │ │
│  │ │ I noticed CyberCo is expanding...  │ │ │
│  │ └──────────────────────────────────────┘ │ │
│  │                                          │ │
│  │           [Approve ✓]  [Reject ✕]       │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ To: Jane Roe (Founder, SecureNet)       │ │
│  │ ...                                      │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

### 7. Export (`/campaigns/[id]/export`)

```
┌──────────────────────────────────────────────┐
│  ← Campaign   Export                          │
│                                                │
│  Export 142 leads from "Cyber MSSPs Israel"   │
│                                                │
│  Filters:                                      │
│  Min Score: [60]                               │
│  Status: [All ▾]                               │
│                                                │
│  Columns:  ☑ Name  ☑ Email  ☑ Phone           │
│            ☑ Title  ☑ Company  ☑ Score         │
│            ☑ Industry  ☐ Raw Data              │
│                                                │
│  Preview (first 5 rows):                       │
│  ┌──────────────────────────────────────────┐ │
│  │ John Doe, john@cyberco.com, CEO, 95     │ │
│  │ Jane Roe, jane@securenet.com, Founder...│ │
│  └──────────────────────────────────────────┘ │
│                                                │
│                          [Download CSV]        │
└────────────────────────────────────────────────┘
```

---

## Components

| Component | Props | Purpose |
|-----------|-------|---------|
| `Sidebar` | activePath | Fixed left navigation |
| `CampaignCard` | campaign | Dashboard card with progress |
| `PipelineProgress` | stage, stages[] | Step indicator (dots/checkmarks) |
| `ProspectTable` | leads, onSort, onFilter | Sortable data table |
| `ProspectDetail` | lead, messages | Side panel detail view |
| `DraftEditor` | message, onSave | Editable subject + body |
| `ICPInput` | value, onChange | Textarea for ICP description |
| `FilterPreview` | filters, onEdit | Tag-based filter editor |
| `ScoreBreakdown` | score, reason | Visual score bar |
| `StatusBadge` | status | Colored status indicator |
| `EmptyState` | title, action | "No data" placeholder |

---

## User Flows

### Create Campaign Flow
1. Dashboard → Click "+ New Campaign"
2. Enter name + ICP text
3. Click "Parse ICP" → see parsed filters
4. Optionally edit filters
5. Click "Create & Run Pipeline"
6. Redirected to Campaign Detail → see pipeline progress
7. Poll for updates until complete

### Review Flow
1. Campaign Detail → Click "View Prospects"
2. Sort by score descending
3. Click lead → see detail panel
4. Review score breakdown + AI explanation
5. Click "View Drafts" on lead
6. Edit subject/body if needed
7. Approve or reject

### Export Flow
1. Campaign Detail → Click "Export CSV"
2. Set min score filter
3. Select columns
4. Click "Download CSV"
