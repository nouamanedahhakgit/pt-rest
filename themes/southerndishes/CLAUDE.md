# ChefTaling Project Memory & Rules

## Core Philosophy

Claude working on this project must always respect all existing connections between static files in our codebase. The framework used is **Astro**, so every edit, refactor, or new code snippet must preserve and align with Astro's file structure, routing conventions, and component organization. Never remove, rename, or change an import, path, or component reference unless the user explicitly asks for it, and even then, keep the overall project wiring consistent and functional.

When editing code, Claude should treat the current project structure as the source of truth. That means keeping all static assets (images, fonts, icons, etc.) correctly referenced, preserving relative and absolute paths, and maintaining layouts, components, and partials as they are wired together. If a change is requested in a specific file, Claude must apply the modification in a way that does **not break other connected files**, especially shared Astro components, layouts, and configuration files.

Claude should always act with a **minimal, safe-change mindset**. Prefer small, targeted edits over large rewrites. Do not introduce new frameworks or patterns that conflict with Astro, and do not assume files or folders that don't exist. If a task involves creating new code, Claude must follow the existing project style, naming conventions, and import patterns so that the new code naturally fits into the current structure without breaking links between static files.

**HOW YOU SHOULD ACT:** Claude must behave like a careful Astro project maintainer: protect the integrity of the file tree, keep all static file references valid, ensure that component and route connections remain correct, and always implement edits in a way that respects and maintains the project's existing architecture. When in doubt, preserve current connections and limit changes strictly to what the user has specified.

---

## 1. Technology Stack & Architecture

### Core Technologies
- **Framework**: Astro 5+ (SSR mode with `output: 'server'`)
- **Adapter**: Cloudflare Pages (`@astrojs/cloudflare`)
- **Database**: Cloudflare D1 (SQLite)
- **Styling**: Tailwind CSS 3.4+
- **Runtime**: TypeScript with strict type checking
- **Deployment**: Cloudflare Pages + Wrangler CLI

### Key Dependencies
```json
{
  "@astrojs/cloudflare": "^12.6.11",
  "@astrojs/tailwind": "^6.0.2",
  "astro": "^5.16.0",
  "tailwindcss": "^3.4.18",
  "wrangler": "^4.50.0"
}
```

### Platform Proxy
- Cloudflare platform proxy is **ENABLED** in `astro.config.mjs`
- This allows local development with D1 database access
- Database binding is available via `Astro.locals.runtime.env.DB`

---

## 2. Project Structure & File Organization

### Directory Layout
```
cheftaling/
├── src/
│   ├── components/          # Reusable Astro components
│   │   ├── RecipeCard.astro
│   │   ├── RecipeDetails.astro
│   │   └── RecipeGrid.astro
│   ├── layouts/            # Page layouts
│   │   └── Layout.astro    # Main layout with header/footer
│   ├── pages/              # File-based routing
│   │   ├── api/           # API endpoints
│   │   │   ├── recipes.ts
│   │   │   ├── recipes/[slug].ts
│   │   │   └── categories.ts
│   │   ├── category/      # Category pages
│   │   │   └── [slug].astro
│   │   ├── author/        # Author pages
│   │   │   └── [slug].astro
│   │   ├── page/          # Static pages
│   │   │   └── [slug].astro
│   │   ├── print/         # Print-friendly recipe pages
│   │   │   └── [slug].astro
│   │   ├── index.astro    # Homepage
│   │   ├── [slug].astro   # Recipe detail pages
│   │   ├── recipes.astro  # All recipes listing
│   │   ├── about-us.astro
│   │   ├── contact-us.astro
│   │   ├── privacy-policy.astro
│   │   ├── terms-of-use.astro
│   │   ├── gdpr-policy.astro
│   │   ├── cookie-policy.astro
│   │   ├── copyright-policy.astro
│   │   ├── disclaimer.astro
│   │   ├── sitemap.xml.ts
│   │   └── robots.txt.ts
│   ├── lib/               # Utilities and services
│   │   ├── database.ts    # DatabaseService class
│   │   └── utils.ts       # Helper functions
│   ├── types/             # TypeScript definitions
│   │   ├── recipe.ts      # Recipe, Category, Author types
│   │   └── cloudflare.ts  # D1Database type
│   └── styles/            # Global styles
│       └── global.css     # Tailwind + custom CSS
├── db/
│   ├── migrations/        # Database schema migrations
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_authors.sql
│   │   ├── 003_add_author_title.sql
│   │   ├── 004_add_settings.sql
│   │   └── 005_add_pages.sql
│   └── seeds/             # Sample data
├── public/                # Static assets (images, favicons)
├── astro.config.mjs       # Astro configuration
├── tailwind.config.mjs    # Tailwind configuration
├── wrangler.toml          # Cloudflare configuration
└── package.json
```

