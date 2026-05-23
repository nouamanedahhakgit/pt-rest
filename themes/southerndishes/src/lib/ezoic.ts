/**
 * Ezoic Ad Placement Utilities
 * Handles ad placeholder generation and content-based ad injection
 */

/**
 * Ezoic Placement IDs
 */
export const EzoicPlacements = {
  TOP_OF_PAGE: 101,
  UNDER_PAGE_TITLE: 102,
  BOTTOM_OF_PAGE: 103,
  SIDEBAR: 104,
  SIDEBAR_MIDDLE: 105,
  SIDEBAR_BOTTOM: 106, // Desktop only
  SIDEBAR_FLOATING_1: 107, // Desktop only
  SIDEBAR_FLOATING_2: 108, // Desktop only
  UNDER_FIRST_PARAGRAPH: 109,
  UNDER_SECOND_PARAGRAPH: 110,
  MID_CONTENT: 111,
  LONG_CONTENT: 112,
  LONGER_CONTENT: 113,
  LONGEST_CONTENT: 114,
  INCONTENT_5: 115,
  BOTTOM_OF_PAGE_ALT: 118,
} as const;

/**
 * Generate Ezoic ad placeholder div
 */
export function getEzoicPlaceholder(placementId: number): string {
  return `<div id="ezoic-pub-ad-placeholder-${placementId}"></div>`;
}

/**
 * Generate showAds() script for given placement IDs
 */
export function getEzoicShowAdsScript(placementIds: number[]): string {
  if (placementIds.length === 0) return '';

  return `
<script>
  ezstandalone.cmd.push(function () {
    ezstandalone.showAds(${placementIds.join(', ')});
  });
</script>`;
}

/**
 * Determine which content ads to show based on paragraph count
 */
export function getContentAdPlacements(paragraphCount: number): number[] {
  const placements: number[] = [];

  // Base placements for 3+ paragraphs
  if (paragraphCount >= 3) {
    placements.push(
      EzoicPlacements.UNDER_FIRST_PARAGRAPH,
      EzoicPlacements.UNDER_SECOND_PARAGRAPH
    );
  }

  // 6+ paragraphs: add mid-content
  if (paragraphCount >= 6) {
    placements.push(EzoicPlacements.MID_CONTENT);
  }

  // 10+ paragraphs: add long content placements
  if (paragraphCount >= 10) {
    placements.push(
      EzoicPlacements.LONG_CONTENT,
      EzoicPlacements.LONGER_CONTENT
    );
  }

  // 15+ paragraphs: add longest content placements
  if (paragraphCount >= 15) {
    placements.push(
      EzoicPlacements.LONGEST_CONTENT,
      EzoicPlacements.INCONTENT_5
    );
  }

  return placements;
}

/**
 * Inject ad placeholders into HTML content based on paragraph positions
 * Returns modified HTML with ad placeholders inserted
 */
