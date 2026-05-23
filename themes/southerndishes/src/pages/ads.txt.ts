import type { APIRoute } from 'astro';
import { DatabaseService } from '../lib/database';

export const GET: APIRoute = async ({ locals }) => {
  try {
    // Initialize database service
    const db = new DatabaseService(locals.runtime?.env?.DB || {} as any);

    // Check if database is available
    if (!locals.runtime?.env?.DB) {
      return new Response('Database not available', {
        status: 500,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }

    // Get site settings from database
    const settings = await db.getAllSettings();
    const siteDomain = settings.site_domain;
    const adProvider = settings.ad_provider || 'ezoic';

    if (!siteDomain) {
      return new Response('Site domain not configured', {
        status: 404,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }

    let adsUrl: string | null = null;

    // Determine which ads.txt URL to fetch based on provider
    if (adProvider === 'hbagency') {
      // HBAgency ads.txt URL
      const hbAgencyAdsTxtUrl = settings.hbagency_ads_txt_url;
      if (hbAgencyAdsTxtUrl) {
        adsUrl = hbAgencyAdsTxtUrl;
      }
    } else if (adProvider === 'ezoic') {
      // Ezoic ads.txt URL (via adstxtmanager.com)
      adsUrl = `https://srv.adstxtmanager.com/19390/${siteDomain}`;
    }

    // If no ads URL configured or provider is 'none', return empty ads.txt
    if (!adsUrl || adProvider === 'none') {
      return new Response('# No ads configured for this site\n', {
        headers: {
          'Content-Type': 'text/plain',
          'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
        },
      });
    }

    // Fetch ads.txt from the configured URL
    try {
      const response = await fetch(adsUrl);

      if (!response.ok) {
        throw new Error(`Failed to fetch ads.txt: ${response.status}`);
      }

      const text = await response.text();

      return new Response(text, {
        headers: {
          'Content-Type': 'text/plain',
          'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
        },
      });
    } catch (fetchError) {
      console.error('Error fetching ads.txt:', fetchError);

      // Return a fallback or empty ads.txt if fetch fails
      return new Response(`# ads.txt file could not be loaded from ${adProvider}\n`, {
        status: 503,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }
  } catch (error) {
    console.error('Error in ads.txt endpoint:', error);

    return new Response('Internal server error', {
      status: 500,
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  }
};

export const prerender = false;
