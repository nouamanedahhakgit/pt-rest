/**
 * Unified Ad Management System
 * Supports multiple ad providers: Ezoic, HBAgency
 * Allows switching between providers via database settings
 * All placement IDs are configurable from database settings
 */

// Ad Provider Types
export type AdProvider = 'ezoic' | 'hbagency' | 'none';

/**
 * Ad placement settings from database
 */
export interface AdSettings {
  // Provider
  ad_provider?: string;

  // Ezoic IDs
  ezoic_id_top?: string;
  ezoic_id_under_title?: string;
  ezoic_id_bottom?: string;
  ezoic_id_sidebar?: string;
  ezoic_id_sidebar_middle?: string;
  ezoic_id_in_content_1?: string;
  ezoic_id_in_content_2?: string;
  ezoic_id_in_content_3?: string;
  ezoic_id_in_content_4?: string;
  ezoic_id_in_content_5?: string;
  ezoic_id_bottom_alt?: string;
  ezoic_id_recipe_card?: string;

  // HBAgency settings
  hbagency_script_url?: string;
  hbagency_ads_txt_url?: string;
  hbagency_space_top?: string;
  hbagency_space_under_title?: string;
  hbagency_space_sidebar?: string;
  hbagency_space_sidebar_middle?: string;
  hbagency_space_in_content?: string;
  hbagency_space_in_content_1?: string;
  hbagency_space_in_content_2?: string;
  hbagency_space_in_content_3?: string;
  hbagency_space_in_content_4?: string;
  hbagency_space_in_content_5?: string;
  hbagency_space_bottom?: string;
  hbagency_space_recipe_card?: string;
  hbagency_space_floor?: string;
  hbagency_space_interstitial?: string;
}

/**
 * Ad Placement Configuration
 * Maps logical placement names to provider-specific implementations
 */
export interface AdPlacement {
  id: string;
  name: string;
  location: 'top' | 'under_title' | 'sidebar' | 'in_content' | 'bottom' | 'recipe_card';
  aboveFold: boolean;
}

/**
 * Standard ad placements used across the site
 */
export const AdPlacements = {
  TOP_OF_PAGE: { id: 'top_of_page', name: 'Top of Page', location: 'top', aboveFold: true },
  UNDER_PAGE_TITLE: { id: 'under_page_title', name: 'Under Page Title', location: 'under_title', aboveFold: true },
  SIDEBAR: { id: 'sidebar', name: 'Sidebar', location: 'sidebar', aboveFold: false },
  SIDEBAR_MIDDLE: { id: 'sidebar_middle', name: 'Sidebar Middle', location: 'sidebar', aboveFold: false },
  IN_CONTENT_1: { id: 'in_content_1', name: 'In Content 1', location: 'in_content', aboveFold: false },
  IN_CONTENT_2: { id: 'in_content_2', name: 'In Content 2', location: 'in_content', aboveFold: false },
  IN_CONTENT_3: { id: 'in_content_3', name: 'In Content 3', location: 'in_content', aboveFold: false },
  IN_CONTENT_4: { id: 'in_content_4', name: 'In Content 4', location: 'in_content', aboveFold: false },
  IN_CONTENT_5: { id: 'in_content_5', name: 'In Content 5', location: 'in_content', aboveFold: false },
  BOTTOM_OF_PAGE: { id: 'bottom_of_page', name: 'Bottom of Page', location: 'bottom', aboveFold: false },
  BOTTOM_OF_PAGE_ALT: { id: 'bottom_of_page_alt', name: 'Bottom of Page Alt', location: 'bottom', aboveFold: false },
  RECIPE_CARD: { id: 'recipe_card', name: 'Recipe Card', location: 'recipe_card', aboveFold: false },
} as const;

// ============================================================
// EZOIC CONFIGURATION
// ============================================================

/**
 * Default Ezoic Placement IDs (used if not set in database)
 */
export const DefaultEzoicIds: Record<string, number> = {
  top_of_page: 101,
  under_page_title: 102,
  bottom_of_page: 103,
  sidebar: 104,
  sidebar_middle: 105,
  in_content_1: 109,
  in_content_2: 110,
  in_content_3: 111,
  in_content_4: 112,
  in_content_5: 113,
  bottom_of_page_alt: 118,
  recipe_card: 120,
};

/**
 * Get Ezoic placement ID from settings or use default
 */
