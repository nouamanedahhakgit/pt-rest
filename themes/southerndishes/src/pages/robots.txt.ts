import type { APIRoute } from 'astro';
import { DatabaseService } from '../lib/database';

export const prerender = false;

export const GET: APIRoute = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime?.env?.DB || {} as any);

    // Get site domain from database (without https://)
    const siteDomain = await db.getSetting('site_domain') || 'cheftaling.com';

    const robotsTxt = `# robots.txt for ${siteDomain}

User-agent: *
Allow: /

# Sitemap
Sitemap: https://${siteDomain}/sitemap.xml

# Disallow print pages from indexing
Disallow: /print/
`;

    return new Response(robotsTxt, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain',
        'Cache-Control': 'public, max-age=86400' // Cache for 24 hours
      }
    });
  } catch (error) {
    console.error('Error generating robots.txt:', error);
    // Return a basic fallback robots.txt
    const fallback = `User-agent: *
Allow: /

Sitemap: https://cheftaling.com/sitemap.xml
`;
    return new Response(fallback, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain'
      }
    });
  }
};
