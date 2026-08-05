---
name: uxpsych-design
description: Apply conversion psychology to UI/UX work — trust, friction, motivation, and layout rules grounded in cognitive science. Use this skill whenever building or reviewing any user-facing screen, landing page, onboarding flow, pricing page, paywall, checkout, form, empty state, or upgrade prompt — even if the user only asks for "a page" or "a form" and never mentions psychology or conversion. Complements aesthetic skills (frontend-design): that one decides how it looks; this one decides what converts.
---

# UX Psychology Design

Aesthetic skills make an interface memorable; this skill makes it convert. The rules below translate cognitive science into checkable implementation rules. Apply every rule that touches the surface you're building. Full psychological rationale and before/after examples for each rule: `references/playbook.md` — read the relevant section when a rule needs justification or the user pushes back.

## When building, enforce these rules

### First impressions & copy
1. **The 4-element hero (mini-site rule).** Every hero renders exactly four things above the fold, no more: one `<h1>` headline stating what the product *is*; one jargon-free context line saying who it's for; one visible social-proof cluster (client logos or a rating badge); one context-rich primary button naming the next event ("Book a demo", never "Schedule a call" / "Get started" / "Learn more"). The hero must let a user decide without scrolling. Badge premium items ("Bestseller", "Top Rated") directly above the title; no un-badged raw product shots above the fold.
2. **Sensory, contextual copy.** Show products in use, not isolated on flat backgrounds. Headlines evoke spatial/physical experience ("beachside escape steps from the sand"), never clinical descriptors.
3. **Specific numbers beat round ones.** "4.9 stars, 221 reviews" not "5 stars, 200+ reviews". "Start in 2 taps" not "quick setup". Ban the words fast/quick/easy in favor of exact metrics.

### Friction reduction
4. **No dropdowns *or* stacked radios for ≤5 options.** Render side-by-side selection cards/swatches. The target option is pre-selected, carries a gently tinted background and a "Most Popular"/"Best Value" tag, and states its reassuring contract terms *inside the card* ("Save 15%", "Cancel anytime"). Selecting a lower tier progressively discloses bundles rather than pre-cluttering the screen. Expose core content directly — no "Discover more" banners hiding the actual list.
5. **Standard placement for critical chrome.** Nav, logo, search, cart go where every other site puts them. Creativity lives in content blocks and micro-interactions (`transform: scale(1.03)` bounds), never in relocating navigation.
6. **Chunk to 3–4 items.** Lists longer than 4 get thematic subheadings. Pricing tiers show deltas ("Everything in Basic, plus…" + 3–4 items), never repeated checkmark matrices.
7. **Never render an empty form.** Pre-fill with high-probability defaults (current date, nearest location, 1 traveler). 70–90% of users keep defaults — they're a recommendation engine.

### Trust & de-risking
8. **Trial transparency timeline.** Paywalls show Day 0 / reminder day / charge day as a visual timeline, including "we'll remind you before charging". Put guarantee micro-badges under primary buttons.
9. **Single exact price, never a range.** Ranges make brains anchor to the worst case. Put the total in the button: "Reserve • $445 total (no hidden fees)". Soften button copy — "Start my free trial", not "Subscribe".
10. **Proof sits at the point of doubt.** Every pricing tier, subscription selector, and checkout submit button carries a trust component within ~150px: a specific review, a rating, or an objection-busting illustrated badge ("60-Day Guarantee", "Third-Party Tested"), not a generic "Free Shipping" icon. Testimonials on a separate tab count as absent.

### Motivation & retention
11. **Never start progress at 0%.** Credit signup/verification so onboarding opens at 15–20% complete.
12. **Value before signup.** Deliver a readable partial result first; auth is a "save/export" step, not a gate. (Reciprocity.)
13. **Build before register.** Let users customize/configure first; the final button says "Continue" or "Save Progress", not "Sign Up". Hold choices in session state, commit on auth. (IKEA/endowment.)
14. **Loss-framed upgrades.** Upgrade prompts name the user's actual at-risk assets ("Keep My Files Safe" / "I'll risk losing them"), not generic feature gains.
15. **Anchor add-ons to the big number.** Show warranties/add-ons inline with the high-ticket item as a computed percentage ("Just 2.6%"), never on an isolated screen. Cross out original prices next to discounts.

### Layout mechanics
16. **Typography restraint.** Maximum 2 `font-family` declarations per surface — one is better. Decorative/high-personality faces are for large headlines only; body text is always the clean, readable face. Weight and size, not extra fonts, define the eye path.
17. **Value-first metric hierarchy.** Every metric renders its *number* at ≥1.5× the font-size and a heavier weight than its label ("591" big, "sales" small underneath) — never the inverse.
18. **Tinted shadows.** Any shadow over a non-white background takes that background's hue (`rgba(138,43,226,0.15)` on light purple), soft and diffuse. `#000`, `#888`, and `rgba(0,0,0,0.3)` shadows are banned on colored surfaces.
19. **Engineer the peak and the end.** `transition: all 0.2s ease-in-out` on interactive hovers; animated checkmark/morphing button on successful submit; humanized post-purchase tracking (timeline, courier photo) instead of text grids.
20. **Match input widget to frequency × precision.** Frequent or precise entry → numeric text field / steppers. One-time low-precision onboarding → sliders/wheels. Never the reverse.
21. **Tier the UI by engagement.** Branch on user tier (new / repeat / super): simplified onboarding views → routine quick-actions → dense dashboards.
22. **Thumb zone.** Under 768px, primary forms and action buttons render in a `position: sticky`/`fixed` bottom container, in the lower third of the viewport. Never relocate nav to satisfy this — rule 5 wins (the Gaming Bible bottom-menu failure).
23. **Empty states are onboarding.** `items.length === 0` renders headline + illustration + 1–2 tips + creation CTA. Never bare "No projects found". Same for a focused search bar: recent/popular/personalized suggestions, never a blank panel.
24. **Real screenshots.** Product landing pages show actual interior screens, not flat marketing covers.

## Before emitting any HTML/React/CSS, run both checks

- **Squint test (rules 1, 16, 17):** blur the layout mentally — does exactly one element still dominate? If it flattens into uniform gray, the hierarchy is broken; fix it before output, don't ship and explain.
- **One-hand mobile check (rule 22):** at <768px, is the primary CTA reachable by a thumb without a grip change, is everything readable without zoom, and does nothing overflow horizontally?

## When reviewing existing UI

Walk the rules above as a checklist against the screen. Report violations as `rule # — element — fix`, ordered by conversion impact (trust and friction issues first, polish last).

## Guardrails

These are persuasion techniques — use them honestly. Loss framing names *real* at-risk assets, transparency timelines state *actual* billing dates, specific numbers are *true* numbers. Never fabricate reviews, counts, urgency, or losses; dark patterns destroy the trust every rule here depends on.
