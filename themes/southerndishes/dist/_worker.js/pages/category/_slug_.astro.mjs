globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                     */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, h as addAttribute } from '../../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../../chunks/Layout_C1yRHkwR.mjs';
import { $ as $$RecipeGrid } from '../../chunks/RecipeGrid_C1q2C0hT.mjs';
import { D as DatabaseService } from '../../chunks/database_CxskVbB6.mjs';
export { renderers } from '../../renderers.mjs';

const $$Astro = createAstro();
const prerender = false;
async function getStaticPaths() {
  return [];
}
const $$slug = createComponent(async ($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$slug;
  const { slug } = Astro2.params;
  if (!slug) {
    return Astro2.redirect("/404");
  }
  const db = new DatabaseService(Astro2.locals.runtime?.env?.DB || {});
  let category;
  let recipes = [];
  let allCategories = [];
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      [category, recipes, allCategories] = await Promise.all([
        db.getCategoryBySlug(slug),
        db.getRecipesByCategory(slug, 50),
        db.getCategories()
      ]);
      if (!category) {
        return Astro2.redirect("/404");
      }
    }
  } catch (error) {
    console.error("Error fetching category data:", error);
    return Astro2.redirect("/404");
  }
  if (!category) {
    return Astro2.redirect("/404");
  }
  const pageTitle = `${category.name} Recipes - Recipe Website`;
  const pageDescription = category.description || `Discover delicious ${category.name.toLowerCase()} recipes. Perfect for any occasion.`;
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": pageTitle, "description": pageDescription }, { "default": async ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12"> <!-- Breadcrumb --> <nav class="mb-8" aria-label="Breadcrumb"> <ol class="flex items-center space-x-2 text-sm text-gray-500"> <li> <a href="/" class="hover:text-gray-700 transition-colors">Home</a> </li> <li> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path> </svg> </li> <li> <a href="/recipes" class="hover:text-gray-700 transition-colors">Recipes</a> </li> <li> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path> </svg> </li> <li class="text-gray-900 font-medium"> ${category.name} </li> </ol> </nav> <!-- Page Header --> <div class="text-center mb-12"> <h1 class="font-playfair text-4xl md:text-5xl font-bold text-gray-900 mb-4"> ${category.name} Recipes
</h1> ${category.description && renderTemplate`<p class="text-xl text-gray-600 max-w-2xl mx-auto"> ${category.description} </p>`} <div class="mt-4 text-sm text-gray-500"> ${recipes.length} ${recipes.length === 1 ? "recipe" : "recipes"} found
</div> </div> <!-- Categories Filter --> ${allCategories.length > 0 && renderTemplate`<div class="mb-8"> <div class="flex flex-wrap justify-center gap-3"> <a href="/recipes" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full text-sm font-medium hover:bg-gray-200 transition-colors">
All Recipes
</a> ${allCategories.map((cat) => renderTemplate`<a${addAttribute(`/category/${cat.slug}/`, "href")}${addAttribute(`px-4 py-2 rounded-full text-sm font-medium transition-colors ${cat.slug === category.slug ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`, "class")}> ${cat.name} </a>`)} </div> </div>`} <!-- Recipes Grid --> ${renderComponent($$result2, "RecipeGrid", $$RecipeGrid, { "recipes": recipes, "showCategory": false })} ${recipes.length === 0 && renderTemplate`<div class="text-center py-16"> <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center"> <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path> </svg> </div> <h2 class="text-2xl font-bold text-gray-900 mb-2">No ${category.name} Recipes</h2> <p class="text-gray-600 mb-6">
We don't have any ${category.name.toLowerCase()} recipes yet. Check back soon for new additions!
</p> <a href="/recipes" class="inline-flex items-center px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg transition-colors">
Browse All Recipes
<svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path> </svg> </a> </div>`} </div> ` })}`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/category/[slug].astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/category/[slug].astro";
const $$url = "/category/[slug]";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$slug,
  file: $$file,
  getStaticPaths,
  prerender,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
