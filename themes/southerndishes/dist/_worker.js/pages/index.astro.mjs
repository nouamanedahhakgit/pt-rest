globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                  */
import { e as createComponent, f as createAstro, m as maybeRenderHead, h as addAttribute, r as renderTemplate, k as renderComponent } from '../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../chunks/Layout_C1yRHkwR.mjs';
import { $ as $$RecipeCard } from '../chunks/RecipeCard_CGJ9YJbK.mjs';
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
export { renderers } from '../renderers.mjs';

const $$Astro$1 = createAstro();
const $$FeaturedCategorySection = createComponent(($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro$1, $$props, $$slots);
  Astro2.self = $$FeaturedCategorySection;
  const {
    badge = "YUMMY!",
    title,
    description,
    featuredImage,
    buttonText = "More Recipes",
    buttonLink,
    recipes
  } = Astro2.props;
  const displayRecipes = recipes.slice(0, 6);
  return renderTemplate`${maybeRenderHead()}<section class="w-full bg-white py-12"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <div class="grid grid-cols-1 lg:grid-cols-12 gap-8"> <!-- Left: Featured Card --> <div class="lg:col-span-4"> <div class="bg-white rounded-lg overflow-hidden"> <!-- Featured Image with Badge --> <div class="relative"> <img${addAttribute(featuredImage, "src")}${addAttribute(title, "alt")} class="w-full aspect-[4/3] object-cover" loading="lazy"> <!-- Badge --> <div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-brand-400 to-brand-500 text-white text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-full shadow-lg"> ${badge} </div> </div> <!-- Content Below Image --> <div class="p-6 text-center"> <!-- Title --> <h2 class="font-playfair text-3xl font-bold text-gray-900 mb-4"> ${title} </h2> <!-- Description --> <p class="text-gray-600 text-sm mb-6 leading-relaxed"> ${description} </p> <!-- Button --> <a${addAttribute(buttonLink, "href")} class="inline-flex items-center gap-2 text-brand-600 hover:text-brand-700 font-semibold transition-colors group text-sm"> ${buttonText} <svg class="w-4 h-4 transform group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path> </svg> </a> </div> </div> </div> <!-- Right: Recipe Grid (3x2) --> <div class="lg:col-span-8"> <div class="grid grid-cols-3 gap-4"> ${displayRecipes.map((recipe) => renderTemplate`<a${addAttribute(`/${recipe.slug}/`, "href")} class="group block text-center"> <!-- Recipe Image --> <div class="aspect-square overflow-hidden rounded-lg mb-2"> <img${addAttribute(recipe.featured_image, "src")}${addAttribute(recipe.title, "alt")} class="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-300" loading="lazy"> </div> <!-- Recipe Title --> <h3 class="font-semibold text-sm text-gray-900 group-hover:text-brand-600 transition-colors line-clamp-2 leading-tight"> ${recipe.title} </h3> </a>`)} </div> </div> </div> </div> </section>`;
}, "/Users/anjani/Desktop/cheftaling/src/components/FeaturedCategorySection.astro", void 0);

const $$Astro = createAstro();
const $$Index = createComponent(async ($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$Index;
  const db = new DatabaseService(Astro2.locals.runtime?.env?.DB || {});
  let featuredRecipes = [];
  let latestRecipes = [];
  let categories = [];
  let popularRecipes = [];
  let authors = [];
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      [featuredRecipes, latestRecipes, categories, popularRecipes, authors] = await Promise.all([
        db.getFeaturedRecipes(6),
        db.getRecipes(6),
        db.getCategories(),
        db.getRecipesByCategory("desserts", 6, 0),
        // Get 6 dessert recipes for the featured section
        db.getAuthors()
        // Get all authors
      ]);
    }
  } catch (error) {
    console.error("Error fetching data for homepage:", error);
  }
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": "Recipe Website - Delicious Recipes for Every Occasion", "description": "Discover amazing recipes for every meal and occasion. From quick weeknight dinners to special celebration dishes, find your next favorite recipe here." }, { "default": async ($$result2) => renderTemplate`  ${maybeRenderHead()}<section class="relative bg-gradient-to-br from-brand-50 to-teal-50 py-16 lg:py-24"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <div class="text-center"> <h1 class="font-playfair text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-6">
Discover Amazing
<span class="text-brand-600 block">Recipes</span> </h1> <p class="text-xl text-gray-600 mb-8 max-w-2xl mx-auto leading-relaxed">
From quick weeknight dinners to special celebration meals, find delicious recipes
          that bring joy to your kitchen and your table.
