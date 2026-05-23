import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

interface AuthorInsertBody {
  name: string;
  slug: string;
  title?: string | null;
  image_url?: string | null;
  showcase_image?: string | null;
  bio?: string | null;
}

// ───────────────── GET /api/authors ─────────────────
// List all authors with optional pagination
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

    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '50');
    const offset = (page - 1) * limit;

    // Get all authors (DatabaseService doesn't have pagination for authors yet)
    const allAuthors = await db.getAuthors();

    // Manual pagination
    const paginatedAuthors = allAuthors.slice(offset, offset + limit);

    return new Response(
      JSON.stringify({
        success: true,
        data: paginatedAuthors,
        pagination: {
          page,
          limit,
          total: allAuthors.length,
          hasMore: offset + limit < allAuthors.length,
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
    console.error('Error fetching authors:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch authors',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── POST /api/authors (AUTO SLUG HANDLING) ─────────────────
// Create new author with automatic slug incrementing

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get("Authorization");
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(JSON.stringify({
        success: false,
        error: "Unauthorized"
      }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }

    const body = (await request.json()) as AuthorInsertBody;

    // Required fields validation
    if (!body.name || !body.slug) {
      return new Response(JSON.stringify({
        success: false,
        error: "Missing required fields (name, slug)"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    let finalSlug = body.slug;

    // ---- AUTO SLUG INCREMENTING ----
    const slugExists = async (slug: string) => {
      const { results } = await db
        .prepare("SELECT id FROM authors WHERE slug = ?1")
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

    // Insert author
    const insert = await db
      .prepare(
        `INSERT INTO authors (name, slug, title, image_url, showcase_image, bio)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)`
      )
      .bind(
        body.name,
        finalSlug,
        body.title ?? null,
        body.image_url ?? null,
        body.showcase_image ?? null,
        body.bio ?? null
      )
      .run();

    const newId = insert.meta.last_row_id;

    // Fetch created author
    const { results } = await db
      .prepare("SELECT * FROM authors WHERE id = ?1")
      .bind(newId)
      .all();

    // Get site domain for full URL
    const dbService = new DatabaseService(db);
    const settings = await dbService.getAllSettings();
    const siteDomain = settings.site_domain || 'momdishmagic.com';
    const fullUrl = `https://${siteDomain}/author/${finalSlug}/`;

    return new Response(JSON.stringify({
      success: true,
      data: results[0],
      generated_slug: finalSlug,    // The slug that was used (with -1, -2 etc if needed)
      url: fullUrl                  // Full URL to the author page
    }), {
      status: 201,
      headers: { "Content-Type": "application/json" }
    });

  } catch (error: any) {
    console.error("Error creating author:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to create author"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};

// ───────────────── PUT /api/authors ─────────────────
// Update an existing author by ID

export const PUT: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get("Authorization");
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(JSON.stringify({
        success: false,
        error: "Unauthorized"
      }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }

    const body = (await request.json()) as Partial<AuthorInsertBody> & { id: number };

    // ID is required for updates
    if (!body.id) {
      return new Response(JSON.stringify({
        success: false,
        error: "Author ID is required for updates"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Check if author exists
    const { results: existing } = await db
      .prepare("SELECT * FROM authors WHERE id = ?1")
      .bind(body.id)
      .all();

    if (existing.length === 0) {
      return new Response(JSON.stringify({
        success: false,
        error: "Author not found"
      }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Build update query dynamically based on provided fields
    const updateFields: string[] = [];
    const values: any[] = [];

    if (body.name !== undefined) {
      updateFields.push("name = ?");
      values.push(body.name);
    }
    if (body.slug !== undefined) {
      updateFields.push("slug = ?");
      values.push(body.slug);
    }
    if (body.title !== undefined) {
      updateFields.push("title = ?");
      values.push(body.title);
    }
    if (body.image_url !== undefined) {
      updateFields.push("image_url = ?");
      values.push(body.image_url);
    }
    if (body.showcase_image !== undefined) {
      updateFields.push("showcase_image = ?");
      values.push(body.showcase_image);
    }
    if (body.bio !== undefined) {
      updateFields.push("bio = ?");
      values.push(body.bio);
    }

    if (updateFields.length === 0) {
      return new Response(JSON.stringify({
        success: false,
        error: "No fields to update"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Always update the updated_at timestamp
    updateFields.push("updated_at = CURRENT_TIMESTAMP");

    // Add ID as the last parameter
    values.push(body.id);

    // Execute update
    const updateQuery = `UPDATE authors SET ${updateFields.join(", ")} WHERE id = ?${values.length}`;
    await db.prepare(updateQuery).bind(...values).run();

    // Fetch updated author
    const { results } = await db
      .prepare("SELECT * FROM authors WHERE id = ?1")
      .bind(body.id)
      .all();

    return new Response(JSON.stringify({
      success: true,
      data: results[0]
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });

  } catch (error: any) {
    console.error("Error updating author:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to update author"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};

// ───────────────── DELETE /api/authors ─────────────────
// Delete an author by ID

export const DELETE: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get("Authorization");
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(JSON.stringify({
        success: false,
        error: "Unauthorized"
      }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }

    const body = (await request.json()) as { id: number };

    // ID is required
    if (!body.id) {
      return new Response(JSON.stringify({
        success: false,
        error: "Author ID is required"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Check if author exists
    const { results: existing } = await db
      .prepare("SELECT * FROM authors WHERE id = ?1")
      .bind(body.id)
      .all();

    if (existing.length === 0) {
      return new Response(JSON.stringify({
        success: false,
        error: "Author not found"
      }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Check if author has recipes (optional - you may want to prevent deletion)
    const { results: recipes } = await db
      .prepare("SELECT COUNT(*) as count FROM recipes WHERE author_id = ?1")
      .bind(body.id)
      .all();

    const recipeCount = (recipes[0] as any)?.count || 0;

    if (recipeCount > 0) {
      return new Response(JSON.stringify({
        success: false,
        error: `Cannot delete author. This author has ${recipeCount} recipe(s) associated. Please reassign or delete those recipes first.`
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Delete author
    await db
      .prepare("DELETE FROM authors WHERE id = ?1")
      .bind(body.id)
      .run();

    return new Response(JSON.stringify({
      success: true,
      message: "Author deleted successfully"
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });

  } catch (error: any) {
    console.error("Error deleting author:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to delete author"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};
