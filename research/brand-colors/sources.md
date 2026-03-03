# Brand Color Research Sources

## Source Documentation

### Primary Sources (Tier 1 - Official Websites)

#### 1. HTT Brands (Head To Toe Brands)
- **URL:** https://httbrands.com
- **Type:** Official corporate website
- **Date Accessed:** March 2, 2025
- **Credibility:** Tier 1 - Official brand website, direct from source
- **Method:** Live HTML extraction using curl + browser inspection
- **Data Quality:** High - extracted 50+ unique colors
- **Notes:** Corporate site showcasing all four brands in portfolio

#### 2. Frenchies Nails
- **URL:** https://frenchiesnails.com
- **Type:** Official brand website
- **Date Accessed:** March 2, 2025
- **Credibility:** Tier 1 - Official brand website, direct from source
- **Method:** Live HTML extraction using curl + browser inspection
- **Data Quality:** High - extracted 30+ unique colors
- **Notes:** Clean, health-focused nail salon brand

#### 3. Bishops Haircuts
- **URL:** https://bishops.co
- **Type:** Official brand website
- **Date Accessed:** March 2, 2025
- **Credibility:** Tier 1 - Official brand website, direct from source
- **Method:** Live HTML extraction using curl + browser inspection
- **Data Quality:** High - extracted 20+ unique colors
- **Notes:** Bold, creative hair salon brand with strong orange identity

#### 4. The Lash Lounge
- **URL:** https://thelashlounge.com
- **Type:** Official brand website
- **Date Accessed:** March 2, 2025
- **Credibility:** Tier 1 - Official brand website, direct from source
- **Method:** Live HTML extraction using curl + browser inspection
- **Data Quality:** High - extracted 25+ unique colors
- **Notes:** Premium eyelash extension brand with purple luxury aesthetic

---

## Extraction Methodology

### Tools Used
1. **Browser Automation** (Playwright/Chromium)
   - Full-page screenshots for visual verification
   - Element inspection for color usage patterns
   - Screenshot documentation for reference

2. **Command Line Tools**
   - `curl` for HTML extraction
   - `grep` with regex patterns for color extraction:
     - `#[0-9A-Fa-f]{6}` - 6-digit hex colors
     - `#[0-9A-Fa-f]{3}` - 3-digit hex colors
     - `rgb\([0-9, ]+\)` - RGB values
     - `rgba\([0-9, .]+\)` - RGBA values

3. **Pattern Analysis**
   - Count of color occurrences (frequency = importance)
   - Visual context from screenshots
   - Semantic analysis (where colors are used)

### Extraction Process
1. Navigate to each website homepage
2. Capture full-page screenshot for visual reference
3. Extract HTML source via curl
4. Parse for all color values (hex, rgb, rgba)
5. Count occurrences to determine primary vs accent
6. Cross-reference with screenshot for context
7. Document findings in structured format

---

## Source Reliability Assessment

### Tier 1 Sources (Official Websites)
| Website | Reliability | Currency | Authority | Validation |
|---------|-------------|----------|-----------|------------|
| httbrands.com | High | Current | Official | Direct source |
| frenchiesnails.com | High | Current | Official | Direct source |
| bishops.co | High | Current | Official | Direct source |
| thelashlounge.com | High | Current | Official | Direct source |

### Data Quality Indicators
- ✅ All colors extracted from live production sites
- ✅ Multiple extraction methods used (browser + curl)
- ✅ Screenshots captured for visual verification
- ✅ Color frequency analysis performed
- ✅ Cross-checked across multiple page elements

---

## Limitations & Considerations

### Technical Limitations
1. **Dynamic Content:** Some colors may be loaded via JavaScript and not captured in initial HTML
2. **External Stylesheets:** Colors defined in external CSS files may not be fully captured
3. **Image-Based Colors:** Logo colors extracted from CSS may not match actual image files

### Mitigation Strategies
1. Used screenshots for visual color verification
2. Extracted from multiple page elements (not just CSS)
3. Cross-referenced with brand identity patterns
4. Prioritized colors by frequency of occurrence

---

## Source Files Generated
- `raw-findings/httbrands-colors.txt` - 50+ colors extracted
- `raw-findings/frenchies-colors.txt` - 30+ colors extracted
- `raw-findings/bishops-colors.txt` - 20+ colors extracted
- `raw-findings/lashlounge-colors.txt` - 25+ colors extracted

---

*Sources evaluated and documented by Web-Puppy research agent*  
*All extractions completed on March 2, 2025*
