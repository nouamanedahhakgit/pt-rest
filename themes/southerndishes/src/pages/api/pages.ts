import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

interface PageBody {
  title: string;
  slug: string;
  content: string;
  meta_description?: string;
  status?: string;
}

// ───────────────── GET /api/pages ─────────────────
// Fetch all pages or a specific page by slug
// Protected with Authorization: Bearer <API_TOKEN>

export const GET: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const apiToken = runtimeEnv.API_TOKEN as string | undefined;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const db = new DatabaseService(runtimeEnv.DB);
    const searchParams = new URL(url).searchParams;
    const slug = searchParams.get('slug');
    const status = searchParams.get('status');
    const limit = parseInt(searchParams.get('limit') || '50');
    const offset = parseInt(searchParams.get('offset') || '0');

    // If slug is provided, return single page
    if (slug) {
      const page = await db.getPageBySlug(slug);

      if (!page) {
        return new Response(
          JSON.stringify({
            success: false,
            error: `Page with slug '${slug}' not found`,
          }),
          {
            status: 404,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      return new Response(
        JSON.stringify({
          success: true,
          data: page,
        }),
        {
          headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=300',
          },
        }
      );
    }

    // Build query based on filters
    let query = 'SELECT * FROM pages';
    const conditions: string[] = [];
    const bindings: any[] = [];

    if (status) {
      conditions.push('status = ?');
      bindings.push(status);
    }

    if (conditions.length > 0) {
      query += ' WHERE ' + conditions.join(' AND ');
    }

    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
    bindings.push(limit, offset);

    // Execute query
    const dbRaw = runtimeEnv.DB;
    let preparedStatement = dbRaw.prepare(query);

    // Bind parameters
    if (bindings.length > 0) {
      preparedStatement = preparedStatement.bind(...bindings);
    }

    const { results } = await preparedStatement.all();

    // Get total count for pagination
    let countQuery = 'SELECT COUNT(*) as total FROM pages';
    if (conditions.length > 0) {
      countQuery += ' WHERE ' + conditions.slice(0, -2).join(' AND ');
    }

    const countBindings = bindings.slice(0, -2);
    let countStatement = dbRaw.prepare(countQuery);
    if (countBindings.length > 0) {
      countStatement = countStatement.bind(...countBindings);
    }
    const { results: countResults } = await countStatement.all();
    const total = (countResults[0] as any).total || 0;

    return new Response(
      JSON.stringify({
        success: true,
        data: results,
        pagination: {
          total,
          limit,
          offset,
          hasMore: offset + results.length < total,
        },
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=300',
        },
      }
    );
  } catch (error) {
    console.error('Error fetching pages:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch pages',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── POST /api/pages ─────────────────
// Create a new page with auto-slug handling
// Protected with Authorization: Bearer <API_TOKEN>

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const body = (await request.json()) as PageBody;

    // Validate required fields
    if (!body.title || !body.slug || !body.content) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Missing required fields (title, slug, content)',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    let finalSlug = body.slug;

    // ---- AUTO SLUG INCREMENTING ----
    const slugExists = async (slug: string) => {
      const { results } = await db
        .prepare('SELECT id FROM pages WHERE slug = ?1')
        .bind(slug)
        .all();
      return results.length > 0;
    };

    // If slug exists, append -1, -2, -3...
    if (await slugExists(finalSlug)) {
      let counter = 1;
      while (await slugExists(`${finalSlug}-${counter}`)) {
        counter++;
      }
      finalSlug = `${finalSlug}-${counter}`;
    }

    const status = body.status || 'published';

    // Insert page
    const insert = await db
      .prepare(
        `INSERT INTO pages (
          title, slug, content, meta_description, status
        ) VALUES (?1, ?2, ?3, ?4, ?5)`
      )
      .bind(
        body.title,
        finalSlug,
        body.content,
        body.meta_description || null,
        status
      )
      .run();

    const newId = insert.meta.last_row_id;

    // Fetch newly created page
    const { results } = await db
      .prepare('SELECT * FROM pages WHERE id = ?1')
      .bind(newId)
      .all();

    // Get site domain from settings for full URL
    const dbService = new DatabaseService(db);
    const settings = await dbService.getAllSettings();
    const siteDomain = settings.site_domain || 'momdishmagic.com';
    const fullUrl = `https://${siteDomain}/page/${finalSlug}/`;

    return new Response(
      JSON.stringify({
        success: true,
        data: results[0],
        generated_slug: finalSlug,
        url: fullUrl,
      }),
      {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error creating page:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to create page',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── PUT /api/pages ─────────────────
// Update an existing page
// Protected with Authorization: Bearer <API_TOKEN>

export const PUT: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const body = (await request.json()) as Partial<PageBody> & { id: number };

    // ID is required for updates
    if (!body.id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Page ID is required for updates',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Check if page exists
    const { results: existing } = await db
      .prepare('SELECT * FROM pages WHERE id = ?1')
      .bind(body.id)
      .all();

    if (existing.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Page not found',
        }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Build update query dynamically based on provided fields
    const updateFields: string[] = [];
    const values: any[] = [];

    if (body.title !== undefined) {
      updateFields.push('title = ?');
      values.push(body.title);
    }
    if (body.slug !== undefined) {
      updateFields.push('slug = ?');
      values.push(body.slug);
    }
    if (body.content !== undefined) {
      updateFields.push('content = ?');
      values.push(body.content);
    }
    if (body.meta_description !== undefined) {
      updateFields.push('meta_description = ?');
      values.push(body.meta_description);
    }
    if (body.status !== undefined) {
      updateFields.push('status = ?');
      values.push(body.status);
    }

    if (updateFields.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'No fields to update',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Add updated_at timestamp
    updateFields.push('updated_at = CURRENT_TIMESTAMP');

    // Add ID as the last parameter
    values.push(body.id);

    // Execute update
    const updateQuery = `UPDATE pages SET ${updateFields.join(', ')} WHERE id = ?${values.length}`;
    await db.prepare(updateQuery).bind(...values).run();

    // Fetch updated page
    const { results } = await db
      .prepare('SELECT * FROM pages WHERE id = ?1')
      .bind(body.id)
      .all();

    return new Response(
      JSON.stringify({
        success: true,
        data: results[0],
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error updating page:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to update page',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── DELETE /api/pages ─────────────────
// Delete a page by ID
// Protected with Authorization: Bearer <API_TOKEN>

export const DELETE: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const searchParams = new URL(url).searchParams;
    const id = searchParams.get('id');

    if (!id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Page ID is required',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Check if page exists
    const { results: existing } = await db
      .prepare('SELECT * FROM pages WHERE id = ?1')
      .bind(parseInt(id))
      .all();

    if (existing.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Page not found',
        }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Delete page
    await db.prepare('DELETE FROM pages WHERE id = ?1').bind(parseInt(id)).run();

    return new Response(
      JSON.stringify({
        success: true,
        message: `Page '${(existing[0] as any).title}' deleted successfully`,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error deleting page:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to delete page',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};
