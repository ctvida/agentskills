---
name: uxpsych-design
description: Apply conversion psychology to UI/UX work — trust, friction, motivation, and layout rules grounded in cognitive science. Use this skill whenever building or reviewing any user-facing screen, landing page, onboarding flow, pricing page, paywall, checkout, form, empty state, or upgrade prompt — even if the user only asks for "a page" or "a form" and never mentions psychology or conversion. Complements aesthetic skills (frontend-design): that one decides how it looks; this one decides what converts.
---

# UX Psychology Design

Aesthetic skills make an interface memorable; this skill makes it convert. The rules below translate cognitive science into checkable implementation rules. Apply every rule that touches the surface you're building. Full psychological rationale and before/after examples for each rule: `references/playbook.md` — read the relevant section when a rule needs justification or the user pushes back.

## When building, enforce these rules

### First impressions & copy
1. **One CTA above the fold.** Top ~500px of a landing/home page: one primary CTA, one bold headline, one high-quality contextual visual. No competing messages. Badge premium items ("Bestseller", "Top Rated") directly above the title.
2. **Sensory, contextual copy.** Show products in use, not isolated on flat backgrounds. Headlines evoke spatial/physical experience ("beachside escape steps from the sand"), never clinical descriptors.
3. **Specific numbers beat round ones.** "4.9 stars, 221 reviews" not "5 stars, 200+ reviews". "Start in 2 taps" not "quick setup". Ban the words fast/quick/easy in favor of exact metrics.

### Friction reduction
4. **No dropdowns for ≤5 options.** Render inline selectable cards/swatches instead. Expose core content directly — no "Discover more" banners hiding the actual list.
5. **Standard placement for critical chrome.** Nav, logo, search, cart go where every other site puts them. Creativity lives in content blocks and micro-interactions (`transform: scale(1.03)` bounds), never in relocating navigation.
6. **Chunk to 3–4 items.** Lists longer than 4 get thematic subheadings. Pricing tiers show deltas ("Everything in Basic, plus…" + 3–4 items), never repeated checkmark matrices.
7. **Never render an empty form.** Pre-fill with high-probability defaults (current date, nearest location, 1 traveler). 70–90% of users keep defaults — they're a recommendation engine.

### Trust & de-risking
8. **Trial transparency timeline.** Paywalls show Day 0 / reminder day / charge day as a visual timeline, including "we'll remind you before charging". Put guarantee micro-badges under primary buttons.
9. **Single exact price, never a range.** Ranges make brains anchor to the worst case. Put the total in the button: "Reserve • $445 total (no hidden fees)".

### Motivation & retention
10. **Never start progress at 0%.** Credit signup/verification so onboarding opens at 15–20% complete.
11. **Value before signup.** Deliver a readable partial result first; auth is a "save/export" step, not a gate. (Reciprocity.)
12. **Build before register.** Let users customize/configure first; the final button says "Continue" or "Save Progress", not "Sign Up". Hold choices in session state, commit on auth. (IKEA/endowment.)
13. **Loss-framed upgrades.** Upgrade prompts name the user's actual at-risk assets ("Keep My Files Safe" / "I'll risk losing them"), not generic feature gains.
14. **Anchor add-ons to the big number.** Show warranties/add-ons inline with the high-ticket item as a computed percentage ("Just 2.6%"), never on an isolated screen. Cross out original prices next to discounts.

### Layout mechanics
15. **Engineer the peak and the end.** `transition: all 0.2s ease-in-out` on interactive hovers; animated checkmark/morphing button on successful submit; humanized post-purchase tracking (timeline, courier photo) instead of text grids.
16. **Match input widget to frequency × precision.** Frequent or precise entry → numeric text field / steppers. One-time low-precision onboarding → sliders/wheels. Never the reverse.
17. **Tier the UI by engagement.** Branch on user tier (new / repeat / super): simplified onboarding views → routine quick-actions → dense dashboards.
18. **Thumb zone.** Mobile primary CTAs live in a sticky bottom-anchored container, lower third of the viewport.
19. **Empty states are onboarding.** `items.length === 0` renders headline + illustration + 1–2 tips + creation CTA. Never bare "No projects found".
20. **Value-first metric hierarchy; tinted shadows.** Numbers larger/bolder than their labels. Shadows on colored backgrounds take the background hue (e.g. `rgba(138,43,226,0.15)`), never `#000`. Product landing pages show real interior screenshots, not flat covers.

## When reviewing existing UI

Walk the rules above as a checklist against the screen. Report violations as `rule # — element — fix`, ordered by conversion impact (trust and friction issues first, polish last).

## Guardrails

These are persuasion techniques — use them honestly. Loss framing names *real* at-risk assets, transparency timelines state *actual* billing dates, specific numbers are *true* numbers. Never fabricate reviews, counts, urgency, or losses; dark patterns destroy the trust every rule here depends on.
