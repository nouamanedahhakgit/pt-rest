globalThis.process ??= {}; globalThis.process.env ??= {};
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
export { renderers } from '../renderers.mjs';

const prerender = false;
function escapeXml(unsafe) {
  return unsafe.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case "&":
        return "&amp;";
      case "'":
        return "&apos;";
      case '"':
        return "&quot;";
      default:
        return c;
    }
  });
}
function formatDate(date) {
  return new Date(date).toISOString().split("T")[0];
}
const GET = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime?.env?.DB || {});
    const siteDomain = await db.getSetting("site_domain") || "cheftaling.com";
    const fullDomain = `https://${siteDomain}`;
    const [recipes, categories, authors, pages] = await Promise.all([
      db.getRecipes(),
      db.getCategories(),
      db.getAuthors(),
      db.getAllPages()
    ]);
    const urls = [];
    urls.push(`
  <url>
    <loc>${fullDomain}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>`);
    urls.push(`
  <url>
    <loc>${fullDomain}/recipes/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>`);
    for (const recipe of recipes) {
      urls.push(`
  <url>
    <loc>${fullDomain}/${escapeXml(recipe.slug)}/</loc>
    <lastmod>${formatDate(recipe.updated_at || recipe.created_at)}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    }
    for (const category of categories) {
      urls.push(`
  <url>
    <loc>${fullDomain}/category/${escapeXml(category.slug)}/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`);
    }
    for (const author of authors) {
      urls.push(`
  <url>
    <loc>${fullDomain}/author/${escapeXml(author.slug)}/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>`);
    }
    for (const page of pages) {
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
${urls.join("")}
</urlset>`;
    return new Response(sitemap, {
      status: 200,
      headers: {
        "Content-Type": "application/xml",
        "Cache-Control": "public, max-age=3600"
        // Cache for 1 hour
      }
    });
  } catch (error) {
    console.error("Error generating sitemap:", error);
    return new Response("Error generating sitemap", { status: 500 });
  }
};

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  GET,
  prerender
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
