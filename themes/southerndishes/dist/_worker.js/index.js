globalThis.process ??= {}; globalThis.process.env ??= {};
import { renderers } from './renderers.mjs';
import { c as createExports, s as serverEntrypointModule } from './chunks/_@astrojs-ssr-adapter_QaZFiBsf.mjs';
import { manifest } from './manifest_B0sUGrc4.mjs';

const serverIslandMap = new Map();;

const _page0 = () => import('./pages/_image.astro.mjs');
const _page1 = () => import('./pages/404.astro.mjs');
const _page2 = () => import('./pages/about-us.astro.mjs');
const _page3 = () => import('./pages/api/categories.astro.mjs');
const _page4 = () => import('./pages/api/recipes/_slug_.astro.mjs');
const _page5 = () => import('./pages/api/recipes.astro.mjs');
const _page6 = () => import('./pages/author/_slug_.astro.mjs');
const _page7 = () => import('./pages/category/_slug_.astro.mjs');
const _page8 = () => import('./pages/contact-us.astro.mjs');
const _page9 = () => import('./pages/cookie-policy.astro.mjs');
const _page10 = () => import('./pages/copyright-policy.astro.mjs');
const _page11 = () => import('./pages/disclaimer.astro.mjs');
const _page12 = () => import('./pages/gdpr-policy.astro.mjs');
const _page13 = () => import('./pages/page/_slug_.astro.mjs');
const _page14 = () => import('./pages/print/_slug_.astro.mjs');
const _page15 = () => import('./pages/privacy-policy.astro.mjs');
const _page16 = () => import('./pages/recipes.astro.mjs');
const _page17 = () => import('./pages/robots.txt.astro.mjs');
const _page18 = () => import('./pages/search.astro.mjs');
const _page19 = () => import('./pages/sitemap.xml.astro.mjs');
const _page20 = () => import('./pages/terms-of-use.astro.mjs');
const _page21 = () => import('./pages/_slug_.astro.mjs');
const _page22 = () => import('./pages/index.astro.mjs');
const pageMap = new Map([
    ["node_modules/@astrojs/cloudflare/dist/entrypoints/image-endpoint.js", _page0],
    ["src/pages/404.astro", _page1],
    ["src/pages/about-us.astro", _page2],
    ["src/pages/api/categories.ts", _page3],
    ["src/pages/api/recipes/[slug].ts", _page4],
    ["src/pages/api/recipes.ts", _page5],
    ["src/pages/author/[slug].astro", _page6],
    ["src/pages/category/[slug].astro", _page7],
    ["src/pages/contact-us.astro", _page8],
    ["src/pages/cookie-policy.astro", _page9],
    ["src/pages/copyright-policy.astro", _page10],
    ["src/pages/disclaimer.astro", _page11],
    ["src/pages/gdpr-policy.astro", _page12],
    ["src/pages/page/[slug].astro", _page13],
    ["src/pages/print/[slug].astro", _page14],
    ["src/pages/privacy-policy.astro", _page15],
    ["src/pages/recipes.astro", _page16],
    ["src/pages/robots.txt.ts", _page17],
    ["src/pages/search.astro", _page18],
    ["src/pages/sitemap.xml.ts", _page19],
    ["src/pages/terms-of-use.astro", _page20],
    ["src/pages/[slug].astro", _page21],
    ["src/pages/index.astro", _page22]
]);

const _manifest = Object.assign(manifest, {
    pageMap,
    serverIslandMap,
    renderers,
    actions: () => import('./noop-entrypoint.mjs'),
    middleware: () => import('./_astro-internal_middleware.mjs')
});
const _args = undefined;
const _exports = createExports(_manifest);
const __astrojsSsrVirtualEntry = _exports.default;
const _start = 'start';
if (Object.prototype.hasOwnProperty.call(serverEntrypointModule, _start)) {
	serverEntrypointModule[_start](_manifest, _args);
}

export { __astrojsSsrVirtualEntry as default, pageMap };
