# WCAG 2.2 + Chartability Requirements for Data Visualizations

## W3C WAI Guidance for Complex Images (Charts)

Source: https://www.w3.org/WAI/tutorials/images/complex/

### Two-Part Text Alternative Required

Charts and graphs are classified as **complex images** that require:
1. **Short description** — identifies the image, in `alt` attribute
2. **Long description** — textual representation of essential information

### Four Approaches for Long Descriptions

#### Approach 1: Adjacent Text Link (Recommended)
```html
<figure role="group">
  <img src="chart.png"
       alt="Bar chart showing compliance scores for SOC2, NIST, CIS">
  <figcaption>
    <a href="compliance-data.html">Full compliance data table</a>
  </figcaption>
</figure>
```

#### Approach 2: Location in alt attribute
```html
<img src="chart.png"
     alt="Bar chart showing compliance scores. Described under the heading Compliance Data.">
```

#### Approach 3: figure/figcaption with data table
```html
<figure role="group">
  <img src="chart.png"
       alt="Bar chart showing compliance scores, described in detail below.">
  <figcaption>
    <h2>Compliance Scores</h2>
    <table>
      <caption>Framework compliance percentages</caption>
      <tr><th>Framework</th><th>Score</th></tr>
      <tr><td>SOC 2</td><td>87%</td></tr>
    </table>
  </figcaption>
</figure>
```

#### Approach 4: aria-describedby (text-only descriptions)
```html
<img src="chart.png"
     alt="Compliance score chart"
     aria-describedby="chart-desc">
<p id="chart-desc">
  SOC 2 compliance is at 87%, up from 82% last quarter.
  NIST framework shows 92% compliance. CIS benchmark at 78%.
</p>
```

**Note**: `aria-describedby` treats referenced content as one continuous paragraph — no structural info (headings, tables) is conveyed. Use only for text-only descriptions.

---

## Chartability Workbook — 50 Heuristics for Accessible Charts

Source: https://chartability.github.io/POUR-CAF/

### Framework: POUR-CAF
- **P**erceivable — users must identify content via sight, sound, touch
- **O**perable — controls must be error-tolerant, discoverable, multi-modal
- **U**nderstandable — information presented without ambiguity, minimal cognitive load
- **R**obust — compliant with standards, works with assistive tech
- **C**ompromising — transparent, tolerant of different consumption preferences
- **A**ssistive — intelligent, multi-sensory, reduces labor
- **F**lexible — respects user settings, provides control

### 14 Critical Heuristics

#### Perceivable (4 critical)

1. **Low contrast** — Most common failure (88% of audits fail)
   - Geometries and large text: ≥ 3:1 contrast
   - Regular text: ≥ 4.5:1 contrast
   - Tool: https://webaim.org/resources/contrastchecker/

2. **Content is only visual** — Chart info must be available without visuals
   - Test with JAWS+Chrome, NVDA+Firefox, VoiceOver+Safari
   - All annotations, trends, narrative elements exposed to screen readers
   - WCAG ref: https://www.w3.org/WAI/WCAG21/quickref/#text-alternatives

3. **Small text size** — All chart text ≥ 9pt/12px minimum
   - Ideally only axis labels at 9pt; all other text larger

4. **Visual presents seizure risk** — Avoid red flashes, large red areas
   - Tool: PEAT (Photosensitive Epilepsy Analysis Tool)

#### Operable (4 critical)

5. **Interaction modality only has one input type**
   - If mouse interactive, MUST also be keyboard interactive
   - Tab and arrow keys for navigation
   - Focus should mirror hover, enter/space should mirror click
   - WCAG ref: https://www.w3.org/WAI/WCAG21/Understanding/keyboard-no-exception.html

6. **No interaction cues or instructions**
   - All interactive capabilities must be explained
   - Keyboard controls must be documented
   - WCAG ref: https://www.w3.org/WAI/WCAG21/Understanding/labels-or-instructions.html

7. **Controls override AT controls**
   - Custom keyboard controls must NOT override screen reader settings
   - Custom keys only apply when chart has focus
   - No page-level key overrides

#### Understandable (3 critical)

8. **No explanation for purpose or how to read**
   - Chart should explain its purpose and interpretation

9. **No title, summary, or caption**
   - Title, summary, context, or caption MUST be provided

10. **Reading level inappropriate**
    - All text (including alt text) at reading grade level ≤ 9
    - Tool: https://hemingwayapp.com/

#### Compromising (1 critical)

11. **No table**
    - Data table MUST be provided alongside chart
    - Table alone is insufficient — chart still needs to be accessible
    - US Gov Design System: "a data table does not provide an equivalent narrative"
    - Table should be downloadable, filterable, or sortable

#### Assistive (2 critical)

12. **Data density is inappropriate**
    - Charts should not have more than ~5 categories
    - Dense data should be aggregated or divided

13. **Navigation and interaction is tedious**
    - Large blocks of repeated content must be skippable
    - Task completion time should be measured across modalities

#### Flexible (1 critical)

14. **User style change not respected**
    - Charts must not override user styling changes
    - Must respond to custom stylesheets, zoom, font size changes

### Non-Critical but Important Heuristics

- **Color alone communicates meaning** — textures/shapes/size required for categorical
- **Not CVD-friendly** — test with Viz Palette or Chroma.js
- **Meaningful elements indistinguishable** — ≥1px white space between adjacent elements
- **Keyboard focus indicator missing** — 4.5:1 contrast, ≥2px border
- **Inappropriate tab stops** — not every element needs tabindex
- **Target size too small** — interactive elements ≥ 24×24px
- **Visually apparent features not described** — trends, outliers must be in text
- **Data in text not human-readable** — format numbers (6500000000 → "6.5 billion")
- **Zoom and reflow not supported** — content shouldn't be cut off when zoomed
- **Contrast and textures cannot be adjusted** — user should be able to toggle

---

## WCAG 2.2 Specific Success Criteria for Charts

| Criterion | Level | Requirement for Charts |
|-----------|-------|----------------------|
| 1.1.1 Non-text Content | A | Alt text for chart; long description |
| 1.3.1 Info and Relationships | A | Structure conveyed programmatically |
| 1.4.1 Use of Color | A | Color not sole means of conveying info |
| 1.4.3 Contrast (Minimum) | AA | 4.5:1 text, 3:1 non-text |
| 1.4.11 Non-text Contrast | AA | 3:1 for chart elements |
| 2.1.1 Keyboard | A | All functionality via keyboard |
| 2.4.6 Headings and Labels | AA | Descriptive headings/labels |
| 2.4.7 Focus Visible | AA | Visible focus indicator |
| 2.5.8 Target Size | AA | ≥24×24px for interactive elements |
| 4.1.2 Name, Role, Value | A | ARIA roles for interactive charts |
