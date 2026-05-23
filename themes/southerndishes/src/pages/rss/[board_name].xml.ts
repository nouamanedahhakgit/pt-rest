import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

export const prerender = false;

// Helper function to escape XML special characters
function escapeXml(unsafe: string): string {
  if (!unsafe) return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// Helper function to get correct MIME type from image URL
function getImageMimeType(url: string): string {
  if (!url) return 'image/jpeg';

  try {
    // Try to parse as URL to get pathname
    const urlObj = new URL(url);
    const pathname = urlObj.pathname.toLowerCase();

    if (pathname.endsWith('.png')) return 'image/png';
    if (pathname.endsWith('.webp')) return 'image/webp';
    if (pathname.endsWith('.gif')) return 'image/gif';
    if (pathname.endsWith('.jpg') || pathname.endsWith('.jpeg')) return 'image/jpeg';

    return 'image/jpeg'; // default
  } catch {
    // Fallback: check string endings if URL parsing fails
    const lowerUrl = url.toLowerCase();
    if (lowerUrl.endsWith('.png')) return 'image/png';
    if (lowerUrl.endsWith('.webp')) return 'image/webp';
    if (lowerUrl.endsWith('.gif')) return 'image/gif';
    if (lowerUrl.endsWith('.jpg') || lowerUrl.endsWith('.jpeg')) return 'image/jpeg';

    return 'image/jpeg'; // default
  }
}

export async function getStaticPaths() {
  return [];
}

export const GET: APIRoute = async ({ params, locals }) => {
  const { board_name } = params;

  if (!board_name) {
    return new Response('Board name is required', { status: 400 });
  }

  const db = new DatabaseService(locals.runtime?.env?.DB || {} as any);

  try {
    // Get site settings
    const settings = await db.getAllSettings();
    const siteName = settings.site_name || 'ChefTaling';
    const siteDomain = settings.site_domain || 'cheftaling.com';
    const siteDescription = settings.site_description || 'Delicious recipes and cooking inspiration';
    const siteUrl = `https://${siteDomain}`;

    // Get recipes for this board (limited to 25 for Pinterest)
    const recipes = await db.getRecipesByBoardName(board_name, 25);

    // Generate RSS feed from database recipes
    const rssItems = recipes.map((recipe) => {
      const recipeUrl = `${siteUrl}/${recipe.slug}/`;
      const pubDate = new Date(recipe.updated_at).toUTCString();

      // Parse recipe data for description
      let recipeData;
      try {
        recipeData = JSON.parse(recipe.recipe_json);
      } catch (e) {
        recipeData = { summary: '' };
      }

      const description = recipe.pin_description || recipeData.summary || recipe.title;
      const imageUrl = recipe.pin_image || recipe.featured_image;

      // Get correct MIME type before escaping
      const imageMimeType = imageUrl ? getImageMimeType(imageUrl) : 'image/jpeg';
      // Clean and escape image URL
      const cleanImageUrl = imageUrl ? escapeXml(imageUrl) : '';

      return `    <item>
      <title><![CDATA[${recipe.title}]]></title>
      <link>${escapeXml(recipeUrl)}</link>
      <guid isPermaLink="true">${escapeXml(recipeUrl)}</guid>
      <pubDate>${pubDate}</pubDate>
      <description><![CDATA[${description}]]></description>
      ${cleanImageUrl ? `<media:content url="${cleanImageUrl}" type="${imageMimeType}" medium="image" width="1200" height="800"/>` : ''}
      ${cleanImageUrl ? `<enclosure url="${cleanImageUrl}" type="${imageMimeType}" length="0"/>` : ''}
      ${recipe.category ? `<category><![CDATA[${recipe.category.name}]]></category>` : ''}
    </item>`;
    }).join('\n');

    // Calculate lastBuildDate from newest recipe (stable, not "now")
    const newestDate = recipes.length > 0
      ? new Date(Math.max(...recipes.map(r => new Date(r.updated_at).getTime()))).toUTCString()
      : new Date().toUTCString();

    const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>${escapeXml(siteName)} - ${escapeXml(board_name)}</title>
    <link>${escapeXml(siteUrl)}</link>
    <description>${escapeXml(siteDescription)} - ${escapeXml(board_name)} Board</description>
    <language>en-us</language>
    <lastBuildDate>${newestDate}</lastBuildDate>
    <atom:link href="${escapeXml(siteUrl)}/rss/${escapeXml(board_name)}.xml" rel="self" type="application/rss+xml"/>
${rssItems}
  </channel>
</rss>`;

    return new Response(rssXml, {
      headers: {
        'Content-Type': 'application/xml; charset=utf-8',
        'Cache-Control': 'public, max-age=300'  // 5 minutes instead of 1 hour
      }
    });
  } catch (error) {
    console.error('Error generating RSS feed:', error);
    return new Response('Error generating RSS feed', { status: 500 });
  }
};
