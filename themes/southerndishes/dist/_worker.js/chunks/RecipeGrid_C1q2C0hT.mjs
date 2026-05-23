globalThis.process ??= {}; globalThis.process.env ??= {};
import { e as createComponent, f as createAstro, h as addAttribute, m as maybeRenderHead, r as renderTemplate, k as renderComponent } from './astro/server_BboE5Sy9.mjs';
import { $ as $$RecipeCard } from './RecipeCard_CGJ9YJbK.mjs';

const $$Astro = createAstro();
const $$RecipeGrid = createComponent(($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$RecipeGrid;
  const {
    recipes,
    title,
    showCategory = false,
    className = "",
    limit
  } = Astro2.props;
  const displayRecipes = limit ? recipes.slice(0, limit) : recipes;
  return renderTemplate`${title && renderTemplate`${maybeRenderHead()}<div class="text-center mb-8"><h2 class="font-playfair text-3xl font-bold text-gray-900">${title}</h2></div>`}<div${addAttribute(`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 ${className}`, "class")}> ${displayRecipes.map((recipe) => renderTemplate`${renderComponent($$result, "RecipeCard", $$RecipeCard, { "recipe": recipe, "showCategory": showCategory })}`)} </div> ${displayRecipes.length === 0 && renderTemplate`<div class="text-center py-12"> <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center"> <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path> </svg> </div> <h3 class="text-lg font-semibold text-gray-900 mb-2">No recipes found</h3> <p class="text-gray-600">
We couldn't find any recipes matching your criteria. Try browsing other categories or check back later for new recipes.
</p> </div>`}`;
}, "/Users/anjani/Desktop/cheftaling/src/components/RecipeGrid.astro", void 0);

export { $$RecipeGrid as $ };
