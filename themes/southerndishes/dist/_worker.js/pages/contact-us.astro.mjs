globalThis.process ??= {}; globalThis.process.env ??= {};
/* empty css                                  */
import { e as createComponent, f as createAstro, k as renderComponent, r as renderTemplate, m as maybeRenderHead, u as unescapeHTML, h as addAttribute } from '../chunks/astro/server_BboE5Sy9.mjs';
import { $ as $$Layout } from '../chunks/Layout_C1yRHkwR.mjs';
import { D as DatabaseService } from '../chunks/database_CxskVbB6.mjs';
/* empty css                                      */
export { renderers } from '../renderers.mjs';

const $$Astro = createAstro();
const prerender = false;
const $$ContactUs = createComponent(async ($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$ContactUs;
  const db = new DatabaseService(Astro2.locals.runtime?.env?.DB || {});
  let page;
  let settings = {};
  try {
    if (Astro2.locals.runtime?.env?.DB) {
      page = await db.getPageBySlug("contact-us");
      if (!page) return Astro2.redirect("/404");
      settings = await db.getAllSettings();
    }
  } catch (error) {
    console.error("Error fetching page:", error);
    return Astro2.redirect("/404");
  }
  if (!page) return Astro2.redirect("/404");
  const siteName = settings.site_name || "ChefTaling";
  const siteDomain = settings.site_domain || "cheftaling.com";
  const contactMethods = [
    {
      title: "General Inquiries",
      description: "For general questions, feedback, or suggestions",
      email: `hello@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>`
    },
    {
      title: "Recipe Questions",
      description: "Have a question about one of our recipes? Need a substitution suggestion? We're happy to help!",
      email: `recipes@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>`
    },
    {
      title: "Business Inquiries",
      description: "For partnership opportunities, sponsorships, or business-related inquiries",
      email: `business@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>`
    },
    {
      title: "Technical Support",
      description: "Experiencing issues with our website? Let us know",
      email: `support@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>`
    },
    {
      title: "Legal Matters",
      description: "For copyright, privacy, or other legal concerns",
      email: `legal@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/>`
    },
    {
      title: "Media & Press",
      description: "Are you a journalist or blogger looking for information or interviews?",
      email: `press@${siteDomain}`,
      icon: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>`
    }
  ];
  return renderTemplate`${renderComponent($$result, "Layout", $$Layout, { "title": `${page.title} - ${siteName}`, "description": page.meta_description || page.title, "canonical": Astro2.url.toString() }, { "default": async ($$result2) => renderTemplate` ${maybeRenderHead()}<div class="page-header"> <div class="wrap"> <nav class="mb-6" aria-label="Breadcrumb"> <ol class="flex items-center space-x-3 text-sm"> <li><a href="/" class="breadcrumb-link"><svg class="w-4 h-4 mr-1 inline" fill="currentColor" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"></path></svg>Home</a></li> <li class="breadcrumb-separator"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M9.29 15.88L13.17 12 9.29 8.12a.996.996 0 1 1 1.41-1.41l4.59 4.59c.39.39.39 1.02 0 1.41L10.7 17.3a.996.996 0 0 1-1.41-1.42z"></path></svg></li> <li class="breadcrumb-current">${page.title}</li> </ol> </nav> <h1 class="page-title">${page.title}</h1> </div> </div> <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12"> <div class="contact-cards-grid"> ${contactMethods.map((method) => renderTemplate`<div class="contact-card"> <div class="contact-icon-wrapper"> <svg class="contact-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">${unescapeHTML(method.icon)}</svg> </div> <h3 class="contact-card-title">${method.title}</h3> <p class="contact-card-description">${method.description}</p> <a${addAttribute(`mailto:${method.email}`, "href")} class="contact-email"> <svg class="email-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path> </svg> ${method.email} </a> </div>`)} </div> <div class="additional-info"> <div class="info-card"> <h2 class="info-title">Connect on Social Media</h2> <p class="info-text">Follow us on social media for daily recipe inspiration, cooking tips, and behind-the-scenes content.</p> <div class="social-links"> <a href="https://pinterest.com" target="_blank" rel="noopener noreferrer" class="social-link pinterest"> <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.174-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.781c0-1.663.967-2.911 2.168-2.911 1.024 0 1.518.769 1.518 1.688 0 1.029-.653 2.567-.992 3.992-.285 1.193.6 2.165 1.775 2.165 2.128 0 3.768-2.245 3.768-5.487 0-2.861-2.063-4.869-5.008-4.869-3.41 0-5.409 2.562-5.409 5.199 0 1.033.394 2.143.889 2.741.099.12.112.225.085.345-.09.375-.293 1.199-.334 1.363-.053.225-.172.271-.402.165-1.495-.69-2.433-2.878-2.433-4.646 0-3.776 2.748-7.252 7.92-7.252 4.158 0 7.392 2.967 7.392 6.923 0 4.135-2.607 7.462-6.233 7.462-1.214 0-2.357-.629-2.758-1.378l-.749 2.848c-.269 1.045-1.004 2.352-1.498 3.146 1.123.345 2.306.535 3.55.535 6.624 0 11.99-5.367 11.99-11.988C24.007 5.367 18.641.001 12.017.001z"></path></svg> <span>Pinterest</span> </a> <a href="https://facebook.com" target="_blank" rel="noopener noreferrer" class="social-link facebook"> <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"></path></svg> <span>Facebook</span> </a> </div> </div> <div class="info-card"> <h2 class="info-title">Response Time</h2> <p class="info-text">We aim to respond to all inquiries within 2-3 business days. During busy periods, it may take slightly longer, but we promise to get back to you as soon as possible.</p> </div> </div> </div> ` })} `;
}, "/Users/anjani/Desktop/cheftaling/src/pages/contact-us.astro", void 0);

const $$file = "/Users/anjani/Desktop/cheftaling/src/pages/contact-us.astro";
const $$url = "/contact-us";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$ContactUs,
  file: $$file,
  prerender,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
