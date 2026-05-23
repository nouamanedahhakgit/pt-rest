/**
 * Ezoic Dynamic Ad Management Utilities
 *
 * Use these functions when you add dynamic content features like:
 * - Infinite scroll
 * - Tab/accordion navigation
 * - AJAX content loading
 * - Client-side routing (SPA)
 *
 * Your site currently uses server-side rendering (SSR), so these aren't needed yet.
 * But if you add dynamic features, these utilities will help manage Ezoic ads properly.
 */

// Extend window object to include ezstandalone
declare global {
  interface Window {
    ezstandalone: {
      cmd: Array<() => void>;
      refresh: () => void;
      showAds: (...placementIds: number[]) => void;
      destroyPlaceholders: (...placementIds: number[]) => void;
      destroyAll: () => void;
      define: (placementId: number, slotName: string) => void;
    };
  }
}

/**
 * Initialize ezstandalone.cmd array if it doesn't exist
 * This ensures commands can be queued before Ezoic script loads
 */
function ensureEzoicCmd(): void {
  if (typeof window !== 'undefined' && !window.ezstandalone) {
    window.ezstandalone = {
      cmd: [],
      refresh: () => {},
      showAds: () => {},
      destroyPlaceholders: () => {},
      destroyAll: () => {},
      define: () => {}
    };
  }
}

/**
 * Refresh all Ezoic ads on the current page
 *
 * Use when: Content changes dynamically but placeholders remain the same
 *
 * Example: Tab switching where ads need to re-render
 * ```typescript
 * // User clicks a tab
 * tabButton.addEventListener('click', () => {
 *   showTabContent(tabId);
 *   EzoicDynamic.refreshAds();
 * });
 * ```
 */
export function refreshAds(): void {
  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.refresh();
  });
}

/**
 * Show ads for newly added placeholders
 *
 * Use when: You dynamically inject new content with ad placeholders
 *
 * Example: Infinite scroll loading new articles
 * ```typescript
 * // After appending new article with ads
 * const newContent = `
 *   <article>
 *     <h2>New Article</h2>
 *     <div id="ezoic-pub-ad-placeholder-104"></div>
 *     <p>Content...</p>
 *     <div id="ezoic-pub-ad-placeholder-105"></div>
 *   </article>
 * `;
 * container.insertAdjacentHTML('beforeend', newContent);
 * EzoicDynamic.showNewAds([104, 105]);
 * ```
 *
 * @param placementIds - Array of Ezoic placement IDs to show
 */
export function showNewAds(placementIds: number[]): void {
  if (!placementIds || placementIds.length === 0) {
    console.warn('EzoicDynamic.showNewAds: No placement IDs provided');
    return;
  }

  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.showAds(...placementIds);
  });
}

/**
 * Destroy specific ad placeholders before removing their content
 *
 * Use when: Removing DOM elements that contain ad placeholders
 *
 * Example: Closing a modal with ads
 * ```typescript
 * closeButton.addEventListener('click', () => {
 *   EzoicDynamic.destroyAds([106, 107]);
 *   modal.remove();
 * });
 * ```
 *
 * IMPORTANT: Always destroy ads BEFORE removing their DOM elements
 *
 * @param placementIds - Array of Ezoic placement IDs to destroy
 */
export function destroyAds(placementIds: number[]): void {
  if (!placementIds || placementIds.length === 0) {
    console.warn('EzoicDynamic.destroyAds: No placement IDs provided');
    return;
  }

  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.destroyPlaceholders(...placementIds);
  });
}

/**
 * Destroy all Ezoic ads on the page
 *
 * Use when: Complete page content replacement (rare)
 *
 * Example: SPA route change that replaces entire page content
 * ```typescript
 * router.beforeEach((to, from) => {
 *   EzoicDynamic.destroyAllAds();
 *   // Load new route content
 *   loadRoute(to);
 * });
 * ```
 *
 * WARNING: Use sparingly. Usually better to destroy specific placeholders.
 */
export function destroyAllAds(): void {
  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.destroyAll();
  });
}

/**
 * Destroy old ads and show new ones with the same IDs
 *
 * Use when: Reusing the same placeholder IDs for new content (like infinite scroll)
 *
 * Example: Infinite scroll that reuses placement IDs
 * ```typescript
 * function loadMoreArticles() {
 *   // Destroy old ads first
 *   EzoicDynamic.destroyAndShowAds([102, 103, 104]);
 *
 *   // Then add new content with same placeholder IDs
 *   const newContent = `
 *     <article>
 *       <div id="ezoic-pub-ad-placeholder-102"></div>
 *       <p>New content...</p>
 *       <div id="ezoic-pub-ad-placeholder-103"></div>
 *     </article>
 *   `;
 *   container.insertAdjacentHTML('beforeend', newContent);
 * }
 * ```
 *
 * IMPORTANT: Never have duplicate placeholder IDs on the same page
 *
 * @param placementIds - Array of placement IDs to destroy and recreate
 */
export function destroyAndShowAds(placementIds: number[]): void {
  if (!placementIds || placementIds.length === 0) {
    console.warn('EzoicDynamic.destroyAndShowAds: No placement IDs provided');
    return;
  }

  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.destroyPlaceholders(...placementIds);
    window.ezstandalone.showAds(...placementIds);
  });
}

/**
 * Show all ads on the page (without specific IDs)
 *
 * Use when: Initial page load or showing all available ad placeholders
 *
 * Example: After SPA route change with new page content
 * ```typescript
 * router.afterEach(() => {
 *   EzoicDynamic.showAllAds();
 * });
 * ```
 */
export function showAllAds(): void {
  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.showAds();
  });
}

/**
 * Define a custom ad placement programmatically
 *
 * Use when: Creating ad placeholders dynamically without hardcoded HTML
 *
 * Example: Programmatic ad placement
 * ```typescript
 * EzoicDynamic.defineAdPlacement(104, 'sidebar_ad_1');
 * ```
 *
 * @param placementId - Ezoic placement ID
 * @param slotName - Unique slot name for this placement
 */
export function defineAdPlacement(placementId: number, slotName: string): void {
  ensureEzoicCmd();
  window.ezstandalone.cmd.push(() => {
    window.ezstandalone.define(placementId, slotName);
  });
}

/**
 * Utility to check if Ezoic script has loaded
 *
 * Use when: You need to ensure Ezoic is ready before executing ad commands
 *
 * Example: Wait for Ezoic before showing ads
 * ```typescript
 * if (await EzoicDynamic.waitForEzoic(5000)) {
 *   EzoicDynamic.showNewAds([104, 105]);
 * } else {
 *   console.error('Ezoic script failed to load');
 * }
 * ```
 *
 * @param timeout - Maximum wait time in milliseconds (default: 10000)
 * @returns Promise that resolves to true if Ezoic loaded, false if timeout
 */
export function waitForEzoic(timeout: number = 10000): Promise<boolean> {
  return new Promise((resolve) => {
    const startTime = Date.now();

    const checkEzoic = () => {
      if (typeof window !== 'undefined' &&
          window.ezstandalone &&
          typeof window.ezstandalone.showAds === 'function') {
        resolve(true);
        return;
      }

      if (Date.now() - startTime >= timeout) {
        resolve(false);
        return;
      }

      setTimeout(checkEzoic, 100);
    };

    checkEzoic();
  });
}

// Export all functions as a namespace for convenience
export const EzoicDynamic = {
  refreshAds,
  showNewAds,
  destroyAds,
  destroyAllAds,
  destroyAndShowAds,
  showAllAds,
  defineAdPlacement,
  waitForEzoic
};

// Default export
export default EzoicDynamic;
