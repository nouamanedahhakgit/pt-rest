import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

type RecipeJson = Record<string, unknown>;

interface RecipeInsertBody {
  title: string;
  pin_image?: string | null;
  pin_description?: string | null;
  board_name?: string | null;
  slug: string;
  article_content: string;
  featured_image: string;
  recipe_json: RecipeJson;
  post_tag?: string | null;
  category_id?: number | null;
  status?: string;
  author_id: number;
  created_at?: string; // "YYYY-MM-DD HH:MM:SS"
  updated_at?: string; // "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
}

function formatDbDateTime(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return (
    `${date.getFullYear()}-` +
    `${pad(date.getMonth() + 1)}-` +
    `${pad(date.getDate())} ` +
    `${pad(date.getHours())}:` +
    `${pad(date.getMinutes())}:` +
    `${pad(date.getSeconds())}`
  );
}

// ───────────────── GET /api/recipes ─────────────────
// Now protected with Authorization: Bearer <API_TOKEN>

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

    // Your original logic
    const db = new DatabaseService(runtimeEnv.DB);
    const searchParams = new URL(url).searchParams;

    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '12');
    const category = searchParams.get('category');
    const search = searchParams.get('search');

    const offset = (page - 1) * limit;

    let recipes;

    if (search) {
      recipes = await db.searchRecipes(search, limit);
    } else if (category) {
      recipes = await db.getRecipesByCategory(category, limit, offset);
    } else {
      recipes = await db.getRecipes(limit, offset);
    }

    return new Response(
      JSON.stringify({
        success: true,
        data: recipes,
        pagination: {
          page,
          limit,
          hasMore: recipes.length === limit,
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
    console.error('Error fetching recipes:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch recipes',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── PUT /api/recipes/:id ─────────────────
// Update an existing recipe

export const PUT: APIRoute = async ({ request, locals, params }) => {
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

    const body = (await request.json()) as Partial<RecipeInsertBody> & { id: number };

    // ID is required for updates
    if (!body.id) {
      return new Response(JSON.stringify({
        success: false,
        error: "Recipe ID is required for updates"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Check if recipe exists
    const { results: existing } = await db
      .prepare("SELECT * FROM recipes WHERE id = ?1")
      .bind(body.id)
      .all();

    if (existing.length === 0) {
      return new Response(JSON.stringify({
        success: false,
        error: "Recipe not found"
      }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Build update query dynamically based on provided fields
    const updateFields: string[] = [];
    const values: any[] = [];

    if (body.title !== undefined) {
      updateFields.push("title = ?");
      values.push(body.title);
    }
    if (body.pin_image !== undefined) {
      updateFields.push("pin_image = ?");
      values.push(body.pin_image);
    }
    if (body.pin_description !== undefined) {
      updateFields.push("pin_description = ?");
      values.push(body.pin_description);
    }
    if (body.board_name !== undefined) {
      updateFields.push("board_name = ?");
      values.push(body.board_name);
    }
    if (body.slug !== undefined) {
      updateFields.push("slug = ?");
      values.push(body.slug);
    }
    if (body.article_content !== undefined) {
      updateFields.push("article_content = ?");
      values.push(body.article_content);
    }
    if (body.featured_image !== undefined) {
      updateFields.push("featured_image = ?");
      values.push(body.featured_image);
    }
    if (body.recipe_json !== undefined) {
      updateFields.push("recipe_json = ?");
      values.push(JSON.stringify(body.recipe_json));
    }
    if (body.post_tag !== undefined) {
      updateFields.push("post_tag = ?");
      values.push(body.post_tag);
    }
    if (body.category_id !== undefined) {
      updateFields.push("category_id = ?");
      values.push(body.category_id);
    }
    if (body.status !== undefined) {
      updateFields.push("status = ?");
      values.push(body.status);
    }
    if (body.author_id !== undefined) {
      updateFields.push("author_id = ?");
      values.push(body.author_id);
    }
    if (body.updated_at !== undefined) {
      updateFields.push("updated_at = ?");
      values.push(body.updated_at);
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

    // Add ID as the last parameter
    values.push(body.id);

    // Execute update
    const updateQuery = `UPDATE recipes SET ${updateFields.join(", ")} WHERE id = ?${values.length}`;
    await db.prepare(updateQuery).bind(...values).run();

    // Fetch updated recipe
    const { results } = await db
      .prepare("SELECT * FROM recipes WHERE id = ?1")
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
    console.error("Error updating recipe:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to update recipe"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};

// ───────────────── POST /api/recipes (AUTO SLUG HANDLING) ─────────────────

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

    const body = (await request.json()) as RecipeInsertBody;

    // Required fields
    if (
      !body.title ||
      !body.slug ||
      !body.article_content ||
      !body.featured_image ||
      !body.recipe_json ||
      body.author_id == null
    ) {
      return new Response(JSON.stringify({
        success: false,
        error: "Missing required fields (title, slug, article_content, featured_image, recipe_json, author_id)"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    let finalSlug = body.slug;

    // ---- AUTO SLUG INCREMENTING ----
    const slugExists = async (slug: string) => {
      const { results } = await db
        .prepare("SELECT id FROM recipes WHERE slug = ?1")
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

    const status = body.status ?? "draft";
    const categoryId = body.category_id ?? null;
    const createdAt = body.created_at ?? formatDbDateTime(new Date());

    // Insert recipe
    const insert = await db
      .prepare(
        `INSERT INTO recipes (
          title, pin_image, pin_description, board_name, slug,
          article_content, featured_image, recipe_json, post_tag,
          category_id, status, author_id, created_at
        ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)`
      )
      .bind(
        body.title,
        body.pin_image ?? null,
        body.pin_description ?? null,
        body.board_name ?? null,
        finalSlug,
        body.article_content,
        body.featured_image,
        JSON.stringify(body.recipe_json),
        body.post_tag ?? null,
        categoryId,
        status,
        body.author_id,
        createdAt
      )
      .run();

    const newId = insert.meta.last_row_id;

    const { results } = await db
      .prepare("SELECT * FROM recipes WHERE id = ?1")
      .bind(newId)
      .all();

    // Get site domain from settings for full URL
    const dbService = new DatabaseService(db);
    const settings = await dbService.getAllSettings();
    const siteDomain = settings.site_domain || 'momdishmagic.com';
    const fullUrl = `https://${siteDomain}/${finalSlug}/`;

    return new Response(JSON.stringify({
      success: true,
      data: results[0],
      generated_slug: finalSlug,    // The slug that was used (with -1, -2 etc if needed)
      url: fullUrl                  // Full URL to the recipe page
    }), {
      status: 201,
      headers: { "Content-Type": "application/json" }
    });

  } catch (error: any) {
    console.error("Error creating recipe:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to create recipe"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};