### Critical File Organization Rules
1. **Never move or rename** core directories (`src/`, `db/`, `public/`)
2. **Components go in `src/components/`** - reusable Astro components only
3. **Layouts go in `src/layouts/`** - page layout templates only
4. **Pages use file-based routing** - `src/pages/[slug].astro` becomes `/{slug}/`
5. **API routes end in `.ts`** - `src/pages/api/*.ts`
6. **Utilities in `src/lib/`** - shared TypeScript logic
7. **Types in `src/types/`** - TypeScript interfaces and types

---

## 3. Database Architecture

### Schema Overview
The D1 database has **5 core tables**:

#### 1. Categories Table
```sql
CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- **Purpose**: Organize recipes (Desserts, Main Dishes, Appetizers, etc.)
- **Key Index**: `idx_categories_slug` on `slug`

#### 2. Authors Table
```sql
CREATE TABLE authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  title TEXT,              -- e.g., "Recipe Creator", "Food Blogger"
  image_url TEXT,
  bio TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- **Purpose**: Store author/creator information
- **Key Index**: `idx_authors_slug` on `slug`

#### 3. Recipes Table
```sql
CREATE TABLE recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,          -- Pinterest-specific image
  pin_description TEXT,    -- Pinterest-specific description
  slug TEXT UNIQUE NOT NULL,
  article_content TEXT NOT NULL,  -- HTML content
  featured_image TEXT NOT NULL,
  recipe_json TEXT NOT NULL,      -- JSON-encoded RecipeData
  category_id INTEGER,
  author_id INTEGER,
  status TEXT DEFAULT 'draft',    -- 'draft' or 'published'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES authors(id)
);
```
- **Purpose**: Store recipe data
- **Key Indexes**:
  - `idx_recipes_slug` on `slug`
  - `idx_recipes_category` on `category_id`
  - `idx_recipes_status` on `status`
  - `idx_recipes_author_id` on `author_id`

#### 4. Settings Table
```sql
CREATE TABLE settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- **Purpose**: Site configuration (site_name, site_domain, site_logo, etc.)
- **Default Settings**:
  - `site_domain`: 'cheftaling.com'
  - `site_name`: 'ChefTaling'
  - `site_description`: 'Delicious recipes and cooking inspiration'
  - `contact_email`: 'contact@cheftaling.com'
  - `site_logo`: '' (empty = use letter icon)
- **Key Index**: `idx_settings_key` on `key`

#### 5. Pages Table
```sql
CREATE TABLE pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  content TEXT NOT NULL,
  meta_description TEXT,
  status TEXT DEFAULT 'published',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- **Purpose**: Static content pages (About Us, Contact, etc.)
- **Key Indexes**:
  - `idx_pages_slug` on `slug`
  - `idx_pages_status` on `status`

### Recipe JSON Structure
The `recipe_json` field stores structured recipe data:
```typescript
{
  name: string;
  summary: string;
  servings: string;
  prep_time: string;      // In minutes
  cook_time: string;      // In minutes
  total_time: string;     // In minutes
  calories: string;
  course: string;         // e.g., "Dessert", "Main Course"
  cuisine: string;        // e.g., "American", "Italian"
  keywords: string[];
  notes: string;
  ingredients: {
    amount: string;
    unit: string;
    name: string;
  }[];
  instructions: string[];
}
```

