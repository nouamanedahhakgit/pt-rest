globalThis.process ??= {}; globalThis.process.env ??= {};
import { D as DatabaseService } from '../../chunks/database_CxskVbB6.mjs';
export { renderers } from '../../renderers.mjs';

const GET = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const categories = await db.getCategories();
    return new Response(JSON.stringify({
      success: true,
      data: categories
    }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=600"
      }
    });
  } catch (error) {
    console.error("Error fetching categories:", error);
    return new Response(JSON.stringify({
      success: false,
      error: "Failed to fetch categories"
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
