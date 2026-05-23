globalThis.process ??= {}; globalThis.process.env ??= {};
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
export { renderers } from '../renderers.mjs';

const prerender = false;
const GET = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime?.env?.DB || {});
    const siteDomain = await db.getSetting("site_domain") || "cheftaling.com";
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
        "Content-Type": "text/plain",
        "Cache-Control": "public, max-age=86400"
        // Cache for 24 hours
      }
    });
  } catch (error) {
    console.error("Error generating robots.txt:", error);
    const fallback = `User-agent: *
Allow: /

Sitemap: https://cheftaling.com/sitemap.xml
`;
    return new Response(fallback, {
      status: 200,
      headers: {
        "Content-Type": "text/plain"
      }
    });
  }
};

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  GET,
  prerender
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