</p> <div class="flex flex-col sm:flex-row gap-4 justify-center"> <a href="/recipes" class="inline-flex items-center px-8 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg transition-colors">
Browse All Recipes
<svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path> </svg> </a> <a href="/category/desserts" class="inline-flex items-center px-8 py-3 bg-white hover:bg-gray-50 text-gray-700 font-semibold rounded-lg border border-gray-300 transition-colors">
Popular Desserts
</a> </div> </div> </div> </section>  ${popularRecipes.length > 0 && renderTemplate`${renderComponent($$result2, "FeaturedCategorySection", $$FeaturedCategorySection, { "badge": "YUMMY!", "title": "Popular Recipes", "description": "Have you ever tried all of my famously popular recipes yet? From my irresistible favorites to numerous sweet recipes too! Check out our wide selection of delectable favorites that are sure to satisfy!", "featuredImage": popularRecipes[0]?.featured_image || "https://cheftaling.b-cdn.net/Screenshot%202025-10-30%20at%2016.15.08.png", "buttonText": "More Desserts", "buttonLink": "/category/desserts", "recipes": popularRecipes })}`} ${categories.length > 0 && renderTemplate`<section class="py-16"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <div class="text-center mb-12"> <h2 class="font-playfair text-3xl font-bold text-gray-900 mb-4">
Browse by Category
</h2> <p class="text-gray-600 max-w-2xl mx-auto">
Explore our collection of recipes organized by meal type and cuisine
</p> </div> <div class="flex justify-center items-center gap-12 flex-wrap"> ${categories.slice(0, 4).map((category) => {
    const iconMap = {
      "appetizers": "https://cheftaling.b-cdn.net/Untitled%20design%20(4)-min.png",
      "desserts": "https://cheftaling.b-cdn.net/Untitled%20design%20(3)-min.png",
      "main-dishes": "https://cdn-icons-png.flaticon.com/128/1046/1046786.png",
      "dinners": "https://cheftaling.b-cdn.net/Untitled%20design%20(7)-min.png",
      "breakfast": "https://cdn-icons-png.flaticon.com/128/2771/2771427.png",
      "drinks": "https://cheftaling.b-cdn.net/Untitled%20design%20(5)-min.png",
      "salads": "https://cdn-icons-png.flaticon.com/128/1046/1046769.png",
      "snacks": "https://cdn-icons-png.flaticon.com/128/2729/2729082.png"
    };
    const iconUrl = iconMap[category.slug] || "https://cdn-icons-png.flaticon.com/128/1046/1046857.png";
    return renderTemplate`<a${addAttribute(`/category/${category.slug}/`, "href")} class="group flex flex-col items-center text-center transition-all duration-300 hover:transform hover:scale-105"> <div class="w-25 h-25 mb-3 transition-transform duration-300 group-hover:scale-110"> <img${addAttribute(iconUrl, "src")}${addAttribute(category.name, "alt")} class="w-full h-full object-contain" loading="lazy"> </div> <h3 class="font-sans font-bold text-sm uppercase tracking-wide text-gray-900 group-hover:text-brand-600 transition-colors"> ${category.name} </h3> </a>`;
  })} </div> </div> </section>`} <section class="bg-white py-16 lg:py-24"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <!-- Two Column Layout --> <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-20 items-center mb-16"> <!-- Left Column: Circular Image with Dashed Border and Decorative Elements --> <div class="relative flex justify-center lg:justify-start"> <div class="relative w-full max-w-md"> <!-- Background Decorative Elements --> <div class="absolute inset-0 overflow-visible" style="z-index: 0;"> <!-- Pea Pod --> <svg class="absolute top-[5%] right-[8%] w-16 h-16 text-brand-300 opacity-70" viewBox="0 0 100 100" fill="currentColor"> <ellipse cx="50" cy="50" rx="18" ry="45" transform="rotate(25 50 50)"></ellipse> <circle cx="45" cy="30" r="10" fill="#3ae6c8"></circle> <circle cx="50" cy="50" r="10" fill="#3ae6c8"></circle> <circle cx="55" cy="70" r="10" fill="#3ae6c8"></circle> </svg> <!-- Carrot --> <svg class="absolute bottom-[15%] left-[-5%] w-20 h-20 text-brand-400 opacity-70" viewBox="0 0 100 100" fill="currentColor"> <path d="M50 25 L62 85 L50 92 L38 85 Z"></path> <path d="M43 22 L38 10 L40 5" stroke="#24a38a" stroke-width="4" fill="none" stroke-linecap="round"></path> <path d="M50 22 L50 5 L52 0" stroke="#24a38a" stroke-width="4" fill="none" stroke-linecap="round"></path> <path d="M57 22 L62 10 L60 5" stroke="#24a38a" stroke-width="4" fill="none" stroke-linecap="round"></path> </svg> <!-- Brand color circles (abstract soft shapes) --> <circle class="absolute top-[8%] right-[2%]" cx="0" cy="0" r="40" fill="#c2f9f0" opacity="0.6"></circle> <circle class="absolute bottom-[8%] right-[18%]" cx="0" cy="0" r="30" fill="#9df5e7" opacity="0.5"></circle> <circle class="absolute top-[45%] left-[-8%]" cx="0" cy="0" r="45" fill="#e8fdf9" opacity="0.7"></circle> <circle class="absolute bottom-[25%] left-[10%]" cx="0" cy="0" r="25" fill="#77f1de" opacity="0.5"></circle> <!-- Small decorative dots --> <circle class="absolute top-[18%] left-[12%]" cx="0" cy="0" r="5" fill="#1b7d68" opacity="0.3"></circle> <circle class="absolute top-[65%] right-[15%]" cx="0" cy="0" r="5" fill="#1b7d68" opacity="0.3"></circle> <circle class="absolute bottom-[8%] left-[20%]" cx="0" cy="0" r="5" fill="#1b7d68" opacity="0.3"></circle> <circle class="absolute top-[35%] right-[5%]" cx="0" cy="0" r="4" fill="#1b7d68" opacity="0.3"></circle> </div> <!-- Single Circular Image with Dotted Border --> <div class="relative mx-auto" style="width: 300px; height: 300px; z-index: 10;"> <div class="absolute inset-0 rounded-full border-4 border-dotted border-brand-400" style="padding: 12px;"> ${authors[0] && renderTemplate`<img${addAttribute(authors[0].image_url || "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=600&h=600&fit=crop&crop=face", "src")}${addAttribute(authors[0].name, "alt")} class="w-full h-full rounded-full object-cover shadow-xl">`} </div> </div> </div> </div> <!-- Right Column: Text Content --> <div class="text-center lg:text-left space-y-8"> <!-- Welcome Text --> <p class="text-4xl md:text-5xl text-brand-700" style="font-family: 'Dancing Script', cursive;">
