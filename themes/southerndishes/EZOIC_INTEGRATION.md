# Ezoic Ad Integration Documentation

This document describes the complete Ezoic ad integration for your recipe website.

## Current Implementation Status

✅ **Fully Integrated** - Server-side rendering (SSR) with automatic ad refresh on page loads

Your site uses **traditional server-rendered navigation**, which means:
- Every page load triggers a full server response
- Ezoic ads refresh automatically with each navigation
- No special dynamic ad handling needed currently

---

## Ad Placements Overview

### Site-Wide Placements (All Pages)

These placements are in `Layout.astro` and appear on every page:

| ID | Name | Location | Devices |
|----|------|----------|---------|
| 101 | top_of_page | After header | All |
| 103 | bottom_of_page | Before footer | All |
| 118 | bottom_of_page_alt | Before footer | All |

### Recipe Detail Pages (`[slug].astro`)

| ID | Name | Location | Devices | Condition |
|----|------|----------|---------|-----------|
| 102 | under_page_title | After recipe title | All | - |
| 104 | sidebar | Sidebar top | All | - |
| 105 | sidebar_middle | Sidebar middle | All | - |
| 109 | under_first_paragraph | After 1st paragraph | All | 3+ paragraphs |
| 110 | under_second_paragraph | After 2nd paragraph | All | 3+ paragraphs |
| 111 | mid_content | ~40% through article | All | 6+ paragraphs |
| 112 | long_content | ~50% through article | All | 10+ paragraphs |
| 113 | longer_content | ~65% through article | All | 10+ paragraphs |
| 114 | longest_content | ~80% through article | All | 15+ paragraphs |
| 115 | incontent_5 | ~90% through article | All | 15+ paragraphs |

### Listing Pages (Homepage, Categories, Recipes, Authors)

| ID | Name | Location |
|----|------|----------|
| 102 | under_page_title | After page title/hero |

### Print Pages (`print/[slug].astro`)

| ID | Name | Location | Print Behavior |
|----|------|----------|----------------|
| 101 | top_of_page | After header | Hidden when printing |
| 102 | under_page_title | After title | Hidden when printing |
| 103 | bottom_of_page | Before footer | Hidden when printing |

**Note**: Print page ads are hidden via CSS `@media print` rules.

---

## Files Structure

### Core Utilities

```
/src/lib/
├── ezoic.ts           # Static ad placement utilities (ACTIVE)
└── ezoic-dynamic.ts   # Dynamic ad refresh utilities (FUTURE USE)
```

### Integration Points

```
/src/
├── layouts/
│   └── Layout.astro           # Site-wide placements (101, 103, 118)
├── pages/
│   ├── [slug].astro           # Recipe detail with content ads (101-115, 118)
│   ├── index.astro            # Homepage (101-103, 118)
│   ├── recipes.astro          # Recipes listing (101-103, 118)
│   ├── category/[slug].astro  # Category pages (101-103, 118)
│   ├── author/[slug].astro    # Author pages (101-103, 118)
│   └── print/[slug].astro     # Print pages (101-103)
```

---

## Current Implementation (`ezoic.ts`)

### Static Utilities (Currently Used)

```typescript
import { EzoicPlacements, injectContentAds, getContentAdPlacements } from '../lib/ezoic';

// 1. Get placement IDs based on article length
const paragraphCount = (content.match(/<p[^>]*>.*?<\/p>/gs) || []).length;
const contentAdPlacements = getContentAdPlacements(paragraphCount);
// Returns: [109, 110] for 3+ paragraphs, adds more for longer articles

// 2. Inject ad placeholders into HTML content
const contentWithAds = injectContentAds(articleHtml);
// Automatically inserts <div id="ezoic-pub-ad-placeholder-{ID}"></div>

// 3. Call showAds() on page load
const allPlacements = [101, 102, ...contentAdPlacements, 103, 118];
<script is:inline define:vars={{ allPlacements }}>
  ezstandalone.cmd.push(function () {
    ezstandalone.showAds(...allPlacements);
  });
</script>
```

---

## Future: Dynamic Ad Handling (`ezoic-dynamic.ts`)

### When to Use Dynamic Utilities

Use these **ONLY** if you add these features:

1. **Infinite Scroll**
   ```typescript
   import { EzoicDynamic } from '../lib/ezoic-dynamic';

   function loadMoreArticles() {
     // Add new content with ads
     container.insertAdjacentHTML('beforeend', newContentHtml);

     // Show ads for newly loaded content
     EzoicDynamic.showNewAds([104, 105]);
   }
   ```

2. **Tab/Accordion Content**
   ```typescript
   tabButton.addEventListener('click', () => {
     showTabContent(tabId);

     // Refresh ads after tab content changes
     EzoicDynamic.refreshAds();
   });
   ```

3. **Modal/Popup with Ads**
   ```typescript
   // When opening modal
   openModal();
   EzoicDynamic.showNewAds([106, 107]);

   // When closing modal
   EzoicDynamic.destroyAds([106, 107]);
   closeModal();
   ```

4. **SPA Client-Side Routing**
   ```typescript
   router.afterEach(() => {
     // Refresh all ads after route change
     EzoicDynamic.showAllAds();
   });
   ```

