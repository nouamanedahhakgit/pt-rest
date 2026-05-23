globalThis.process ??= {}; globalThis.process.env ??= {};
import { D as DatabaseService } from '../../chunks/database_CxskVbB6.mjs';
export { renderers } from '../../renderers.mjs';

const GET = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = locals.runtime?.env ?? {};
    const apiToken = runtimeEnv.API_TOKEN;
    const authHeader = request.headers.get("Authorization");
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: "Unauthorized" }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );
    }
    const db = new DatabaseService(runtimeEnv.DB);
    const searchParams = new URL(url).searchParams;
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || "12");
    const category = searchParams.get("category");
    const search = searchParams.get("search");
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
          hasMore: recipes.length === limit
        }
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=300"
        }
      }
    );
  } catch (error) {
    console.error("Error fetching recipes:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: "Failed to fetch recipes"
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
};
const POST = async ({ request, locals }) => {
  try {
    const runtimeEnv = locals.runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;
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
    const body = await request.json();
    if (!body.title || !body.slug || !body.article_content || !body.featured_image || !body.recipe_json || body.author_id == null) {
      return new Response(JSON.stringify({
        success: false,
        error: "Missing required fields (title, slug, article_content, featured_image, recipe_json, author_id)"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }
    let finalSlug = body.slug;
    const slugExists = async (slug) => {
      const { results: results2 } = await db.prepare("SELECT id FROM recipes WHERE slug = ?1").bind(slug).all();
      return results2.length > 0;
    };
    if (await slugExists(finalSlug)) {
      let counter = 1;
      while (await slugExists(`${finalSlug}-${counter}`)) {
        counter++;
      }
      finalSlug = `${finalSlug}-${counter}`;
    }
    const status = body.status ?? "draft";
    const categoryId = body.category_id ?? null;
    const insert = await db.prepare(
      `INSERT INTO recipes (
          title, pin_image, pin_description, slug,
          article_content, featured_image, recipe_json,
          category_id, status, author_id
        ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)`
    ).bind(
      body.title,
      body.pin_image ?? null,
      body.pin_description ?? null,
      finalSlug,
      body.article_content,
      body.featured_image,
      JSON.stringify(body.recipe_json),
      categoryId,
      status,
      body.author_id
    ).run();
    const newId = insert.meta.last_row_id;
    const { results } = await db.prepare("SELECT * FROM recipes WHERE id = ?1").bind(newId).all();
    return new Response(JSON.stringify({
      success: true,
      data: results[0],
      generated_slug: finalSlug
      // 👈 helpful for your client/API
    }), {
      status: 201,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
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

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  GET,
  POST
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