### DatabaseService Methods
The `DatabaseService` class (`src/lib/database.ts`) provides:
- `getRecipeBySlug(slug)` - Get single recipe with category and author
- `getRecipes(limit?, offset?)` - Get all published recipes
- `getRecipesByCategory(categorySlug, limit?, offset?)` - Filter by category
- `getFeaturedRecipes(limit)` - Get latest recipes
- `getCategories()` - Get all categories
- `getCategoryBySlug(slug)` - Get category by slug
- `getRelatedRecipes(categoryId, excludeId, limit)` - Get related recipes
- `searchRecipes(query, limit)` - Full-text search
- `generateUniqueSlug(baseSlug)` - Generate unique slug
- `getAuthors()` - Get all authors
- `getAuthorBySlug(slug)` - Get author by slug
- `getRecipesByAuthor(authorSlug, limit?, offset?)` - Filter by author
- `getRecipeCountByAuthor(authorSlug)` - Count author's recipes
- `getSetting(key)` - Get single setting
- `getAllSettings()` - Get all settings as object
- `updateSetting(key, value)` - Update setting
- `getPageBySlug(slug)` - Get static page
- `getAllPages()` - Get all published pages

---

## 4. Routing Patterns

### File-Based Routing
Astro uses file-based routing in the `src/pages/` directory:

| File Path | URL | Purpose |
|-----------|-----|---------|
| `index.astro` | `/` | Homepage |
| `recipes.astro` | `/recipes/` | All recipes listing |
| `[slug].astro` | `/{slug}/` | Recipe detail page |
| `category/[slug].astro` | `/category/{slug}/` | Category page |
| `author/[slug].astro` | `/author/{slug}/` | Author page |
| `page/[slug].astro` | `/page/{slug}/` | Static page |
| `print/[slug].astro` | `/print/{slug}/` | Print recipe page |
| `about-us.astro` | `/about-us/` | About page |
| `contact-us.astro` | `/contact-us/` | Contact page |
| `privacy-policy.astro` | `/privacy-policy/` | Privacy policy |
| `terms-of-use.astro` | `/terms-of-use/` | Terms of use |
| `gdpr-policy.astro` | `/gdpr-policy/` | GDPR policy |
| `cookie-policy.astro` | `/cookie-policy/` | Cookie policy |
| `copyright-policy.astro` | `/copyright-policy/` | Copyright policy |
| `disclaimer.astro` | `/disclaimer/` | Disclaimer |
| `api/recipes.ts` | `/api/recipes/` | Recipes API |
| `api/recipes/[slug].ts` | `/api/recipes/{slug}/` | Single recipe API |
| `api/categories.ts` | `/api/categories/` | Categories API |
| `sitemap.xml.ts` | `/sitemap.xml` | XML sitemap |
| `robots.txt.ts` | `/robots.txt` | Robots.txt |

### Dynamic Routes
- **`[slug].astro`** - Uses `Astro.params.slug` to fetch data
- **`prerender: false`** - Dynamic routes MUST have `export const prerender = false;`
- **404 Handling** - Use `return Astro.redirect('/404')` for missing content

### API Routes
- **API routes return `Response` objects**
- **Use proper HTTP status codes**: 200 (success), 404 (not found), 500 (error)
- **Always set `Content-Type: application/json`**
- **Add cache headers**: `Cache-Control: public, max-age=300` (5 minutes)
- **Example**:
```typescript
export const GET: APIRoute = async ({ locals }) => {
  const db = new DatabaseService(locals.runtime.env.DB);
  const recipes = await db.getRecipes();

  return new Response(JSON.stringify({
    success: true,
    data: recipes
  }), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300'
    }
  });
};
```

---

## 5. Component Patterns

### Layout Component (`src/layouts/Layout.astro`)
- **Single source of truth** for site-wide HTML structure
- **Props interface**:
  ```typescript
  {
    title: string;
    description?: string;
    image?: string;
    canonical?: string;
    jsonLd?: any;
  }
  ```
- **Includes**:
  - Global CSS import (`../styles/global.css`)
  - Google Fonts (Frank Ruhl Libre, Roboto)
  - SEO meta tags (Open Graph, Twitter Cards)
  - JSON-LD structured data
  - Sticky header with navigation
  - Footer with links
  - Mobile menu toggle script
- **Fetches settings** from database for site name, logo, domain
- **Never modify** the header/footer structure without explicit request

