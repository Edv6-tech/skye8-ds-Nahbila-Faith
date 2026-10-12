---
name: tour-card-builder
description: Comprehensive UX research-backed standards and design patterns for building modern, high-converting interactive product tour cards in web applications.
---

# UX Research & Design Standards for Product Tour Cards

Based on UX research (Nielsen Norman Group, Appcues, Driver.js, Intercom, ProductLed), effective product tour cards must adhere to 5 core pillars.

---

## 1. Perfect Visual Anatomy

A world-class tour card requires 5 distinct visual layers:
1. **Linear Progress Bar**: Top 4px progress indicator (`0%` to `100%`) showing exact completion status.
2. **Category & Step Badge**: High-contrast pill badge (`STEP 3 OF 24 · BORROWER WORKSPACE`).
3. **Concise Title & Emoji**: Clear 16–18px bold title with thematic icon.
4. **Scannable Micro-Copy**: Max 2–3 short sentences (<40 words) using plain language with key metrics styled as vibrant inline pill tags (`<span class="tour-highlight">`).
5. **Interactive Controls Row**: Primary CTA ("Next →"), Secondary CTA ("← Back"), Jump-to-Step Dropdown, and Close button (`✕`).

---

## 2. Dynamic Target Positioning & Spotlight Masking

1. **Target Attachment (Popover Anchor)**:
   - Tooltip positions dynamically (Top, Bottom, Left, Right) relative to target element with 12px offset.
   - Includes a visual pointer arrow pointing directly at the highlighted element.
2. **Spotlight Mask Cutout**:
   - Dims surrounding UI with translucent backdrop (`rgba(5, 10, 22, 0.4)`).
   - Highlights targeted element with animated glowing outline (`outline: 3px solid #c8f060; box-shadow: 0 0 30px rgba(200,240,96,0.6)`).
3. **Zero Overlay Conflicts**:
   - Auto-hides fixed utility widgets (like floating AI chat buttons) during active tour turns.

---

## 3. Cognitive Load & Micro-Copy Rules

1. **Rule of One Idea**: Each step highlights exactly ONE element or action.
2. **Plain Language ("7-Year-Old Test")**: Avoid technical jargon (e.g. replace "heuristic ML uplift" with "smart AI guess that finds ready buyers").
3. **Bold Metric Highlights**: Emphasize key numbers and results so users can scan in <3 seconds.

---

## 4. User Control & Friction Reduction

1. **Keyboard Accessibility**: `Right Arrow` (Next), `Left Arrow` (Back), `Esc` (Close).
2. **Non-Linear Jump Selector**: Dropdown to let users skip directly to any step.
3. **Session Persistence**: Saves completion state in `localStorage` so users aren't re-prompted against their choice.