welcome
</p> <!-- Main Heading --> <h2 class="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight text-gray-900">
HI. I'M <span class="font-black text-brand-600">ELYSIA!</span> </h2> <!-- Description --> <p class="text-lg md:text-xl leading-relaxed text-gray-600 max-w-[580px] mx-auto lg:mx-0">
I'm a Registered Dietitian and mom of two, passionate about helping you raise happy, healthy and adventurous eaters. Here, you'll find a collection of fun, nutritious and kid-friendly recipes and practical feeding tips!
</p> <!-- Button --> <div class="pt-4"> <a href="/about-us" class="inline-block px-10 py-4 rounded-2xl font-bold text-base tracking-wide transition-all hover:shadow-xl hover:scale-105 bg-brand-500 hover:bg-brand-600 text-white">
MORE ABOUT US
</a> </div> </div> </div> </div> <!-- Search Bar Section --> <div class="w-full py-10 bg-brand-50"> <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8"> <form action="/search" method="GET"> <div class="relative"> <input type="search" name="q" placeholder="Search for recipes, ingredients, or categories..." class="w-full px-8 py-5 rounded-full border-none outline-none text-gray-700 text-lg shadow-md focus:shadow-xl transition-shadow" style="padding-right: 60px;" autocomplete="off"> <button type="submit" class="absolute right-2 top-1/2 transform -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center transition-all hover:scale-110 bg-brand-600 hover:bg-brand-700" aria-label="Search"> <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path> </svg> </button> </div> </form> </div> </div> </section>  ${featuredRecipes.length > 0 && renderTemplate`<section class="py-16 bg-gray-50"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <div class="text-center mb-12"> <h2 class="font-playfair text-3xl font-bold text-gray-900 mb-4">
Featured Recipes
</h2> <p class="text-gray-600 max-w-2xl mx-auto">
Hand-picked recipes that our community loves most
</p> </div> <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"> ${featuredRecipes.map((recipe, index) => renderTemplate`${renderComponent($$result2, "RecipeCard", $$RecipeCard, { "recipe": recipe, "showCategory": true, "priority": index === 0 })}`)} </div> </div> </section>`} ${latestRecipes.length > 0 && renderTemplate`<section class="py-16"> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"> <div class="flex items-center justify-between mb-8"> <div> <h2 class="font-playfair text-3xl font-bold text-gray-900 mb-2">
Latest Recipes
</h2> <p class="text-gray-600">
Fresh recipes added to our collection
</p> </div> <a href="/recipes" class="hidden sm:inline-flex items-center text-brand-600 hover:text-brand-700 font-semibold">
View all recipes
<svg class="w-5 h-5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path> </svg> </a> </div> <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"> ${latestRecipes.map((recipe) => renderTemplate`${renderComponent($$result2, "RecipeCard", $$RecipeCard, { "recipe": recipe })}`)} </div> <div class="text-center mt-8 sm:hidden"> <a href="/recipes" class="inline-flex items-center px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg transition-colors">
View all recipes
<svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path> </svg> </a> </div> </div> </section>`}` })}`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/index.astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/index.astro";
const $$url = "";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Index,
  file: $$file,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