### RecipeCard Component (`src/components/RecipeCard.astro`)
- **Purpose**: Display recipe preview in grids/lists
- **Props**:
  ```typescript
  {
    recipe: Recipe;
    showCategory?: boolean;
    className?: string;
    imageSize?: 'small' | 'medium' | 'large';
  }
  ```
- **Features**:
  - Hover effects (scale, shadow)
  - Truncated description (120 chars)
  - Time and servings display
  - Category badge (optional)
  - Links to recipe detail page
- **Never remove** hover transitions or accessibility features

### RecipeDetails Component (`src/components/RecipeDetails.astro`)
- **Purpose**: Display full recipe card on detail pages
- **Props**:
  ```typescript
  {
    recipeData: RecipeData;
    slug?: string;
    recipeTitle?: string;
    featuredImage?: string;
    pinImage?: string;
    pinDescription?: string;
    className?: string;
  }
  ```
- **Features**:
  - Print button (`/print/{slug}/`)
  - Pinterest share button
  - Recipe meta (prep time, cook time, servings, calories)
  - Ingredients list with checkboxes
  - Step-by-step instructions
  - Recipe notes
- **Print functionality** - Links to print-optimized page

### RecipeGrid Component (`src/components/RecipeGrid.astro`)
- **Purpose**: Grid layout for recipe listings
- **Responsive**: 1 column (mobile), 2 columns (tablet), 3 columns (desktop)

---

## 6. Styling Conventions

### Tailwind Configuration
- **Font Families**:
  - `font-sans`: Roboto (body text)
  - `font-serif` / `font-playfair`: Frank Ruhl Libre (headings)
