---
name: CloudTier Imaging Archive
description: Approved light archive workspace with teal actions, navy navigation and a dark MRI canvas.
colors:
  teal: "#14776d"
  teal-hover: "#115e57"
  navy: "#173a40"
  nav-hover: "#244b50"
  nav-active: "#dcefe6"
  nav-active-ink: "#1b514c"
  review-mint: "#eaf4ee"
  review-line: "#d5e8dc"
  success-bg: "#e7f4ec"
  success-ink: "#3b7158"
  attention-bg: "#fff3dc"
  attention-ink: "#8b621e"
  status-bg: "#edf1f5"
  status-ink: "#536876"
  tier-standard: "#16877c"
  tier-standard-ia: "#5889c7"
  tier-glacier: "#c49037"
  tier-deep-archive: "#8b80b5"
  workspace-bg: "#f5f7f8"
  surface: "#fff"
  ink: "#20343f"
  muted: "#586b77"
  line: "#e0e7ea"
  field-line: "#cfdce0"
  secondary-ink: "#3e5c65"
  secondary-line: "#d0dcde"
  secondary-hover: "#ecf4f1"
  table-head: "#f9fbfc"
  table-hover: "#f4f9f7"
  viewer-panel: "#12252e"
  viewer-canvas: "#0c1b23"
  viewer-control: "#233c46"
  viewer-line: "#476370"
  viewer-label: "#b4cbd2"
  nav-label: "#c2d4d3"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "clamp(34px, 4vw, 61px)"
    fontWeight: 550
    lineHeight: 1.12
    letterSpacing: "-.035em"
  headline:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "29px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.035em"
  title:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "16px"
    fontWeight: 600
    letterSpacing: "-.02em"
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "14px"
  body-detail:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "12px"
    lineHeight: 1.8
  label:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "11px"
    fontWeight: 500
  navigation:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "14px"
    fontWeight: 500
  button:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "12px"
    fontWeight: 550
  metric:
    fontFamily: "ui-sans-serif, system-ui, sans-serif, \"Apple Color Emoji\", \"Segoe UI Emoji\", \"Segoe UI Symbol\", \"Noto Color Emoji\""
    fontSize: "34px"
    fontWeight: 600
    letterSpacing: "-.035em"
rounded:
  sequence: "4px"
  chip: "5px"
  field: "6px"
  control: "7px"
  navigation: "8px"
  notice: "9px"
  panel: "12px"
spacing:
  compact: "8px"
  control: "10px"
  small: "12px"
  medium: "16px"
  row: "20px"
  column: "22px"
  panel: "23px"
  section: "24px"
  workspace: "36px"
components:
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.teal-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary-ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  nav-item:
    textColor: "{colors.nav-label}"
    typography: "{typography.navigation}"
    rounded: "{rounded.navigation}"
    padding: "12px 13px"
  nav-item-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.nav-active-ink}"
  status-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.chip}"
    padding: "4px 7px"
  status-attention:
    backgroundColor: "{colors.attention-bg}"
    textColor: "{colors.attention-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.chip}"
    padding: "4px 7px"
  status-neutral:
    backgroundColor: "{colors.status-bg}"
    textColor: "{colors.status-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.chip}"
    padding: "4px 7px"
  panel-body:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "23px"
  review-panel:
    backgroundColor: "{colors.review-mint}"
    rounded: "{rounded.panel}"
  viewer-panel:
    backgroundColor: "{colors.viewer-panel}"
    textColor: "{colors.surface}"
    rounded: "{rounded.panel}"
---

# Design System: CloudTier Imaging Archive

## Overview

**Creative North Star: "The Imaging Archive"**

The Imaging Archive is a calm operational workspace: pale working surfaces, teal actions, a fixed navy navigation rail, and a dark canvas reserved for inspecting MRI volumes. Border-defined panels and compact type let study identity, source context and storage state lead.