export function getEzoicId(placementId: string, settings: AdSettings = {}): number {
  const settingsMap: Record<string, keyof AdSettings> = {
    'top_of_page': 'ezoic_id_top',
    'under_page_title': 'ezoic_id_under_title',
    'bottom_of_page': 'ezoic_id_bottom',
    'sidebar': 'ezoic_id_sidebar',
    'sidebar_middle': 'ezoic_id_sidebar_middle',
    'in_content_1': 'ezoic_id_in_content_1',
    'in_content_2': 'ezoic_id_in_content_2',
    'in_content_3': 'ezoic_id_in_content_3',
    'in_content_4': 'ezoic_id_in_content_4',
    'in_content_5': 'ezoic_id_in_content_5',
    'bottom_of_page_alt': 'ezoic_id_bottom_alt',
    'recipe_card': 'ezoic_id_recipe_card',
  };

  const key = settingsMap[placementId];
  if (key && settings[key]) {
    return parseInt(settings[key] as string, 10) || DefaultEzoicIds[placementId];
  }

  return DefaultEzoicIds[placementId];
}

/**
 * Generate Ezoic ad placeholder with settings from database
 */
export function getEzoicPlaceholder(placementId: string, settings: AdSettings = {}, lazy: boolean = true): string {
  const numericId = getEzoicId(placementId, settings);
  if (!numericId) {
    console.warn(`Unknown Ezoic placement: ${placementId}`);
    return '';
  }

  const placement = Object.values(AdPlacements).find(p => p.id === placementId);
  const isAboveFold = placement?.aboveFold ?? false;
  const shouldLazyLoad = lazy && !isAboveFold;

  if (shouldLazyLoad) {
    return `<div id="ezoic-pub-ad-placeholder-${numericId}" data-ezoic-lazy="true"></div>`;
  }
  return `<div id="ezoic-pub-ad-placeholder-${numericId}"></div>`;
}

// ============================================================
// HBAGENCY CONFIGURATION
// ============================================================

/**
 * Get HBAgency space ID from settings
 * For in-content ads, first checks for specific placement (in_content_1, etc.)
 * then falls back to the generic in_content setting
 */
export function getHBAgencySpaceId(placementId: string, settings: AdSettings = {}): string {
  // First, try specific mapping for this placement
  const specificMap: Record<string, keyof AdSettings> = {
    'top_of_page': 'hbagency_space_top',
    'under_page_title': 'hbagency_space_under_title',
    'bottom_of_page': 'hbagency_space_bottom',
    'sidebar': 'hbagency_space_sidebar',
    'sidebar_middle': 'hbagency_space_sidebar_middle',
    'in_content_1': 'hbagency_space_in_content_1',
    'in_content_2': 'hbagency_space_in_content_2',
    'in_content_3': 'hbagency_space_in_content_3',
    'in_content_4': 'hbagency_space_in_content_4',
    'in_content_5': 'hbagency_space_in_content_5',
    'bottom_of_page_alt': 'hbagency_space_bottom',
    'recipe_card': 'hbagency_space_recipe_card',
  };

  const specificKey = specificMap[placementId];
  if (specificKey && settings[specificKey]) {
    return settings[specificKey] as string;
  }

  // Fallback: for in_content placements, use the generic hbagency_space_in_content
  if (placementId.startsWith('in_content_') && settings.hbagency_space_in_content) {
    return settings.hbagency_space_in_content as string;
  }

  return '';
}

/**
 * Generate HBAgency ad placeholder with settings from database
 */
export function getHBAgencyPlaceholder(placementId: string, settings: AdSettings = {}, lazy: boolean = true): string {
  const spaceId = getHBAgencySpaceId(placementId, settings);
  if (!spaceId) {
    // No space ID configured - return empty
    return '';
  }

  return `<div class="hb-ad-inpage"><div class="hb-ad-inner"><div class="hbagency_cls hbagency_space_${spaceId}"></div></div></div>`;
}

/**
 * Generate HBAgency Floor Ad (sticky footer ad with close button)
 */
export function getHBAgencyFloorAd(settings: AdSettings = {}): string {
  const spaceId = settings.hbagency_space_floor;
  if (!spaceId) {
    return '';
  }

  return `<div id="HB_Footer_Close_hbagency_space_${spaceId}" class="hb-floor-ad">
  <div id="HB_CLOSE_hbagency_space_${spaceId}" class="hb-floor-close" onclick="this.parentElement.style.display='none';" aria-label="Close ad"></div>
  <div id="HB_OUTER_hbagency_space_${spaceId}" class="hb-floor-outer">
    <div id="hbagency_space_${spaceId}"></div>
  </div>
</div>`;
}

/**
 * Generate HBAgency Interstitial Ad
 */
export function getHBAgencyInterstitial(settings: AdSettings = {}): string {
  const spaceId = settings.hbagency_space_interstitial;
  if (!spaceId) {
    return '';
  }

  return `<div id="hbagency_space_${spaceId}" class="hb-interstitial"></div>`;
}

