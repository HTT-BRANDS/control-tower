# Brand Color Palette Analysis

**Date:** March 2, 2025  
**Purpose:** Extract complete color palettes for multi-tenant governance platform design system  
**Websites Analyzed:** 4 brands under HTT Brands portfolio

---

## Executive Summary

This research analyzes the color systems of four beauty franchise brands owned by HTT Brands: the parent company (HTT Brands), Frenchies Nails, Bishops Haircuts, and The Lash Lounge. Each brand has distinct visual identities while sharing a cohesive approach to premium beauty service positioning.

### Key Findings

| Brand | Primary Identity | Color Strategy |
|-------|------------------|----------------|
| HTT Brands | Corporate/Multi-brand | Deep burgundy + gold luxury |
| Frenchies | Clean/Natural/Health-focused | Navy + soft pink serenity |
| Bishops | Bold/Creative/Accessible | Vibrant orange + neutral contrast |
| Lash Lounge | Luxury/Elegant/Premium | Deep purple + soft lavender |

---

## HTT Brands (Head To Toe Brands)
**URL:** https://httbrands.com

**Primary:** #500711 (Deep Burgundy/Maroon)  
**Secondary:** #d1bdbf (Soft Pink/Mauve)  
**Accent:** #ffc957 (Golden Yellow), #b0031a (Red accent)  
**Background:** #ffffff (White), #fafae1 (Cream)  
**Text:** #313131 (Dark Gray), #000000 (Black)  
**CTA Buttons:** #ed9bbd (Pink), gradients with pink tones

**Notes:**
- Uses a sophisticated burgundy palette suggesting luxury and professionalism
- Golden yellow accents for highlights and awards badges
- Pink/mauve tones create warmth and approachability
- Clean white backgrounds with subtle cream accents
- Logo uses burgundy (#500711) with a stylized "HT" monogram
- Gradient buttons using pink tones for franchise CTAs

---

## Frenchies Nails
**URL:** https://frenchiesnails.com

**Primary:** #052b48 (Deep Navy Blue)  
**Secondary:** #004a59 (Teal/Navy variant)  
**Accent:** #faaca8 (Soft Peach Pink), #f78da7 (Rose Pink)  
**Background:** #ffffff (White), #ebf0f5 (Light Blue-Gray), #fafae1 (Warm Cream)  
**Text:** #052b48 (Navy - primary text), #313131 (Dark Gray)  
**Buttons:** #052b48 (Navy filled), #052b48 2px border outline

**Notes:**
- Deep navy (#052b48) creates trust and cleanliness - core brand values
- Soft peachy-pink accents (#faaca8) suggest warmth and femininity
- Light blue-gray backgrounds (#ebf0f5) evoke cleanliness and airiness
- Logo uses navy with clean sans-serif typography
- "Not just a nail salon, a revolution" - fresh, modern aesthetic
- Health-conscious positioning reflected in clean color choices

---

## Bishops Haircuts
**URL:** https://bishops.co

**Primary:** #EB631B (Vibrant Orange)  
**Secondary:** #CE9F7C (Tan/Beige)  
**Accent:** #eb631b (Orange - repeated), #32373c (Dark Gray)  
**Background:** #EBEBDF (Warm Beige/Cream), #ffffff (White)  
**Text:** #000000 (Black), #32373c (Charcoal)  
**Buttons:** #EB631B (Solid orange filled), white text

**Notes:**
- Bold, energetic orange (#EB631B) dominates the visual identity
- "You deserve a haircut this cool" - youthful, creative positioning
- Beige/cream backgrounds (#EBEBDF) provide neutral contrast
- "Cookie-cutter isn't your style" - celebrates individuality
- Strong visual hierarchy with orange CTAs and black text
- Logo features "BISHOPS" in bold orange with "CUTS / COLOR" subtitle
- Creative, artistic vibe with halftone image treatments

---

## The Lash Lounge
**URL:** https://thelashlounge.com

**Primary:** #513550 (Deep Purple/Mauve)  
**Secondary:** #D3BCC5 (Soft Lavender/Mauve), #EBE1E5 (Pale Pink-Lavender)  
**Accent:** #232323 (Near Black - used in CTAs), #FCFAFB (Off-White)  
**Background:** #ffffff (White), #FCFAFB (Warm White), #EBE1E5 (Pale Lavender)  
**Text:** #513550 (Purple - headers), #32373c (Dark Gray - body)  
**Buttons:** #232323 (Dark charcoal filled), #ffffff text

**Notes:**
- Deep purple (#513550) conveys luxury, exclusivity, and premium positioning
- Soft lavender tones (#D3BCC5, #EBE1E5) create elegant, feminine atmosphere
- Dark charcoal buttons (#232323) for strong CTAs
- "Choose Lashes, Invest in You" - self-care and luxury messaging
- Logo features stylized script "L" and serif typography in purple
- Light, airy backgrounds with subtle lavender tints
- Premium beauty positioning with sophisticated color palette

---

## Cross-Brand Analysis

### Shared Patterns
1. **All brands use:** White (#ffffff) as primary background
2. **All brands use:** Dark text (#000000, #313131, #32373c) for readability
3. **All brands:** Position as premium/luxury service providers
4. **All brands:** Use solid color CTAs (no gradients for primary actions)

### Brand Differentiation Strategy
| Element | HTT Brands | Frenchies | Bishops | Lash Lounge |
|---------|-----------|-----------|---------|-------------|
| **Mood** | Corporate/Luxury | Clean/Healthy | Bold/Creative | Elegant/Premium |
| **Primary** | Burgundy | Navy | Orange | Purple |
| **Secondary** | Pink/Mauve | Soft Pink | Beige | Lavender |
| **Energy** | Refined | Calm | High | Sophisticated |
| **Target** | Franchise Investors | Health-conscious | Creative/Youth | Luxury seekers |

### Design System Recommendations

For the multi-tenant governance platform:

1. **Use CSS Custom Properties** to allow per-brand theming:
   ```css
   --brand-primary: #500711; /* HTT example */
   --brand-secondary: #d1bdbf;
   --brand-accent: #ffc957;
   --brand-text: #313131;
   --brand-bg: #ffffff;
   ```

2. **Maintain Consistent Patterns:**
   - White/light backgrounds across all brands
   - Dark text for readability (WCAG AA compliance)
   - Solid color buttons for CTAs
   - Subtle accent colors for highlights

3. **Brand-Specific Applications:**
   - **HTT Brands:** Use burgundy for headers, gold for awards/success states
   - **Frenchies:** Navy navigation, soft pink for highlights/health indicators
   - **Bishops:** Orange for primary actions, beige for secondary areas
   - **Lash Lounge:** Purple for luxury tiers, lavender for backgrounds

---

## Source Data Files
- `raw-findings/httbrands-colors.txt` - Raw extracted colors from HTT Brands
- `raw-findings/frenchies-colors.txt` - Raw extracted colors from Frenchies
- `raw-findings/bishops-colors.txt` - Raw extracted colors from Bishops
- `raw-findings/lashlounge-colors.txt` - Raw extracted colors from Lash Lounge

---

*Research conducted by Web-Puppy color analysis agent*  
*All colors extracted from live websites on March 2, 2025*
