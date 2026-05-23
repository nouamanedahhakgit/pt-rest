globalThis.process ??= {}; globalThis.process.env ??= {};
import { e as createComponent, f as createAstro, m as maybeRenderHead, h as addAttribute, r as renderTemplate } from './astro/server_BboE5Sy9.mjs';
import { s as stripHtml, t as truncateText, d as getResponsiveSrcSet, e as getImageSizes, f as formatTime } from './utils_DBF5Gx6Z.mjs';
/* empty css                          */

const $$Astro = createAstro();
const $$RecipeCard = createComponent(($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$RecipeCard;
  const { recipe, showCategory = false, className = "", imageSize = "medium", priority = false } = Astro2.props;
  let recipeData;
  try {
    recipeData = JSON.parse(recipe.recipe_json);
  } catch (e) {
    recipeData = {
      name: recipe.title,
      summary: "",
      servings: "",
      prep_time: "",
      cook_time: "",
      total_time: "",
      calories: "",
      course: "",
      cuisine: "",
      keywords: [],
      notes: "",
      ingredients: [],
      instructions: []
    };
  }
  const imageUrl = recipe.featured_image;
  const description = recipeData.summary || stripHtml(recipe.article_content);
  const truncatedDescription = truncateText(description, 120);
  const imageSizeClasses = {
    small: "h-48",
    medium: "h-56",
    large: "h-64"
  };
  const srcset = getResponsiveSrcSet(imageUrl, [400, 600, 800]);
  const sizes = getImageSizes([
    { maxWidth: "768px", size: "100vw" },
    { maxWidth: "1024px", size: "50vw" },
    { maxWidth: "9999px", size: "33vw" }
  ]);
  return renderTemplate`${maybeRenderHead()}<article${addAttribute(`bg-white rounded-xl shadow-sm hover:shadow-md transition-all duration-300 overflow-hidden group ${className}`, "class")} data-astro-cid-esnuq5xt> <a${addAttribute(`/${recipe.slug}/`, "href")} class="block" data-astro-cid-esnuq5xt> <div${addAttribute(`relative overflow-hidden ${imageSizeClasses[imageSize]}`, "class")} data-astro-cid-esnuq5xt> <img${addAttribute(imageUrl, "src")}${addAttribute(srcset || void 0, "srcset")}${addAttribute(sizes, "sizes")}${addAttribute(recipe.title, "alt")} class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"${addAttribute(priority ? "eager" : "lazy", "loading")}${addAttribute(priority ? "high" : void 0, "fetchpriority")} width="800" height="600" data-astro-cid-esnuq5xt> ${showCategory && recipe.category && renderTemplate`<div class="absolute top-3 left-3" data-astro-cid-esnuq5xt> <span class="bg-white/90 backdrop-blur-sm text-gray-900 px-2 py-1 rounded-full text-xs font-medium" data-astro-cid-esnuq5xt> ${recipe.category.name} </span> </div>`} </div> <div class="p-6" data-astro-cid-esnuq5xt> <h3 class="font-playfair text-xl font-semibold text-gray-900 mb-2 group-hover:text-brand-600 transition-colors line-clamp-2" data-astro-cid-esnuq5xt> ${recipe.title} </h3> ${truncatedDescription && renderTemplate`<p class="text-gray-600 text-sm mb-3 line-clamp-3" data-astro-cid-esnuq5xt> ${truncatedDescription} </p>`} <div class="flex items-center justify-between text-sm text-gray-500" data-astro-cid-esnuq5xt> <div class="flex items-center space-x-4" data-astro-cid-esnuq5xt> ${recipeData.total_time && renderTemplate`<div class="flex items-center space-x-1" data-astro-cid-esnuq5xt> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-esnuq5xt> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" data-astro-cid-esnuq5xt></path> </svg> <span data-astro-cid-esnuq5xt>${formatTime(recipeData.total_time)}</span> </div>`} ${recipeData.servings && renderTemplate`<div class="flex items-center space-x-1" data-astro-cid-esnuq5xt> <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" data-astro-cid-esnuq5xt> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" data-astro-cid-esnuq5xt></path> </svg> <span data-astro-cid-esnuq5xt>${recipeData.servings} servings</span> </div>`} </div> <div class="text-brand-600 group-hover:text-brand-700 font-medium" data-astro-cid-esnuq5xt>
Read more →
</div> </div> </div> </a> </article> `;
}, "/Users/anjani/Desktop/cheftaling/src/components/RecipeCard.astro", void 0);

export { $$RecipeCard as $ };