This records the approved v2 archive and login implementation, extracted from `src/frontend/src/archive/archive.css`, the archive React components, `pages/Login.jsx`, and the effective Tailwind body font. The earlier X-ray routes retain their existing system. Local prototype, synthetic sample and simulation labels are part of the visible interface; this design record makes no model-accuracy or cloud-validation claim.

**Key Characteristics:**

- Quiet light workspace with teal actions and navy navigation.
- Mint review surfaces; amber attention states; stable, labeled tier hues.
- Compact system typography, tabular figures and inspectable evidence.
- Small state-based motion; authored animations and transitions disabled for reduced motion.

## Colors

A cool paper-and-ink foundation carries restrained teal, mint and amber. The frontmatter values are normative. Sidecar tonal strips are synthesized previews, not additional shipped colors.

- **Primary:** `teal` identifies actions, links and focus; `teal-hover` darkens primary controls on hover.
- **Secondary:** `navy` anchors the rail and login story. `nav-label` is subdued navigation text; `nav-hover`, `nav-active` and `nav-active-ink` distinguish hover and the selected destination. `review-mint` and `review-line` group review work.
- **Tertiary:** paired `success-*`, `attention-*` and `status-*` tokens encode labeled state. Standard is green-teal, Standard-IA blue, Glacier amber and Deep Archive lavender; these four `tier-*` hues stay consistent across labels, legends and placement bars.
- **Neutral:** `workspace-bg`, `surface`, `ink`, `muted` and `line` establish readable layers. Field and secondary-control border tokens keep inputs identifiable; `table-head` and `table-hover` assist row scanning.
- **MRI:** `viewer-panel` encloses inspection; `viewer-canvas` sits behind actual slices. `viewer-control`, `viewer-line` and `viewer-label` support controls within that dark surface.

**The Meaning Rule.** Keep actions, clinical states and storage tiers visually distinct. Pair each state or tier color with a readable label; the teal action color is not a clinical verdict.

## Typography

Use the effective system sans stack in the frontmatter. The body has Tailwind's `font-sans` class; it wins over the archive stylesheet's declared Segoe UI fallback. No custom font asset is required.

The scale follows the operational hierarchy rather than a fixed ratio: the login display is the only large expressive text; archive headings, section titles, row details and status labels remain compact. The display becomes (32px) on phones, the archive headline (27px), and inventory metrics shift from (34px) to (29px) at the medium desktop breakpoint and (31px) on phones. Cost metrics use (25px), then (22px) on phones. Numeric inventory and money values use tabular figures. Supporting prose usually uses the `body-detail` role; page descriptions use (13px) and (1.6) line height.

**The Evidence Rule.** Use compact labels and tabular figures to support study inspection. Preserve source, sample and simulation wording next to the values it qualifies.

## Layout

The desktop shell uses a fixed rail (232px), a matching workspace offset, a top bar (72px minimum height), and a main container (1680px maximum width). Main padding is (29px 36px 36px); recurring panel interiors use the `panel` spacing token. Overview review and placement use a (1.13fr / 1fr) split with a (20px) gap; study inspection uses (1.65fr / 1fr) with a (22px) gap.

At (1600px) and above, horizontal workspace padding becomes (55px). At (1200px) and below, the rail narrows to (205px), workspace gutters become (25px), and global search leaves the top bar. At (1023px) and below, paired overview, detail and import regions stack; inventory and cost summaries retain two columns.

At (767px) and below, the rail becomes an off-canvas menu, the workspace fills the width, the top bar is (62px minimum height), and main gutters are (20px). Forms stack. The MRI workbench shows one selected sequence viewport with a sequence selector; plane, relative slice and prediction-overlay controls remain beside the inspection flow. Login changes from two columns to one with a shorter story.

Study tables keep their fields in a horizontal scroller (660px minimum table width on phones); manifests and cost-component tables use (600px). Long manifest identifiers wrap. The scroll region has a name and keyboard focus, and a visible phone hint explains the horizontal interaction. Candidate placement comparisons retain their compact three-column table.