- **Color Scheme**:
  - Primary: Teal shades (`brand-500`: #3ae6c8, `brand-600`, `brand-700`)
  - Secondary: Gray shades (`gray-50` to `gray-900`)
  - Accent: Red (`red-600` for Pinterest)
- **Custom Classes** (defined in `src/styles/global.css`):
  - `.recipe-gradient` - Teal gradient background
  - `.btn-primary` - Primary button style
  - `.btn-secondary` - Secondary button style
  - `.loading-skeleton` - Loading animation
  - `.focus-ring` - Accessible focus states

### Typography Hierarchy
- **Headings**: Use Frank Ruhl Libre (`font-playfair`)
- **Body Text**: Use Roboto (`font-sans`)
- **Font Sizes**:
  - H1: `text-4xl md:text-5xl lg:text-6xl`
  - H2: `text-3xl`
  - H3: `text-xl`
  - Body: `text-base` (16px)

### Article Content Styling
The `[slug].astro` page includes extensive inline `<style is:global>` for article content:
- **H2 headings**: Bold, gradient text, uppercase
- **Lists**: Custom bullets (orange circles) and numbered lists (bold numbers)
- **Special sections**: Yellow lightbulb-style tip boxes
- **Links**: Orange underline with hover effects
- **Responsive**: Mobile-first with breakpoints at 768px and 480px
- **NEVER MODIFY** these styles without explicit request - they're critical for content display

### Print Styles
- **Print button** triggers browser print dialog
- **Hides** navigation, footer, sidebars, buttons
- **Shows** only recipe card content
- **Optimized** for black & white printing

---

## 7. TypeScript Patterns

### Type Definitions (`src/types/recipe.ts`)
- **RecipeIngredient**: Ingredient structure
- **RecipeData**: Parsed recipe JSON
- **Recipe**: Database recipe row
- **Category**: Database category row
- **Author**: Database author row
- **RecipeWithData**: Recipe with parsed `recipe_data`
- **DatabaseSchema**: Schema type definitions
- **Component Props**: RecipeCardProps, RecipePageProps, etc.

### Type Safety Rules
1. **Always import types** from `src/types/recipe.ts`
2. **Use `RecipeWithData`** when recipe_json is parsed
3. **Use `Recipe`** when recipe_json is still a string
4. **DatabaseService** always returns typed results
5. **Astro.locals.runtime.env.DB** is typed as `D1Database`

### Utility Functions (`src/lib/utils.ts`)
- `formatTime(minutes)` - Format minutes to "Xh Ym" or "Xm"
- `createSlug(title)` - Generate URL-safe slug
- `truncateText(text, maxLength)` - Truncate with ellipsis
- `stripHtml(html)` - Remove HTML tags
- `generateRecipeJsonLd(recipe, url, imageUrl)` - Generate schema.org JSON-LD
- `formatIngredient(ingredient)` - Format ingredient display
- `calculateReadTime(content)` - Calculate reading time
- `getImageUrl(path, width?, height?)` - Build image URL with params

---

## 8. SEO & Meta Data Patterns

### JSON-LD Structured Data
Every recipe page includes **schema.org Recipe** markup:
```javascript
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  name: "Recipe Name",
  description: "Recipe summary",
  image: "featured_image_url",
  author: { "@type": "Person", "name": "Author Name" },
  prepTime: "PT15M",
  cookTime: "PT30M",
  totalTime: "PT45M",
  recipeYield: "4 servings",
  nutrition: { "@type": "NutritionInformation", calories: "250 calories" },
  recipeCategory: "Dessert",
  recipeCuisine: "American",
  keywords: "chocolate, cookies, dessert",
  recipeIngredient: ["2 cups flour", "..."],
  recipeInstructions: [
    { "@type": "HowToStep", position: 1, text: "Step 1..." }
  ]
}
```

### Open Graph & Twitter Cards
- **og:type**: "website"
- **og:title**: Recipe title or page title
- **og:description**: Recipe summary or page description
- **og:image**: Recipe featured image or default image
- **og:site_name**: Site name from settings
- **twitter:card**: "summary_large_image"

### Canonical URLs
- Always set canonical URL via `<link rel="canonical">`
- Use `Astro.url.toString()` or explicit URL

### Sitemaps & Robots.txt
- **`sitemap.xml.ts`**: Generate XML sitemap
- **`robots.txt.ts`**: Generate robots.txt
- Both should list all public URLs

---

## 9. Deployment & Environment

### Cloudflare Pages Deployment
1. **Build command**: `npm run build`
2. **Deploy command**: `wrangler pages deploy`
3. **Output directory**: `dist/`

### Database Management
- **Local development**:
  - `npm run db:migrate:local` - Run migrations locally
  - `npm run db:seed:local` - Seed local database
- **Production**:
  - `npm run db:migrate` - Run migrations on production
  - `npm run db:seed` - Seed production database

### Environment Variables
- **Database binding**: Handled via `wrangler.toml`
- **Database ID**: `d93eb0b2-cc9c-4841-89ef-5be433e53d31`
- **Binding name**: `DB`
- **Environments**: production, preview

### Wrangler Configuration
```toml
name = "recipe-website"
compatibility_date = "2023-05-18"
pages_build_output_dir = "dist"

[[d1_databases]]
binding = "DB"
database_name = "recipe-db"
database_id = "d93eb0b2-cc9c-4841-89ef-5be433e53d31"
```

---

## 10. Code Quality Standards

### Code Style
1. **Use TypeScript** for all `.ts` files
2. **Use interfaces** for component props
3. **Use async/await** for database queries
4. **Use try/catch** for error handling
5. **Use template literals** for multi-line strings
6. **Use destructuring** for props and objects

### Database Query Patterns
- **Always check** `Astro.locals.runtime?.env?.DB` exists
- **Always use** prepared statements with `.bind()`
- **Always handle** null/undefined results
- **Always use** indexes for performance
- **Always filter** by `status = 'published'` for public queries

### Error Handling
- **Pages**: Redirect to `/404` on errors
- **API routes**: Return JSON with `{ success: false, error: "message" }`
- **Console.error**: Log errors for debugging

### Accessibility
- **Alt text** on all images
- **ARIA labels** on icon-only buttons
- **Semantic HTML** (nav, main, footer, article, etc.)
- **Focus states** on interactive elements
- **Screen reader text** where needed

---

## 11. Critical Don'ts

### NEVER Do These Things Without Explicit Request:
1. **Change the Astro configuration** (`astro.config.mjs`)
2. **Modify Tailwind config** (`tailwind.config.mjs`)
3. **Change Wrangler settings** (`wrangler.toml`)
4. **Alter database schema** (migration files)
5. **Modify global CSS** extensively (`src/styles/global.css`)
6. **Change Layout component structure** (header, footer, navigation)
7. **Rename or move core directories** (`src/`, `db/`, `public/`)
8. **Change component file names** (breaks imports)
9. **Modify article content CSS** (critical for content display)
10. **Change slug generation logic** (breaks URLs)
11. **Remove database indexes** (breaks performance)
12. **Change font families** (brand consistency)
13. **Modify JSON-LD schema structure** (SEO impact)
14. **Change routing patterns** (breaks existing URLs)
15. **Remove error handling** (breaks robustness)

### Always Check Before:
- **Adding new dependencies** - Verify compatibility with Astro 5 + Cloudflare
- **Creating new database tables** - Check if existing tables can be extended
- **Adding new routes** - Verify no URL conflicts
- **Modifying shared components** - Check all usages first
- **Changing TypeScript types** - Verify no breaking changes

---

## 12. Development Workflow

### Local Development
1. Start dev server: `npm run dev`
2. Visit: `http://localhost:4321`
3. Database binding works automatically via platform proxy

### Adding New Recipes (Manual)
1. Insert into `recipes` table with proper JSON structure
2. Ensure `slug` is unique
3. Set `status = 'published'` to make visible
4. Link to `category_id` and `author_id` (optional)

### Adding New Categories
1. Insert into `categories` table
2. Ensure `slug` is unique
3. Update navigation in `Layout.astro` if needed

### Adding New Static Pages
1. Create `.astro` file in `src/pages/`
2. Use `Layout` component for consistency
3. Add link to footer if needed

### Modifying Settings
1. Use `DatabaseService.updateSetting(key, value)`
2. Settings are cached in Layout component
3. Restart dev server to see changes

---

## 13. Common Tasks & Patterns

### Task: Add a New Recipe Page Feature
1. Check if `RecipeDetails.astro` needs modification
2. Ensure changes don't break print styles
3. Test on mobile, tablet, desktop
4. Verify JSON-LD still validates

### Task: Modify Styling
1. Check if Tailwind utility classes can achieve it
2. If custom CSS needed, add to `global.css` or component `<style>`
3. Maintain mobile-first responsive approach
4. Test across all breakpoints

### Task: Add Database Field
1. Create new migration file in `db/migrations/`
2. Update TypeScript types in `src/types/`
3. Update `DatabaseService` methods if needed
4. Run migration: `npm run db:migrate:local`

### Task: Fix Bug
1. Identify affected files
2. Check if issue is in database query, component, or API
3. Add error handling if missing
4. Test fix thoroughly
5. Verify no regression in other features

---

## 14. Project-Specific Conventions

### Slug Generation
- **Always lowercase**
- **Replace spaces with hyphens**
- **Remove special characters** except hyphens
- **Ensure uniqueness** using `DatabaseService.generateUniqueSlug()`

### Image Handling
- **Featured images**: Full URL or absolute path
- **Pin images**: Optional, for Pinterest sharing
- **Image optimization**: Use `getImageUrl()` with width/height params
- **Alt text**: Always use recipe title or descriptive text

### Navigation Links
- **Header**: Home, Recipes, Desserts, Main Dishes, Appetizers
- **Footer**: Categories, Company (About, Contact, Disclaimer), Legal (Privacy, Terms, GDPR, Cookie, Copyright)
- **Mobile menu**: Collapsible, same structure as desktop

### Social Sharing
- **Pinterest**: Pin button on recipe header and recipe card
- **Facebook**: Link in footer
- **URL structure**: `/{slug}/` (no trailing category in URL)

---

## Summary

This is a **production-ready, SEO-optimized recipe website** built with modern web technologies. The architecture prioritizes:
- **Performance**: Edge deployment, optimized queries, caching
- **SEO**: JSON-LD, Open Graph, sitemaps, clean URLs
- **User Experience**: Responsive design, print support, mobile-first
- **Maintainability**: Clean architecture, TypeScript safety, minimal dependencies
- **Scalability**: D1 database, Cloudflare edge network

When working on this project, always prioritize **stability over innovation**. The current architecture works well and should only be changed with clear justification and user approval.