// ============================================================
// UNIFIED AD SYSTEM
// ============================================================

/**
 * Get ad placeholder based on current provider and settings
 */
export function getAdPlaceholder(
  placementId: string,
  provider: AdProvider,
  lazy: boolean = true,
  settings: AdSettings = {}
): string {
  switch (provider) {
    case 'ezoic':
      return getEzoicPlaceholder(placementId, settings, lazy);
    case 'hbagency':
      return getHBAgencyPlaceholder(placementId, settings, lazy);
    case 'none':
    default:
      return '';
  }
}

/**
 * Get Ezoic IDs for above-fold placements (for showAds call)
 */
export function getEzoicAboveFoldIds(settings: AdSettings = {}): number[] {
  return [
    getEzoicId('top_of_page', settings),
    getEzoicId('under_page_title', settings),
  ].filter(Boolean);
}

/**
 * Get multiple ad placeholders
 */
export function getAdPlaceholders(
  placementIds: string[],
  provider: AdProvider,
  lazy: boolean = true,
  settings: AdSettings = {}
): string {
  return placementIds
    .map(id => getAdPlaceholder(id, provider, lazy, settings))
    .filter(Boolean)
    .join('\n');
}

/**
 * Get the initialization script for the ad provider
 */
export function getAdProviderScript(provider: AdProvider): string {
  switch (provider) {
    case 'ezoic':
      return getEzoicInitScript();
    case 'hbagency':
      return getHBAgencyInitScript();
    case 'none':
    default:
      return '';
  }
}

/**
 * Ezoic initialization and lazy-loading script
 */
function getEzoicInitScript(): string {
  return `
<script>
(function() {
  'use strict';

  // Track which ads have been loaded
  var loadedAds = {};

  // Initialize Intersection Observer for lazy-loading ads
  function initLazyAds() {
    if (!('IntersectionObserver' in window)) {
      // Fallback: load all ads immediately for older browsers
      loadAllLazyAds();
      return;
    }

    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var el = entry.target;
          var placementId = el.id.replace('ezoic-pub-ad-placeholder-', '');

          if (!loadedAds[placementId]) {
            loadedAds[placementId] = true;
            loadAd(parseInt(placementId, 10));
            observer.unobserve(el);
          }
        }
      });
    }, {
      rootMargin: '200px 0px', // Start loading 200px before entering viewport
      threshold: 0
    });

    // Find all lazy ad placeholders
    var lazyAds = document.querySelectorAll('[data-ezoic-lazy="true"]');
    lazyAds.forEach(function(el) {
      observer.observe(el);
    });
  }

  // Load a single ad by placement ID
  function loadAd(placementId) {
    if (typeof window.ezstandalone !== 'undefined') {
      window.ezstandalone.cmd.push(function() {
        window.ezstandalone.showAds(placementId);
      });
    }
  }

  // Fallback: load all lazy ads immediately
  function loadAllLazyAds() {
    var lazyAds = document.querySelectorAll('[data-ezoic-lazy="true"]');
    lazyAds.forEach(function(el) {
      var placementId = el.id.replace('ezoic-pub-ad-placeholder-', '');
      if (!loadedAds[placementId]) {
        loadedAds[placementId] = true;
        loadAd(parseInt(placementId, 10));
      }
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLazyAds);
  } else {
    initLazyAds();
  }
})();
</script>`;
}

/**
 * HBAgency initialization script (no lazy loading - HBAgency handles ad loading)
 */
function getHBAgencyInitScript(): string {
  // HBAgency handles its own ad loading, no additional script needed
  return '';
}

/**
 * Inject ads into HTML content based on provider and settings
 */
