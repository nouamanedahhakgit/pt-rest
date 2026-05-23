globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                     */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, h as addAttribute } from '../../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../../chunks/Layout_C1yRHkwR.mjs';
import { $ as $$RecipeGrid } from '../../chunks/RecipeGrid_C1q2C0hT.mjs';
import { D as DatabaseService } from '../../chunks/database_CxskVbB6.mjs';
/* empty css                                     */
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
  let author;
  let recipes = [];
  let recipeCount = 0;
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      [author, recipes, recipeCount] = await Promise.all([
        db.getAuthorBySlug(slug),
        db.getRecipesByAuthor(slug, 50),
        db.getRecipeCountByAuthor(slug)
      ]);
      if (!author) {
        return Astro2.redirect("/404");
      }
    }
  } catch (error) {
    console.error("Error fetching author data:", error);
    return Astro2.redirect("/404");
  }
  if (!author) {
    return Astro2.redirect("/404");
  }
  const pageTitle = `${author.name} - Recipe Author`;
  const pageDescription = author.bio || `View all recipes by ${author.name}`;
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": pageTitle, "description": pageDescription, "image": author.image_url, "data-astro-cid-qudmmarv": true }, { "default": async ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-astro-cid-qudmmarv> <!-- Breadcrumb --> <nav class="mb-8" aria-label="Breadcrumb" data-astro-cid-qudmmarv> <ol class="flex items-center space-x-2 text-sm text-gray-500" data-astro-cid-qudmmarv> <li data-astro-cid-qudmmarv> <a href="/" class="hover:text-gray-700 transition-colors" data-astro-cid-qudmmarv>Home</a> </li> <li data-astro-cid-qudmmarv> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-qudmmarv> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" data-astro-cid-qudmmarv></path> </svg> </li> <li data-astro-cid-qudmmarv> <a href="/recipes" class="hover:text-gray-700 transition-colors" data-astro-cid-qudmmarv>Recipes</a> </li> <li data-astro-cid-qudmmarv> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-qudmmarv> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" data-astro-cid-qudmmarv></path> </svg> </li> <li class="text-gray-900 font-medium" data-astro-cid-qudmmarv> ${author.name} </li> </ol> </nav> <!-- Author Header --> <div class="author-page-header" data-astro-cid-qudmmarv> <div class="author-page-content" data-astro-cid-qudmmarv> ${author.image_url && renderTemplate`<img${addAttribute(author.image_url, "src")}${addAttribute(author.name, "alt")} class="author-page-avatar" data-astro-cid-qudmmarv>`} <div class="author-page-info" data-astro-cid-qudmmarv> <h1 class="author-page-name" data-astro-cid-qudmmarv>${author.name}</h1> ${author.title && renderTemplate`<p class="author-page-title" data-astro-cid-qudmmarv>${author.title}</p>`} ${author.bio && renderTemplate`<p class="author-page-bio" data-astro-cid-qudmmarv>${author.bio}</p>`} <div class="author-page-stats" data-astro-cid-qudmmarv> <div class="author-stat" data-astro-cid-qudmmarv> <span class="stat-number" data-astro-cid-qudmmarv>${recipeCount}</span> <span class="stat-label" data-astro-cid-qudmmarv>${recipeCount === 1 ? "Recipe" : "Recipes"}</span> </div> </div> </div> </div> </div> <!-- Recipes Section --> <div class="mt-12" data-astro-cid-qudmmarv> <h2 class="text-2xl font-bold text-gray-900 mb-6" data-astro-cid-qudmmarv>
Recipes by ${author.name} </h2> ${renderComponent($$result2, "RecipeGrid", $$RecipeGrid, { "recipes": recipes, "showCategory": true, "data-astro-cid-qudmmarv": true })} </div> ${recipes.length === 0 && renderTemplate`<div class="text-center py-16" data-astro-cid-qudmmarv> <div class="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center" data-astro-cid-qudmmarv> <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-qudmmarv> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" data-astro-cid-qudmmarv></path> </svg> </div> <h2 class="text-2xl font-bold text-gray-900 mb-2" data-astro-cid-qudmmarv>No Recipes Yet</h2> <p class="text-gray-600 mb-6" data-astro-cid-qudmmarv> ${author.name} hasn't published any recipes yet. Check back soon!
</p> <a href="/recipes" class="inline-flex items-center px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg transition-colors" data-astro-cid-qudmmarv>
Browse All Recipes
<svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-qudmmarv> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" data-astro-cid-qudmmarv></path> </svg> </a> </div>`} </div> ` })} `;
}, "/Users/anjani/Desktop/cheftaling/src/pages/author/[slug].astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/author/[slug].astro";
const $$url = "/author/[slug]";

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
