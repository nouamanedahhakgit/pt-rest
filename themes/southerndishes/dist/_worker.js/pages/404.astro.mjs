globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                  */
import { e as createComponent, k as renderComponent, r as renderTemplate, m as maybeRenderHead } from '../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../chunks/Layout_C1yRHkwR.mjs';
export { renderers } from '../renderers.mjs';

const $$404 = createComponent(($$result, $$props, $$slots) => {
  const title = "404 - Page Not Found";
  const description = "Sorry, the page you are looking for does not exist. Browse our delicious recipes instead.";
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": title, "description": description }, { "default": ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="min-h-[60vh] flex items-center justify-center px-4 py-16"> <div class="max-w-2xl mx-auto text-center"> <!-- 404 Illustration --> <div class="mb-8"> <div class="inline-flex items-center justify-center w-32 h-32 bg-brand-100 rounded-full mb-6"> <svg class="w-16 h-16 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path> </svg> </div> <h1 class="text-6xl md:text-8xl font-bold font-playfair text-gray-900 mb-4">
404
</h1> <h2 class="text-2xl md:text-3xl font-semibold text-gray-800 mb-4">
Oops! Page Not Found
</h2> <p class="text-lg text-gray-600 mb-8 max-w-md mx-auto">
The recipe you're looking for seems to have been misplaced. Don't worry, we have plenty of other delicious options for you!
</p> </div> <!-- Action Buttons --> <div class="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12"> <a href="/" class="btn-primary px-8 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors font-medium inline-flex items-center gap-2"> <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path> </svg>
Go to Homepage
</a> <a href="/recipes" class="btn-secondary px-8 py-3 bg-white text-brand-600 border-2 border-brand-600 rounded-lg hover:bg-brand-50 transition-colors font-medium inline-flex items-center gap-2"> <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path> </svg>
Browse Recipes
</a> </div> <!-- Popular Links --> <div class="border-t border-gray-200 pt-8"> <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
Popular Categories
</h3> <div class="flex flex-wrap justify-center gap-3"> <a href="/category/desserts" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-brand-100 hover:text-brand-700 transition-colors text-sm font-medium">
Desserts
</a> <a href="/category/main-dishes" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-brand-100 hover:text-brand-700 transition-colors text-sm font-medium">
Main Dishes
</a> <a href="/category/appetizers" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-brand-100 hover:text-brand-700 transition-colors text-sm font-medium">
Appetizers
</a> <a href="/category/breakfast" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-brand-100 hover:text-brand-700 transition-colors text-sm font-medium">
Breakfast
</a> </div> </div> </div> </div> ` })}`;
}, "/Users/anjani/Desktop/cheftaling/src/pages/404.astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/404.astro";
const $$url = "/404";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$404,
  file: $$file,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
