globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                     */
import { e as createComponent, f as createAstro, n as renderHead, h as addAttribute, r as renderTemplate } from '../../chunks/astro/server_BboE5Sy9.mjs';
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
  let recipe;
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      recipe = await db.getRecipeBySlug(slug);
      if (!recipe) {
        return Astro2.redirect("/404");
      }
    }
  } catch (error) {
    console.error("Error fetching recipe:", error);
    return Astro2.redirect("/404");
  }
  if (!recipe) {
    return Astro2.redirect("/404");
  }
  return renderTemplate`<html lang="en" data-astro-cid-l77jcxit> <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Print: ${recipe.title}</title>${renderHead()}</head> <body data-astro-cid-l77jcxit> <div class="container" data-astro-cid-l77jcxit> <div class="page-header" data-astro-cid-l77jcxit> <a${addAttribute(`/${recipe.slug}/`, "href")} class="back-link" data-astro-cid-l77jcxit>
← Back to Recipe
</a> <button onclick="window.print()" class="print-button" data-astro-cid-l77jcxit>
🖨️ Print Recipe
</button> </div> <div class="content" data-astro-cid-l77jcxit> <div class="print-header" data-astro-cid-l77jcxit> <h1 data-astro-cid-l77jcxit>${recipe.title}</h1> <div class="recipe-meta" data-astro-cid-l77jcxit> ${recipe.recipe_data.prep_time && renderTemplate`<div class="meta-item" data-astro-cid-l77jcxit> <div class="meta-value" data-astro-cid-l77jcxit>${recipe.recipe_data.prep_time}</div> <div class="meta-label" data-astro-cid-l77jcxit>Prep (mins)</div> </div>`} ${recipe.recipe_data.cook_time && renderTemplate`<div class="meta-item" data-astro-cid-l77jcxit> <div class="meta-value" data-astro-cid-l77jcxit>${recipe.recipe_data.cook_time}</div> <div class="meta-label" data-astro-cid-l77jcxit>Cook (mins)</div> </div>`} ${recipe.recipe_data.servings && renderTemplate`<div class="meta-item" data-astro-cid-l77jcxit> <div class="meta-value" data-astro-cid-l77jcxit>${recipe.recipe_data.servings}</div> <div class="meta-label" data-astro-cid-l77jcxit>Servings</div> </div>`} ${recipe.recipe_data.calories && renderTemplate`<div class="meta-item" data-astro-cid-l77jcxit> <div class="meta-value" data-astro-cid-l77jcxit>${recipe.recipe_data.calories}</div> <div class="meta-label" data-astro-cid-l77jcxit>Calories</div> </div>`} </div> </div> ${recipe.recipe_data.ingredients && recipe.recipe_data.ingredients.length > 0 && renderTemplate`<div class="recipe-section" data-astro-cid-l77jcxit> <h2 data-astro-cid-l77jcxit>Ingredients</h2> <ul class="ingredients-list" data-astro-cid-l77jcxit> ${recipe.recipe_data.ingredients.map((ingredient) => renderTemplate`<li data-astro-cid-l77jcxit> <span class="ingredient-checkbox" data-astro-cid-l77jcxit></span> <span class="ingredient-text" data-astro-cid-l77jcxit> ${ingredient.amount && `${ingredient.amount} `} ${ingredient.unit && `${ingredient.unit} `} ${ingredient.name} </span> </li>`)} </ul> </div>`} ${recipe.recipe_data.instructions && recipe.recipe_data.instructions.length > 0 && renderTemplate`<div class="recipe-section" data-astro-cid-l77jcxit> <h2 data-astro-cid-l77jcxit>Instructions</h2> <ol class="instructions-list" data-astro-cid-l77jcxit> ${recipe.recipe_data.instructions.map((instruction) => renderTemplate`<li data-astro-cid-l77jcxit> <span class="instruction-text" data-astro-cid-l77jcxit>${instruction}</span> </li>`)} </ol> </div>`} ${recipe.recipe_data.notes && renderTemplate`<div class="notes-section" data-astro-cid-l77jcxit> <h3 data-astro-cid-l77jcxit>💡 Chef's Notes</h3> <p data-astro-cid-l77jcxit>${recipe.recipe_data.notes}</p> </div>`} ${recipe.author && renderTemplate`<div class="author-credit" data-astro-cid-l77jcxit>
Recipe by <strong data-astro-cid-l77jcxit>${recipe.author.name}</strong> ${recipe.author.title && ` - ${recipe.author.title}`} </div>`} </div> </div> </body></html>`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/print/[slug].astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/print/[slug].astro";
const $$url = "/print/[slug]";

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
