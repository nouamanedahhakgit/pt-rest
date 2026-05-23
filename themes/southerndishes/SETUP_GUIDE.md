# Complete Setup Guide for New Recipe Projects

This guide will help you replicate all the features from cheftaling/momdishmagic projects to a new project.

## 📋 Table of Contents

1. [Database Migration](#1-database-migration)
2. [RSS Feed System](#2-rss-feed-system)
3. [Template Variables for Policy Pages](#3-template-variables-for-policy-pages)
4. [API Updates](#4-api-updates)
5. [Testing](#5-testing)

---

## 1. Database Migration

### Run the Migration

```bash
# Local
wrangler d1 execute YOUR_DB_NAME --local --file=./db/migrations/COMPLETE_SETUP_MIGRATION.sql

# Production
wrangler d1 execute YOUR_DB_NAME --remote --file=./db/migrations/COMPLETE_SETUP_MIGRATION.sql
```

### What It Does
- Adds `board_name` TEXT column to `recipes` table
- Allows organizing recipes into Pinterest boards or RSS feed categories

---

## 2. RSS Feed System

### Step 1: Update TypeScript Types

**File: `src/types/recipe.ts`**

Add `board_name` to the Recipe interface:

```typescript
export interface Recipe {
  id: number;
  title: string;
  pin_image?: string;
  pin_description?: string;
  board_name?: string;  // ← ADD THIS LINE
  slug: string;
  article_content: string;
  // ... rest of interface
}
```

### Step 2: Add Database Methods

**File: `src/lib/database.ts`**

Add these methods before the `// Settings methods` comment:

```typescript
// Board name methods
async getRecipesByBoardName(boardName: string, limit?: number, offset?: number): Promise<Recipe[]> {
  let query = `
    SELECT r.*, c.name as category_name, c.slug as category_slug
    FROM recipes r
    LEFT JOIN categories c ON r.category_id = c.id
    WHERE r.board_name = ? AND r.status = 'published'
    ORDER BY r.created_at DESC
  `;

  if (limit) {
    query += ` LIMIT ${limit}`;
    if (offset) {
      query += ` OFFSET ${offset}`;
    }
  }

  const result = await this.db.prepare(query).bind(boardName).all<Recipe>();
  return result.results || [];
}

async getRecipeCountByBoardName(boardName: string): Promise<number> {
  const result = await this.db
    .prepare(`
      SELECT COUNT(*) as count
      FROM recipes
      WHERE board_name = ? AND status = 'published'
    `)
    .bind(boardName)
    .first<{ count: number }>();

  return result?.count || 0;
}

async getAllBoardNames(): Promise<string[]> {
  const result = await this.db
    .prepare(`
      SELECT DISTINCT board_name
      FROM recipes
      WHERE board_name IS NOT NULL AND board_name != '' AND status = 'published'
      ORDER BY board_name ASC
    `)
    .all<{ board_name: string }>();

  return (result.results || []).map(r => r.board_name);
}
```

### Step 3: Create RSS Feed Routes

**File: `src/pages/rss/[board_name].xml.ts`**

```typescript
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

    // Get recipes for this board
    const recipes = await db.getRecipesByBoardName(board_name);

    if (!recipes || recipes.length === 0) {
      return new Response(
        `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteName)} - ${escapeXml(board_name)}</title>
    <link>${escapeXml(siteUrl)}/rss/${escapeXml(board_name)}.xml</link>
    <description>No recipes found for board: ${escapeXml(board_name)}</description>
    <language>en-us</language>
  </channel>
</rss>`,
        {
          headers: {
            'Content-Type': 'application/xml; charset=utf-8',
            'Cache-Control': 'public, max-age=300'  // 5 minutes
          }
        }
      );
    }

    // Generate RSS feed
    const rssItems = recipes.map((recipe) => {
      const recipeUrl = `${siteUrl}/${recipe.slug}/`;
      const pubDate = new Date(recipe.created_at).toUTCString();

      // Parse recipe data for description
      let recipeData;
      try {
        recipeData = JSON.parse(recipe.recipe_json);
      } catch (e) {
        recipeData = { summary: '' };
      }

      const description = recipe.pin_description || recipeData.summary || recipe.title;
      const imageUrl = recipe.pin_image || recipe.featured_image;

      // Clean and escape image URL
      const cleanImageUrl = imageUrl ? escapeXml(imageUrl) : '';

      return `    <item>
      <title><![CDATA[${recipe.title}]]></title>
      <link>${escapeXml(recipeUrl)}</link>
      <guid isPermaLink="true">${escapeXml(recipeUrl)}</guid>
      <pubDate>${pubDate}</pubDate>
      <description><![CDATA[${description}]]></description>
      ${cleanImageUrl ? `<enclosure url="${cleanImageUrl}" type="image/jpeg"/>` : ''}
      ${recipe.category ? `<category><![CDATA[${recipe.category.name}]]></category>` : ''}
    </item>`;
    }).join('\n');

    const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${escapeXml(siteName)} - ${escapeXml(board_name)}</title>
    <link>${escapeXml(siteUrl)}</link>
    <description>${escapeXml(siteDescription)} - ${escapeXml(board_name)} Board</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${escapeXml(siteUrl)}/rss/${escapeXml(board_name)}.xml" rel="self" type="application/rss+xml"/>
${rssItems}
  </channel>
</rss>`;

    return new Response(rssXml, {
      headers: {
        'Content-Type': 'application/xml; charset=utf-8',
        'Cache-Control': 'public, max-age=300'  // 5 minutes
      }
    });
  } catch (error) {
    console.error('Error generating RSS feed:', error);
    return new Response('Error generating RSS feed', { status: 500 });
  }
};
```

**File: `src/pages/rss/index.xml.ts`**

```typescript
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
```

---

## 3. Template Variables for Policy Pages

### Step 1: Add Utility Function

**File: `src/lib/utils.ts`**

Add this function at the end of the file:

```typescript
/**
 * Replace template variables in content with settings values
 * Supports: {{site_name}}, {{site_domain}}, {{contact_email}}
 */
export function replaceTemplateVariables(
  content: string,
  settings: Record<string, string>
): string {
  if (!content) return '';

  let result = content;

  // Replace {{site_name}}
  if (settings.site_name) {
    result = result.replace(/\{\{site_name\}\}/g, settings.site_name);
  }

  // Replace {{site_domain}}
  if (settings.site_domain) {
    result = result.replace(/\{\{site_domain\}\}/g, settings.site_domain);
  }

  // Replace {{contact_email}}
  if (settings.contact_email) {
    result = result.replace(/\{\{contact_email\}\}/g, settings.contact_email);
  }

  return result;
}
```

### Step 2: Update Policy Pages

For each policy page (`privacy-policy.astro`, `terms-of-use.astro`, `disclaimer.astro`, `gdpr-policy.astro`, `cookie-policy.astro`, `copyright-policy.astro`):

**Add import:**
```typescript
import { replaceTemplateVariables } from '../lib/utils';
```

**Add processing before the `---` separator:**
```typescript
// Replace template variables in content
const processedContent = replaceTemplateVariables(page.content, settings);
```

**Update the Fragment:**
```html
<!-- Change from: -->
<Fragment set:html={page.content} />

<!-- To: -->
<Fragment set:html={processedContent} />
```

### Step 3: Use Variables in Content

Now you can use these in your database page content:

```html
<p>Welcome to {{site_name}}!</p>
<p>Visit us at {{site_domain}}</p>
<p>Contact: {{contact_email}}</p>
```

---

## 4. API Updates

### Update API Interface

**File: `src/pages/api/recipes.ts`**

**Update the interface:**
```typescript
interface RecipeInsertBody {
  title: string;
  pin_image?: string | null;
  pin_description?: string | null;
  board_name?: string | null;  // ← ADD THIS LINE
  slug: string;
  article_content: string;
  // ... rest
}
```

**Update PUT handler (add in the update fields section):**
```typescript
if (body.board_name !== undefined) {
  updateFields.push("board_name = ?");
  values.push(body.board_name);
}
```

**Update POST handler INSERT query:**
```typescript
// Change from:
`INSERT INTO recipes (
  title, pin_image, pin_description, slug,
  article_content, featured_image, recipe_json,
  category_id, status, author_id, created_at
) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)`

// To:
`INSERT INTO recipes (
  title, pin_image, pin_description, board_name, slug,
  article_content, featured_image, recipe_json,
  category_id, status, author_id, created_at
) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)`

// And update .bind():
.bind(
  body.title,
  body.pin_image ?? null,
  body.pin_description ?? null,
  body.board_name ?? null,  // ← ADD THIS LINE
  finalSlug,
  // ... rest
)
```

---

## 5. Testing

### Test Database Migration
```bash
# Check if column was added
wrangler d1 execute YOUR_DB_NAME --local --command="PRAGMA table_info(recipes);"
```

### Test RSS Feeds
```bash
# Add board name to a recipe
wrangler d1 execute YOUR_DB_NAME --local --command="UPDATE recipes SET board_name = 'test-board' WHERE id = 1;"

# Visit in browser
http://localhost:4321/rss/test-board.xml
http://localhost:4321/rss/
```

### Test Template Variables
```sql
-- Update a policy page content
UPDATE pages
SET content = '<p>Welcome to {{site_name}}! Contact: {{contact_email}}</p>'
WHERE slug = 'privacy-policy';
```

Visit: `http://localhost:4321/privacy-policy/`

### Test API
```bash
# Create recipe with board_name
curl -X POST http://localhost:4321/api/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Recipe",
    "slug": "test-recipe",
    "board_name": "my-board",
    "article_content": "<p>Test</p>",
    "featured_image": "image.jpg",
    "recipe_json": {"name": "Test"},
    "author_id": 1
  }'
```

---

## 🎉 Done!

Your new project now has:
- ✅ RSS feeds by board name
- ✅ Dynamic template variables in policy pages
- ✅ API support for board names
- ✅ 5-minute RSS feed caching

## 📚 Additional Resources

- **RSS Feeds**: `/rss/` to see all available feeds
- **Template Variables**: Use `{{site_name}}`, `{{site_domain}}`, `{{contact_email}}` in page content
- **Board Names**: Set unique board names per recipe for organized RSS feeds

---

**Questions?** Check the existing cheftaling or momdishmagic projects for reference implementations.
