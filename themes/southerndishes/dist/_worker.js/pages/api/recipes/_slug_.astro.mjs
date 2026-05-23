globalThis.process ??= {}; globalThis.process.env ??= {};
import { D as DatabaseService } from '../../../chunks/database_CxskVbB6.mjs';
export { renderers } from '../../../renderers.mjs';

const GET = async ({ params, locals }) => {
  try {
    const { slug } = params;
    if (!slug) {
      return new Response(JSON.stringify({
        success: false,
        error: "Recipe slug is required"
      }), {
        status: 400,
        headers: {
          "Content-Type": "application/json"
        }
      });
    }
    const db = new DatabaseService(locals.runtime.env.DB);
    const recipe = await db.getRecipeBySlug(slug);
    if (!recipe) {
      return new Response(JSON.stringify({
        success: false,
        error: "Recipe not found"
      }), {
        status: 404,
        headers: {
          "Content-Type": "application/json"
        }
      });
    }
    let relatedRecipes = [];
    if (recipe.category_id) {
      relatedRecipes = await db.getRelatedRecipes(recipe.category_id, recipe.id, 3);
    }
    return new Response(JSON.stringify({
      success: true,
      data: {
        recipe,
        relatedRecipes
      }
    }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=300"
      }
    });
  } catch (error) {
    console.error("Error fetching recipe:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to fetch recipe"
    }), {
      status: 500,
      headers: {
        "Content-Type": "application/json"
      }
    });
  }
};

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  GET
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
