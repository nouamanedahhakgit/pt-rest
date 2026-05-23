globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                     */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, l as Fragment, u as unescapeHTML } from '../../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../../chunks/Layout_C1yRHkwR.mjs';
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
  let page;
  let settings = {};
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      [page, settings] = await Promise.all([
        db.getPageBySlug(slug),
        db.getAllSettings()
      ]);
      if (!page) {
        return Astro2.redirect("/404");
      }
    }
  } catch (error) {
    console.error("Error fetching page:", error);
    return Astro2.redirect("/404");
  }
  if (!page) {
    return Astro2.redirect("/404");
  }
  const siteName = settings.site_name || "ChefTaling";
  settings.site_domain || "cheftaling.com";
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": `${page.title} - ${siteName}`, "description": page.meta_description || page.title, "canonical": Astro2.url.toString() }, { "default": async ($$result2) => renderTemplate`  ${maybeRenderHead()}<div class="page-header"> <div class="wrap"> <!-- Breadcrumb --> <nav class="mb-6" aria-label="Breadcrumb"> <ol class="flex items-center space-x-3 text-sm"> <li> <a href="/" class="breadcrumb-link"> <svg class="w-4 h-4 mr-1 inline" fill="currentColor" viewBox="0 0 24 24"> <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"></path> </svg>
Home
</a> </li> <li class="breadcrumb-separator"> <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"> <path d="M9.29 15.88L13.17 12 9.29 8.12a.996.996 0 1 1 1.41-1.41l4.59 4.59c.39.39.39 1.02 0 1.41L10.7 17.3a.996.996 0 0 1-1.41-1.42z"></path> </svg> </li> <li class="breadcrumb-current"> ${page.title} </li> </ol> </nav> <h1 class="page-title">${page.title}</h1> </div> </div>  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12"> <div class="page-content"> ${renderComponent($$result2, "Fragment", Fragment, {}, { "default": async ($$result3) => renderTemplate`${unescapeHTML(page.content)}` })} </div> </div> ` })} `;
}, "/Users/anjani/Desktop/cheftaling/src/pages/page/[slug].astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/page/[slug].astro";
const $$url = "/page/[slug]";

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
