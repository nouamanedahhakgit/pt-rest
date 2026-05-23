import type { APIRoute } from 'astro';
import { DatabaseService } from '../lib/database';

export const prerender = false;

function escapeXml(unsafe: string): string {
  return unsafe.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case "'": return '&apos;';
      case '"': return '&quot;';
      default: return c;
    }
  });
}

function formatDate(date: string): string {
  return new Date(date).toISOString().split('T')[0];
}

export const GET: APIRoute = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime?.env?.DB || {} as any);

    // Get site domain from database (without https://)
    const siteDomain = await db.getSetting('site_domain') || 'cheftaling.com';
    const fullDomain = `https://${siteDomain}`;

    // Fetch all data
    const [recipes, categories, authors, pages] = await Promise.all([
      db.getRecipes(),
      db.getCategories(),
      db.getAuthors(),
      db.getAllPages()
    ]);

    // Build sitemap XML
    const urls: string[] = [];

    // Homepage
    urls.push(`
  <url>
    <loc>${fullDomain}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>`);

    // Recipes page
    urls.push(`
  <url>
    <loc>${fullDomain}/recipes/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>`);

    // Recipe pages
    for (const recipe of recipes) {
      urls.push(`
  <url>
    <loc>${fullDomain}/${escapeXml(recipe.slug)}/</loc>
    <lastmod>${formatDate(recipe.updated_at || recipe.created_at)}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    }

    // Category pages
    for (const category of categories) {
      urls.push(`
  <url>
    <loc>${fullDomain}/category/${escapeXml(category.slug)}/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`);
    }

    // Author pages
    for (const author of authors) {
      urls.push(`
  <url>
    <loc>${fullDomain}/author/${escapeXml(author.slug)}/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>`);
    }

    // Static pages (About, Privacy, etc.)
    for (const page of pages) {
      // All pages now have direct routes at root level
      urls.push(`
  <url>
    <loc>${fullDomain}/${escapeXml(page.slug)}/</loc>
    <lastmod>${formatDate(page.updated_at || page.created_at)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>`);
    }

    const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('')}
</urlset>`;

    return new Response(sitemap, {
      status: 200,
      headers: {
        'Content-Type': 'application/xml',
        'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
      }
    });
  } catch (error) {
    console.error('Error generating sitemap:', error);
    return new Response('Error generating sitemap', { status: 500 });
  }
};
