globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                  */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, h as addAttribute } from '../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../chunks/Layout_C1yRHkwR.mjs';
import { $ as $$RecipeGrid } from '../chunks/RecipeGrid_C1q2C0hT.mjs';
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
export { renderers } from '../renderers.mjs';

const $$Astro = createAstro();
const $$Recipes = createComponent(async ($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$Recipes;
  const db = new DatabaseService(Astro2.locals.runtime?.env?.DB || {});
  let recipes = [];
  let categories = [];
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      [recipes, categories] = await Promise.all([
        db.getRecipes(50),
        db.getCategories()
      ]);
    }
  } catch (error) {
    console.error("Error fetching recipes:", error);
  }
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": "All Recipes - Recipe Website", "description": "Browse our complete collection of delicious recipes. Find the perfect recipe for any occasion, from quick weeknight dinners to special celebration meals." }, { "default": async ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12"> <!-- Page Header --> <div class="text-center mb-12"> <h1 class="font-playfair text-4xl md:text-5xl font-bold text-gray-900 mb-4">
All Recipes
</h1> <p class="text-xl text-gray-600 max-w-2xl mx-auto">
Discover our complete collection of tested and perfected recipes
</p> </div> <!-- Categories Filter --> ${categories.length > 0 && renderTemplate`<div class="mb-8"> <div class="flex flex-wrap justify-center gap-3"> <a href="/recipes" class="px-4 py-2 bg-brand-600 text-white rounded-full text-sm font-medium hover:bg-brand-700 transition-colors">
All Recipes
</a> ${categories.map((category) => renderTemplate`<a${addAttribute(`/category/${category.slug}/`, "href")} class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full text-sm font-medium hover:bg-gray-200 transition-colors"> ${category.name} </a>`)} </div> </div>`} <!-- Recipes Grid --> ${renderComponent($$result2, "RecipeGrid", $$RecipeGrid, { "recipes": recipes, "showCategory": true })} ${recipes.length === 0 && renderTemplate`<div class="text-center py-16"> <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center"> <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path> </svg> </div> <h2 class="text-2xl font-bold text-gray-900 mb-2">No Recipes Available</h2> <p class="text-gray-600">
Recipes will appear here once the database is set up and populated.
</p> </div>`} </div> ` })}`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/recipes.astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/recipes.astro";
const $$url = "/recipes";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Recipes,
  file: $$file,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