### Available Functions

| Function | Use Case | Example |
|----------|----------|---------|
| `refreshAds()` | Content changes, placeholders stay | Tab switching |
| `showNewAds([ids])` | New placeholders added | Infinite scroll |
| `destroyAds([ids])` | Before removing content | Closing modal |
| `destroyAllAds()` | Complete page replacement | SPA navigation |
| `destroyAndShowAds([ids])` | Reusing same IDs | Infinite scroll (same IDs) |
| `showAllAds()` | Show all available ads | Initial page load |
| `waitForEzoic(timeout)` | Ensure Ezoic loaded | Before ad operations |

---

## Custom Header Code Integration

The site supports custom code injection via database settings:

### Settings Table Fields

- `custom_head_code` - Injected in `<head>` (e.g., Ezoic script, analytics)
- `custom_body_top_code` - Injected after `<body>` opening
- `custom_body_bottom_code` - Injected before `</body>` closing

### Files That Support Custom Code

- ✅ All pages using `Layout.astro`
- ✅ Print pages (`print/[slug].astro`)

### Example: Adding Ezoic Script via Settings

Instead of hardcoding, you can add to database:

```sql
UPDATE settings
SET value = '<script async src="//www.ezoic.com/ezoic/ezoic.js"></script>'
WHERE key = 'custom_head_code';
```

This will inject the script on all pages automatically.

---

## Pages WITHOUT Ezoic Ads

These pages only have Layout-level ads (101, 103, 118):

- `/about-us/` - About Us page
- `/contact-us/` - Contact page
- `/privacy-policy/` - Privacy policy
- `/terms-of-use/` - Terms of use
- `/gdpr-policy/` - GDPR policy
- `/cookie-policy/` - Cookie policy
- `/copyright-policy/` - Copyright policy
- `/disclaimer/` - Disclaimer

**Reason**: Informational/legal pages typically have lower ad value and better UX without extra ads.

---

## Testing Your Ad Integration

### 1. Visual Verification

Visit these pages and check for ad placeholders:

- ✅ Homepage: `/`
- ✅ Recipe detail: `/chicken-caesar-pasta-salad-tasty-and-easy-recipe/`
- ✅ Category page: `/category/desserts/`
- ✅ All recipes: `/recipes/`
- ✅ Print page: `/print/chicken-caesar-pasta-salad-tasty-and-easy-recipe/`

### 2. Browser Console Check

Open DevTools Console and verify:

```javascript
// Check if Ezoic loaded
console.log(window.ezstandalone); // Should show object

// Check for ad placeholders in DOM
document.querySelectorAll('[id^="ezoic-pub-ad-placeholder-"]');
// Should return NodeList with multiple elements

// Check which ads are being called
// Look for: ezstandalone.showAds(101, 102, 103, ...)
```

### 3. Network Tab Check

In DevTools Network tab, filter by "ezoic":
- ✅ Ezoic script loaded from `ezoic.com`
- ✅ Ad requests being made
- ✅ No 404 errors

### 4. Print Page Test

1. Visit `/print/your-recipe-slug/`
2. Click "Print Recipe" button
3. In print preview, verify ads are **hidden**

---

## Performance Considerations

### Current Setup (Optimal)

✅ **Server-side ad injection** - Ads load with initial HTML
✅ **Single `showAds()` call** per page - Efficient initialization
✅ **Content-aware placement** - Only shows ads if enough content
✅ **Print-optimized** - Ads hidden when printing

### If Adding Dynamic Features

⚠️ **Avoid frequent `refresh()` calls** - Can cause layout shift
⚠️ **Batch ad operations** - Don't call `showAds()` for each element
⚠️ **Clean up destroyed ads** - Always destroy before removing DOM
⚠️ **Test thoroughly** - Dynamic ads can impact Core Web Vitals

---

## Troubleshooting

### Ads Not Showing

1. **Check Ezoic script loaded**
   ```javascript
   console.log(window.ezstandalone);
   ```

2. **Check placeholder exists**
   ```javascript
   document.getElementById('ezoic-pub-ad-placeholder-101');
   ```

3. **Check showAds() was called**
   - Look in Console for any errors
   - Verify `ezstandalone.cmd.push()` executed

4. **Check custom header code**
   - Verify `custom_head_code` in settings contains Ezoic script

### Duplicate Ad IDs Error

- **Never have two placeholders with same ID on one page**
- Use `destroyPlaceholders()` before reusing IDs
- For infinite scroll, use unique IDs or destroy-then-show pattern

### Ads Showing on Print

- Verify CSS has `@media print { .ezoic-ad { display: none; } }`
- Check that ad divs have `ezoic-ad` class

---

## Summary

Your Ezoic integration is **complete and production-ready** for your current server-rendered architecture. The dynamic utilities (`ezoic-dynamic.ts`) are available if you add dynamic features in the future, but they're not needed now.

**Next Steps:**
1. ✅ Test ads on live site
2. ✅ Monitor Ezoic dashboard for ad performance
3. ✅ Adjust placements based on Ezoic recommendations
4. 📦 Keep `ezoic-dynamic.ts` for future enhancements

**Questions?** Check Ezoic's documentation: https://support.ezoic.com/
