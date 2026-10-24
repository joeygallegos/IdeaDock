# LoopList Design Guide

This document describes the current visual language of LoopList as implemented in `templates/index.html`. Use it as the house style when extending the UI or prompting GPT to generate matching screens and components.

## Design Brief

LoopList should feel like a premium, light-mode productivity dashboard. The mood is airy, polished, and calm: editorial typography, soft glass surfaces, bright blue-violet accents, and subtle motion. It should never feel dark, corporate, heavy, or generic.

Short description for team/GPT:

> Build a light, polished checklist UI with glassy white panels, a pale sky/blue/violet atmosphere, bold serif headlines, clean sans body text, oversized rounded corners, subtle blur and shadow, and small purposeful motion. Keep it premium and calm, not playful or noisy.

## Core Principles

- Light-first UI. The background should stay bright and open, with color coming from soft gradients and tinted surfaces rather than dark fills.
- Soft-glass surfaces. Panels should feel translucent and layered, not flat.
- Strong shape language. Large radii are part of the identity; avoid square or barely rounded elements.
- Editorial contrast. Pair expressive serif headings with clean sans-serif UI text.
- Controlled accent color. The primary accent is blue-violet, supported by cyan and slate neutrals.
- Motion with restraint. A few subtle animations are good; constant busy motion is not.
- Utility with polish. This is still a checklist tool, so clarity and readability come first.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--bg-1` | `#f8fbff` | Main page background |
| `--bg-2` | `#eef4ff` | Lower page gradient |
| `--bg-3` | `#f5f1ff` | Secondary background tint |
| `--ink` | `#16203a` | Primary text |
| `--muted` | `#64748f` | Supporting text, labels |
| `--panel` | `rgba(255, 255, 255, 0.84)` | Card backgrounds |
| `--panel-border` | `rgba(99, 91, 255, 0.12)` | Card borders |
| `--accent` | `#635bff` | Primary brand/action color |
| `--accent-strong` | `#4f46e5` | Stronger accent state |
| `--accent-soft` | `rgba(99, 91, 255, 0.12)` | Soft accent fills/rings |
| `--accent-blue` | `#0ea5e9` | Cyan support color |
| `--shadow` | `0 24px 80px rgba(80, 102, 144, 0.16)` | Main shell shadow |

## Color Direction

- Base the page on layered white and pale blue, not flat gray.
- Use a blue-violet accent for primary actions and selected states.
- Use cyan as a supporting color inside gradients and highlights.
- Use slate neutrals for quiet states like muted text and skipped items.
- Borders should usually be tinted and subtle, not high-contrast.

The page background should use layered gradients:

- A cyan radial glow near the top left
- A violet radial glow near the top right
- A white-to-blue vertical wash across the page

## Typography

- Headings use `Fraunces`, weight `600` to `700`.
- Body/UI text uses `Manrope`, weight `400` to `800`.
- `h1` and `h2` use tighter tracking: `letter-spacing: -0.03em`.
- Micro-labels are uppercase, bold, and widely tracked.
- The hero heading should feel oversized and confident, not restrained.

Typography rules:

- Reserve the serif for major headings only.
- Keep body copy clean and readable.
- Use small uppercase labels for metadata like section labels and panel headings.
- Favor short, crisp product copy over long descriptions.

## Layout System

- The app is centered in a single main column with `max-w-5xl`.
- Everything sits inside one large `page-shell` with heavy rounding and blur.
- Decorative color orbs live behind the content to create atmosphere.
- Internal content is divided into stacked `panel-card` sections.
- On mobile, content stacks naturally. On desktop, top-level rows split horizontally when useful.

Primary shape sizes:

- Main shell radius: about `2rem`
- Standard panel radius: about `1.75rem`
- Checklist row radius: about `1.35rem`
- Inputs and buttons: `rounded-2xl` or fully pill-shaped where appropriate

## Surface Style

The visual stack depends on three recurring surface types:

### 1. Page Shell

- Translucent white gradient background
- 1px light border
- Strong blur (`backdrop-filter: blur(20px)`)
- Deep, soft shadow
- Relative positioning so floating background orbs can sit underneath content

### 2. Panel Cards

- Semi-opaque white background
- Accent-tinted border
- Medium soft shadow
- Short rise-in animation on render

### 3. Field Shells

- Nearly solid white
- Thin violet-tinted border
- Inset top highlight
- Soft violet focus ring, not default browser blue

## Components

### Header

- Small pill badge above the title
- Large serif headline
- Short muted supporting sentence
- Compact progress stat card aligned beside it on larger screens

### Buttons

- Primary buttons use solid accent fill, white text, and a visible colored shadow
- Secondary buttons use near-white fill, dark text, and a faint accent ring
- Hover effect is a tiny upward lift, not a big scale or bounce

### Progress Bar

- Rounded full-width track with inset depth
- Animated multi-stop gradient fill
- Gradient should move slowly from left to right
- It can include a soft glow tied to current completion

### Panels and Lists

- Each section lives in its own panel card
- Section title is prominent but smaller than the hero
- Controls stay simple and aligned: one primary add action, one secondary action where needed

### Modals

- Full-screen darkened overlay with blur
- Centered white glass card
- Same border, radius, and shadow language as the main panels

## Motion

Keep motion soft, slow, and intentional.

Current motion language:

- `shine`: slow animated gradient sweep for the progress bar
- `float`: gentle vertical drift for decorative orbs
- `rise`: short entrance animation for cards
- Hover lift: about `translateY(-1px)` for buttons and interactive rows

Guidelines:

- Use easing, not sharp linear snaps, except for the progress-bar shine.
- Animation should support depth and polish, not call attention to itself.
- Avoid large transforms, elastic springs, or exaggerated parallax.

## Copy Tone

- Product copy should feel concise, confident, and a little elevated.
- Avoid enterprise jargon and avoid cutesy language.
- Use short labels and sharp one-line descriptions.

Good examples from the current app:

- `LoopList Control Panel`
- `Checklists that feel worth opening.`
- `Current Progress`
- `Add to this group`

## What To Avoid

- Dark-mode-first interpretations
- Flat white pages with no atmosphere
- Generic gray cards and default Tailwind styling with no customization
- Square corners or tiny radii
- Default system fonts in place of the serif/sans pairing
- Loud rainbow gradients or neon colors
- Oversized shadows that make panels feel muddy
- Busy animations on every element

## Prompt Starter For GPT

Use this when you want GPT to make new UI that matches LoopList:

> Match the existing LoopList aesthetic: bright light-mode dashboard, glassy white panels, soft blue and violet atmospheric gradients, Fraunces serif for major headings, Manrope for UI text, large rounded corners, tinted borders, subtle shadows, and restrained motion. Keep the interface premium, airy, and highly readable. Avoid dark themes, flat generic cards, default Tailwind-only styling, or overly playful visuals.