export function injectContentAds(htmlContent: string): string {
  // Parse HTML to count paragraphs
  const paragraphs = htmlContent.match(/<p[^>]*>.*?<\/p>/gs) || [];
  const paragraphCount = paragraphs.length;

  if (paragraphCount < 3) {
    return htmlContent; // Not enough paragraphs for ads
  }

  let modifiedContent = htmlContent;
  const adPlacements = getContentAdPlacements(paragraphCount);

  // Track which ads we've inserted
  const adsToInsert: { position: number; placementId: number }[] = [];

  // Under first paragraph (109)
  if (adPlacements.includes(EzoicPlacements.UNDER_FIRST_PARAGRAPH)) {
    adsToInsert.push({ position: 1, placementId: EzoicPlacements.UNDER_FIRST_PARAGRAPH });
  }

  // Under second paragraph (110)
  if (adPlacements.includes(EzoicPlacements.UNDER_SECOND_PARAGRAPH)) {
    adsToInsert.push({ position: 2, placementId: EzoicPlacements.UNDER_SECOND_PARAGRAPH });
  }

  // Mid content (111) - at ~40% of content
  if (adPlacements.includes(EzoicPlacements.MID_CONTENT)) {
    const midPosition = Math.floor(paragraphCount * 0.4);
    adsToInsert.push({ position: midPosition, placementId: EzoicPlacements.MID_CONTENT });
  }

  // Long content (112) - at ~50% for articles with 10+ paragraphs
  if (adPlacements.includes(EzoicPlacements.LONG_CONTENT)) {
    const longPosition = Math.floor(paragraphCount * 0.5);
    adsToInsert.push({ position: longPosition, placementId: EzoicPlacements.LONG_CONTENT });
  }

  // Longer content (113) - at ~65% for articles with 10+ paragraphs
  if (adPlacements.includes(EzoicPlacements.LONGER_CONTENT)) {
    const longerPosition = Math.floor(paragraphCount * 0.65);
    adsToInsert.push({ position: longerPosition, placementId: EzoicPlacements.LONGER_CONTENT });
  }

  // Longest content (114) - at ~80% for articles with 15+ paragraphs
  if (adPlacements.includes(EzoicPlacements.LONGEST_CONTENT)) {
    const longestPosition = Math.floor(paragraphCount * 0.8);
    adsToInsert.push({ position: longestPosition, placementId: EzoicPlacements.LONGEST_CONTENT });
  }

  // Incontent 5 (115) - near end, at ~90% for articles with 15+ paragraphs
  if (adPlacements.includes(EzoicPlacements.INCONTENT_5)) {
    const incontent5Position = Math.floor(paragraphCount * 0.9);
    adsToInsert.push({ position: incontent5Position, placementId: EzoicPlacements.INCONTENT_5 });
  }

  // Sort ads by position (highest to lowest to avoid index shifting)
  adsToInsert.sort((a, b) => b.position - a.position);

  // Split content by paragraphs and insert ads
  let currentContent = modifiedContent;

  for (const ad of adsToInsert) {
    const regex = new RegExp(`(<p[^>]*>.*?<\\/p>)`, 'gs');
    const matches = [...currentContent.matchAll(regex)];

    if (matches.length > ad.position) {
      const targetParagraph = matches[ad.position];
      const insertPosition = targetParagraph.index! + targetParagraph[0].length;

      currentContent =
        currentContent.slice(0, insertPosition) +
        '\n' + getEzoicPlaceholder(ad.placementId) + '\n' +
        currentContent.slice(insertPosition);
    }
  }

  return currentContent;
}

/**
 * Get all placement IDs used on a page
 * Useful for generating the showAds() call
 */
export function getAllPagePlacements(options: {
  hasTitle?: boolean;
  hasSidebar?: boolean;
  hasContent?: boolean;
  paragraphCount?: number;
  includeDesktopOnly?: boolean;
}): number[] {
  const placements: number[] = [];

  // Top of page (always)
  placements.push(EzoicPlacements.TOP_OF_PAGE);

  // Under page title
  if (options.hasTitle) {
    placements.push(EzoicPlacements.UNDER_PAGE_TITLE);
  }

  // Content-based placements
  if (options.hasContent && options.paragraphCount) {
    placements.push(...getContentAdPlacements(options.paragraphCount));
  }

  // Sidebar placements
  if (options.hasSidebar) {
    placements.push(EzoicPlacements.SIDEBAR, EzoicPlacements.SIDEBAR_MIDDLE);

    if (options.includeDesktopOnly) {
      placements.push(
        EzoicPlacements.SIDEBAR_BOTTOM,
        EzoicPlacements.SIDEBAR_FLOATING_1,
        EzoicPlacements.SIDEBAR_FLOATING_2
      );
    }
  }

  // Bottom of page (always)
  placements.push(EzoicPlacements.BOTTOM_OF_PAGE, EzoicPlacements.BOTTOM_OF_PAGE_ALT);

  return placements;
}
