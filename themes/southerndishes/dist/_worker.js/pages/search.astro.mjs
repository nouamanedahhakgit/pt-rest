globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                  */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, h as addAttribute, l as Fragment } from '../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../chunks/Layout_C1yRHkwR.mjs';
import { $ as $$RecipeCard } from '../chunks/RecipeCard_CGJ9YJbK.mjs';
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
export { renderers } from '../renderers.mjs';

const $$Astro = createAstro();
const prerender = false;
const $$Search = createComponent(async ($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$Search;
  const searchQuery = Astro2.url.searchParams.get("q") || "";
  let recipes = [];
  let errorMessage = "";
  if (Astro2.locals.runtime?.env?.DB) {
    try {
      const db = new DatabaseService(Astro2.locals.runtime.env.DB);
      if (searchQuery.trim()) {
        recipes = await db.searchRecipes(searchQuery, 50);
      }
    } catch (error) {
      console.error("Search error:", error);
      errorMessage = "An error occurred while searching. Please try again.";
    }
  }
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": searchQuery ? `Search Results for "${searchQuery}"` : "Search Recipes", "description": searchQuery ? `Search results for "${searchQuery}" on our recipe website` : "Search our collection of delicious recipes" }, { "default": async ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12"> <!-- Search Header --> <div class="mb-8"> <h1 class="font-playfair text-4xl font-bold text-gray-900 mb-4"> ${searchQuery ? `Search Results` : "Search Recipes"} </h1> ${searchQuery && renderTemplate`<p class="text-gray-600 text-lg">
Showing results for <span class="font-semibold text-brand-600">"${searchQuery}"</span> </p>`} </div> <!-- Search Form --> <div class="mb-12"> <form action="/search" method="GET" class="max-w-2xl"> <div class="relative"> <input type="search" name="q"${addAttribute(searchQuery, "value")} placeholder="Search recipes..." class="w-full px-4 py-3 pl-12 pr-4 text-gray-700 bg-white border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" autocomplete="off" autofocus> <svg class="absolute left-4 top-1/2 transform -translate-y-1/2 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path> </svg> <button type="submit" class="absolute right-2 top-1/2 transform -translate-y-1/2 px-6 py-2 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg transition-colors">
Search
</button> </div> </form> </div> <!-- Error Message --> ${errorMessage && renderTemplate`<div class="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg"> <p class="text-red-700">${errorMessage}</p> </div>`} <!-- No Query Message --> ${!searchQuery && !errorMessage && renderTemplate`<div class="text-center py-12"> <svg class="mx-auto h-16 w-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path> </svg> <p class="text-gray-500 text-lg">Enter a search term to find recipes</p> </div>`} <!-- Search Results --> ${searchQuery && !errorMessage && renderTemplate`<div> ${recipes.length > 0 ? renderTemplate`${renderComponent($$result2, "Fragment", Fragment, {}, { "default": async ($$result3) => renderTemplate` <p class="text-gray-600 mb-6">
Found <span class="font-semibold">${recipes.length}</span> ${recipes.length === 1 ? "recipe" : "recipes"} </p> <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"> ${recipes.map((recipe) => renderTemplate`${renderComponent($$result3, "RecipeCard", $$RecipeCard, { "recipe": recipe, "showCategory": true })}`)} </div> ` })}` : renderTemplate`<div class="text-center py-12"> <svg class="mx-auto h-16 w-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path> </svg> <h3 class="text-xl font-semibold text-gray-900 mb-2">No recipes found</h3> <p class="text-gray-600 mb-6">
We couldn't find any recipes matching "${searchQuery}"
</p> <p class="text-gray-500 text-sm">
Try searching with different keywords or browse our <a href="/recipes" class="text-brand-600 hover:text-brand-700 underline">recipe collection</a> </p> </div>`} </div>`} </div> ` })}`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/search.astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/search.astro";
const $$url = "/search";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Search,
  file: $$file,
  prerender,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