**The Local Scroll Rule.** Wide study and object tables scroll inside their own focusable, named regions. Keep the phone scroll hint visible and the surrounding workspace within the viewport.

## Elevation & Depth

The archive defines no box-shadow vocabulary. White panels on a pale workspace, a mint review region, fine dividing strokes and the navy rail provide depth. The phone menu uses a translucent navy backdrop and separate stacking layers: backdrop (25), rail (30), skip link (100).

**The Border Rule.** Use fine borders and surface tone to group archive content. Do not add card shadows to this flat system.

## Shapes

Use softly squared forms: compact sequence markers, chips, fields, buttons and navigation progress through the frontmatter radius scale; panels and the MRI workbench share the largest radius. Borders are ordinarily (1px) solid. Missing sequence markers and unselected file upload areas use dashed borders. Small circular avatars and dots are semantic details, not a replacement card shape.

## Components

- **Buttons:** primary teal and white secondary variants share compact label type, an icon/text gap (8px), and minimum height (44px). Hover changes color; an enabled press shifts down (1px). Disabled buttons reduce opacity to (.48). The shared focus outline is (3px) with (4px) offset.
- **Fields and upload areas:** white, bordered controls use minimum height (42px) and the field radius; filters use (40px). File areas expose sequence role and selection text, switch from dashed to solid after selection, and use a (3px) focus-within outline with (3px) offset.
- **Chips and sequences:** success, attention and neutral badges combine text and background. Sequence markers state T1, T1ce, T2 and FLAIR explicitly; missing markers use a dashed outline and a companion missing-sequence description.
- **Panels and tables:** generic panels have a border and clipped rounded corners; padded bodies use the `panel` spacing token. Tables use tinted headers, row dividers, hover feedback and textual study links. Keep table captions or region names and phone scroll hints.
- **Navigation:** the active destination is a mint filled row on navy. On phones, opening the menu makes workspace content inert and confines keyboard focus to the menu; Escape, close and backdrop actions close it and restore focus to the trigger. Closed mobile navigation is inert.
- **MRI workbench:** show uploaded preview slices only when available. Missing, DICOM-only and failed-preview states stay explicit. Desktop shows four sequence previews; phones select one. The canvas labels the sequence, plane and relative slice; overlay controls require an available analysis result.
- **Placement review:** the review trigger exposes its expanded state. Opening the section focuses its heading and scrolls it into view immediately, with heading scroll margin (24px). Cancel closes it and returns focus to the trigger. Candidate eligibility, modeled cost and reason remain visible before the local simulation action.
- **Motion:** page arrival moves up from (7px) over (.38s); placement bars scale from (.94) to (1) over (.8s), and cost bars over (.75s), using `cubic-bezier(.16,1,.3,1)`. Buttons and rows use (.18s) color/press feedback; navigation uses (.2s); the mobile rail uses (.25s). Loading rotation uses (1.3s) linear repetition. Reduced motion disables all authored animations and transitions, and sets scrolling to auto.

**The Visible Motion Rule.** Content remains visible throughout navigation and placement reveals. Use the existing small transforms, and disable authored animation and transition when reduced motion is requested.

## Do's and Don'ts

### Do:

- **Do** keep the archive light, actions teal, navigation navy and MRI inspection dark.
- **Do** repeat textual state and tier labels beside their colors.
- **Do** keep phone MRI inspection to one selected sequence viewport with plane, slice and overlay controls nearby.
- **Do** preserve table scroll hints, focusable scroll regions and focused placement review.
- **Do** retain synthetic sample, local workspace and simulation labels beside their evidence.

### Don't:

- **Don't** use synthetic metadata as MRI imagery or analysis output.
- **Don't** present modeled cost, local placement or restore simulations as verified cloud operations.
- **Don't** replace compact operational headings with oversized marketing typography inside the archive.
- **Don't** add decorative card shadows or animate layout dimensions.
- **Don't** hide content during arrival motion or bypass reduced-motion preferences.