export function injectContentAds(
  htmlContent: string,
  provider: AdProvider,
  settings: AdSettings = {},
  maxAds: number = 5
): string {
  if (provider === 'none') {
    return htmlContent;
  }

  const paragraphs = htmlContent.match(/<p[^>]*>.*?<\/p>/gs) || [];
  const paragraphCount = paragraphs.length;

  if (paragraphCount < 3) {
    return htmlContent;
  }

  // Determine how many in-content ads to use based on content length
  let adsToInsert = 0;
  if (paragraphCount >= 3) adsToInsert = 2;
  if (paragraphCount >= 6) adsToInsert = 3;
  if (paragraphCount >= 10) adsToInsert = 4;
  if (paragraphCount >= 15) adsToInsert = Math.min(maxAds, 5);

  const contentAdIds = [
    'in_content_1',
    'in_content_2',
    'in_content_3',
    'in_content_4',
    'in_content_5',
  ].slice(0, adsToInsert);

  const insertPositions: Array<{ index: number; adId: string }> = [];

  // Find H3 tags to insert ads before
  const h3Pattern = /<h3[^>]*>/gi;
  const allH3s = [...htmlContent.matchAll(h3Pattern)];

  let usedAds = 0;

  for (const h3Match of allH3s) {
    if (usedAds >= contentAdIds.length) break;
    if (h3Match.index === undefined) continue;

    // Check if there's a </p> before this H3
    const beforeH3 = htmlContent.substring(0, h3Match.index);
    const lastPIndex = beforeH3.lastIndexOf('</p>');

    if (lastPIndex === -1) continue;

    // Check content between </p> and <h3>
    const between = htmlContent.substring(lastPIndex + 4, h3Match.index);
    const hasOnlyWhitespace = /^[\s\n\r]*$/.test(between);

    if (!hasOnlyWhitespace) continue;

    // Skip if inside a list
    if (isInsideList(htmlContent, h3Match.index)) continue;

    insertPositions.push({
      index: h3Match.index,
      adId: contentAdIds[usedAds],
    });

    usedAds++;
  }

  // If we still need more ads, distribute across paragraphs
  if (usedAds < contentAdIds.length) {
    const allPs = [...htmlContent.matchAll(/<p[^>]*>.*?<\/p>/gs)];
    const remaining = contentAdIds.length - usedAds;
    const spacing = Math.max(1, Math.floor(allPs.length / (remaining + 1)));

    for (let i = 0; i < remaining; i++) {
      const pIndex = Math.min((i + 1) * spacing, allPs.length - 1);
      const pMatch = allPs[pIndex];

      if (pMatch && pMatch.index !== undefined) {
        const insertAt = pMatch.index + pMatch[0].length;

        if (isInsideList(htmlContent, pMatch.index)) continue;

        const tooClose = insertPositions.some(pos => Math.abs(pos.index - insertAt) < 100);
        if (tooClose) continue;

        insertPositions.push({
          index: insertAt,
          adId: contentAdIds[usedAds],
        });

        usedAds++;
      }
    }
  }

  if (insertPositions.length === 0) {
    return htmlContent;
  }

  // Sort descending to insert from end to start
  insertPositions.sort((a, b) => b.index - a.index);

  let result = htmlContent;

  for (const pos of insertPositions) {
    const placeholder = getAdPlaceholder(pos.adId, provider, true, settings);
    result = result.slice(0, pos.index) + '\n' + placeholder + '\n' + result.slice(pos.index);
  }

  return result;
}

/**
 * Check if a position in HTML is inside a list
 */
function isInsideList(htmlContent: string, position: number): boolean {
  const beforeContent = htmlContent.substring(0, position);

  const openUl = (beforeContent.match(/<ul[^>]*>/gi) || []).length;
  const closeUl = (beforeContent.match(/<\/ul>/gi) || []).length;

  const openDiv = (beforeContent.match(/<div[^>]*class="[^"]*\bwp-block-group\b[^"]*"[^>]*>/gi) || []).length;
  const closeDiv = (beforeContent.match(/<\/div>/gi) || []).length;

  return (openUl > closeUl) || (openDiv > closeDiv);
}

/**
 * CSS styles for HBAgency ads
 */
export function getHBAgencyStyles(): string {
  return `
<style>
.hb-ad-inpage {
  display: block;
  width: 100%;
  margin: 1.5rem 0;
  text-align: center;
}

.hb-ad-inner {
  display: inline-block;
  max-width: 100%;
}

.hbagency_cls {
  min-height: 90px;
}

/* Floor Ad (Sticky Footer) Styles */
.hb-floor-ad {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: #fff;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.15);
  text-align: center;
  padding: 0;
}

.hb-floor-close {
  position: absolute;
  top: -24px;
  right: 10px;
  width: 24px;
  height: 24px;
  background: #333;
  border-radius: 50%;
  cursor: pointer;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hb-floor-close::before,
.hb-floor-close::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 2px;
  background: #fff;
}

.hb-floor-close::before {
  transform: rotate(45deg);
}

.hb-floor-close::after {
  transform: rotate(-45deg);
}

.hb-floor-close:hover {
  background: #555;
}

.hb-floor-outer {
  padding: 8px 0;
}

/* Interstitial Ad Styles */
.hb-interstitial {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
}

@media print {
  .hb-ad-inpage,
  .hb-floor-ad,
  .hb-interstitial {
    display: none !important;
  }
}

/* Mobile adjustments for floor ad */
@media (max-width: 768px) {
  .hb-floor-close {
    top: -20px;
    right: 8px;
    width: 20px;
    height: 20px;
  }

  .hb-floor-close::before,
  .hb-floor-close::after {
    width: 10px;
  }
}
</style>`;
}
