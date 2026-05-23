import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

export const prerender = false;

export const GET: APIRoute = async ({ locals }) => {
  const db = new DatabaseService(locals.runtime?.env?.DB || {} as any);

  try {
    // Get site settings
    const settings = await db.getAllSettings();
    const siteName = settings.site_name || 'ChefTaling';
    const siteDomain = settings.site_domain || 'cheftaling.com';
    const siteDescription = settings.site_description || 'Delicious recipes and cooking inspiration';
    const siteUrl = `https://${siteDomain}`;

    // Get all board names
    const boardNames = await db.getAllBoardNames();

    // Generate list of RSS feeds
    const feedList = boardNames.map(boardName => {
      const feedUrl = `${siteUrl}/rss/${encodeURIComponent(boardName)}.xml`;
      return `      <li><a href="${feedUrl}">${boardName}</a> - <code>${feedUrl}</code></li>`;
    }).join('\n');

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RSS Feeds - ${siteName}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      max-width: 900px;
      margin: 50px auto;
      padding: 20px;
      line-height: 1.6;
      color: #333;
    }
    h1 {
      color: #2ec9ad;
      border-bottom: 3px solid #2ec9ad;
      padding-bottom: 10px;
    }
    h2 {
      color: #1b7d68;
      margin-top: 30px;
    }
    ul {
      list-style: none;
      padding: 0;
    }
    li {
      background: #f9fafb;
      margin: 10px 0;
      padding: 15px;
      border-radius: 8px;
      border-left: 4px solid #2ec9ad;
    }
    a {
      color: #2ec9ad;
      text-decoration: none;
      font-weight: 600;
      font-size: 1.1em;
    }
    a:hover {
      color: #24a38a;
      text-decoration: underline;
    }
    code {
      background: #e5e7eb;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
      color: #6b7280;
    }
    .info {
      background: #e8fdf9;
      padding: 15px;
      border-radius: 8px;
      border-left: 4px solid #3ae6c8;
      margin: 20px 0;
    }
    .count {
      color: #6b7280;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <h1>🍽️ ${siteName} RSS Feeds</h1>

  <div class="info">
    <p><strong>About:</strong> ${siteDescription}</p>
    <p class="count">Available RSS feeds: <strong>${boardNames.length}</strong></p>
  </div>

  <h2>📋 Available Board Feeds</h2>
  ${boardNames.length > 0 ? `
  <ul>
${feedList}
  </ul>
  ` : '<p>No board feeds available yet. Add <code>board_name</code> to your recipes to create RSS feeds.</p>'}

  <h2>📖 How to Use</h2>
  <div class="info">
    <p>Each RSS feed contains recipes assigned to a specific board name. You can use these feeds with:</p>
    <ul style="list-style: disc; padding-left: 20px; background: none; border: none;">
      <li>Pinterest automation tools</li>
      <li>RSS readers</li>
      <li>Social media schedulers</li>
      <li>Email newsletter services</li>
    </ul>
  </div>

  <h2>🔗 Main Site RSS</h2>
  <ul>
    <li>
      <a href="${siteUrl}/sitemap.xml">Sitemap</a> - <code>${siteUrl}/sitemap.xml</code>
    </li>
  </ul>

  <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; text-align: center;">
    <p>&copy; ${new Date().getFullYear()} ${siteName}. All rights reserved.</p>
  </footer>
</body>
</html>`;

    return new Response(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  } catch (error) {
    console.error('Error generating RSS index:', error);
    return new Response('Error generating RSS index', { status: 500 });
  }
};
