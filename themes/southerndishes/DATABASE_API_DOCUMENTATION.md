# ChefTaling Database & API Documentation

Complete guide to database tables, API endpoints, and how to manage your recipe website data.

---

## Table of Contents

1. [Database Tables](#database-tables)
2. [API Authentication](#api-authentication)
3. [API Endpoints](#api-endpoints)
4. [Common Use Cases](#common-use-cases)
5. [Database Direct Access](#database-direct-access)

---

## Database Tables

### 1. **Recipes Table**

Stores all recipe data including content, images, and metadata.

**Table Schema:**
```sql
CREATE TABLE recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,              -- Pinterest-specific image URL
  pin_description TEXT,        -- Pinterest-specific description
  slug TEXT UNIQUE NOT NULL,   -- URL-friendly identifier
  article_content TEXT NOT NULL,  -- HTML content of the article
  featured_image TEXT NOT NULL,   -- Main recipe image URL
  recipe_json TEXT NOT NULL,      -- JSON with ingredients, instructions, etc.
  category_id INTEGER,            -- FK to categories table
  author_id INTEGER,              -- FK to authors table
  status TEXT DEFAULT 'draft',    -- 'draft' or 'published'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES authors(id)
);
```

**recipe_json Structure:**
```json
{
  "name": "Chocolate Chip Cookies",
  "summary": "Best chocolate chip cookies ever!",
  "servings": "24 cookies",
  "prep_time": "15",
  "cook_time": "12",
  "total_time": "27",
  "calories": "150",
  "course": "Dessert",
  "cuisine": "American",
  "keywords": ["cookies", "chocolate", "dessert"],
  "notes": "Store in airtight container for up to 1 week",
  "ingredients": [
    {
      "amount": "2",
      "unit": "cups",
      "name": "all-purpose flour"
    },
    {
      "amount": "1",
      "unit": "cup",
      "name": "chocolate chips"
    }
  ],
  "instructions": [
    "Preheat oven to 350°F",
    "Mix dry ingredients",
    "Add chocolate chips",
    "Bake for 12 minutes"
  ]
}
```

**Indexes:**
- `idx_recipes_slug` on `slug`
- `idx_recipes_category` on `category_id`
- `idx_recipes_status` on `status`
- `idx_recipes_author_id` on `author_id`

---

### 2. **Categories Table**

Organizes recipes by type (Desserts, Main Dishes, Appetizers, etc.)

**Table Schema:**
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

**Example Data:**
```json
{
  "id": 1,
  "name": "Desserts",
  "slug": "desserts",
  "description": "Sweet treats and baked goods"
}
```

**Index:**
- `idx_categories_slug` on `slug`

---

### 3. **Authors Table**

Stores recipe creator/author information.

**Table Schema:**
```sql
CREATE TABLE authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  title TEXT,                    -- e.g., "Recipe Creator", "Food Blogger"
  image_url TEXT,                -- Author profile image
  showcase_image TEXT,           -- Separate image for about page
  bio TEXT,                      -- Author biography
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Example Data:**
```json
{
  "id": 2,
  "name": "Elysia Thompson",
  "slug": "elysia-thompson",
  "title": "Recipe Creator & Food Blogger",
  "image_url": "https://example.com/elysia-profile.jpg",
  "showcase_image": "https://example.com/elysia-showcase.jpg",
  "bio": "Passionate about creating delicious recipes..."
}
```

**Index:**
- `idx_authors_slug` on `slug`

---

### 4. **Redirects Table**

Manages URL redirects for deleted or renamed recipes. Supports multiple old URLs redirecting to one new URL.

**Table Schema:**
```sql
CREATE TABLE redirects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  old_slug TEXT UNIQUE NOT NULL,
  new_url TEXT NOT NULL,
  redirect_type INTEGER DEFAULT 301,  -- HTTP status code (301, 302, etc.)
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Example Data:**
```json
[
  {
    "id": 1,
    "old_slug": "chocolate-chip-cookies-v1",
    "new_url": "/chocolate-chip-cookies/",
    "redirect_type": 301
  },
  {
    "id": 2,
    "old_slug": "old-chocolate-cookies",
    "new_url": "/chocolate-chip-cookies/",
    "redirect_type": 301
  }
]
```

**Redirect Types:**
- **301** - Permanent redirect (recommended for SEO)
- **302** - Temporary redirect

**Index:**
- `idx_redirects_old_slug` on `old_slug`

---

### 5. **Settings Table**

Site-wide configuration settings.

**Table Schema:**
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

**Default Settings:**
```json
{
  "site_domain": "cheftaling.com",
  "site_name": "ChefTaling",
  "site_description": "Delicious recipes and cooking inspiration",
  "contact_email": "contact@cheftaling.com",
  "site_logo": "",
  "facebook_url": "https://facebook.com/cheftaling",
  "pinterest_url": "https://pinterest.com/cheftaling"
}
```

**Index:**
- `idx_settings_key` on `key`

---

### 6. **Pages Table**

Static content pages (About Us, Contact, Privacy Policy, etc.)

**Table Schema:**
```sql
CREATE TABLE pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  content TEXT NOT NULL,         -- HTML content
  meta_description TEXT,
  status TEXT DEFAULT 'published',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_pages_slug` on `slug`
- `idx_pages_status` on `status`

---

## API Authentication

All write operations (POST, PUT, DELETE) require authentication using a Bearer token.

### Setting Up API Token

1. **Set environment variable in Cloudflare:**
   ```bash
   wrangler secret put API_TOKEN
   ```
   Enter your secure token when prompted.

2. **Use token in API requests:**
   ```bash
   Authorization: Bearer YOUR_API_TOKEN
   ```

### Example with cURL:
```bash
curl -H "Authorization: Bearer your-secret-token" \
     https://cheftaling.com/api/recipes
```

---

## API Endpoints

### Base URL
- **Production:** `https://cheftaling.com/api`
- **Local Development:** `http://localhost:4321/api`

---

### 📝 Recipes API

#### **GET /api/recipes**

Fetch recipes with pagination, filtering, and search.

**Authentication:** Required

**Query Parameters:**
- `page` (optional) - Page number (default: 1)
- `limit` (optional) - Items per page (default: 12)
- `category` (optional) - Filter by category slug
- `search` (optional) - Search recipes by title

**Example Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "https://cheftaling.com/api/recipes?page=1&limit=10&category=desserts"
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "Chocolate Chip Cookies",
      "slug": "chocolate-chip-cookies",
      "featured_image": "https://...",
      "status": "published",
      "category_id": 2,
      "author_id": 1,
      "created_at": "2025-12-01 10:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "hasMore": true
  }
}
```

---

#### **GET /api/recipes/[slug]**

Get a single recipe by slug.

**Authentication:** Not required

**Example Request:**
```bash
curl "https://cheftaling.com/api/recipes/chocolate-chip-cookies"
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "recipe": {
      "id": 1,
      "title": "Chocolate Chip Cookies",
      "slug": "chocolate-chip-cookies",
      "article_content": "<p>These are the best...</p>",
      "featured_image": "https://...",
      "recipe_json": "{...}",
      "status": "published",
      "category": {
        "id": 2,
        "name": "Desserts",
        "slug": "desserts"
      },
      "author": {
        "id": 1,
        "name": "Chef Name",
        "slug": "chef-name"
      }
    },
    "relatedRecipes": [...]
  }
}
```

---

#### **POST /api/recipes**

Create a new recipe.

**Authentication:** Required

**Required Fields:**
- `title` (string)
- `slug` (string) - Auto-incremented if exists (e.g., slug-1, slug-2)
- `article_content` (string) - HTML content
- `featured_image` (string) - Image URL
- `recipe_json` (object) - Recipe data
- `author_id` (number)

**Optional Fields:**
- `pin_image` (string)
- `pin_description` (string)
- `category_id` (number)
- `status` (string) - "draft" or "published" (default: "draft")
- `created_at` (string) - Format: "YYYY-MM-DD HH:MM:SS"

**Example Request:**
```bash
curl -X POST "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Chocolate Chip Cookies",
       "slug": "chocolate-chip-cookies",
       "article_content": "<p>These cookies are amazing...</p>",
       "featured_image": "https://example.com/cookies.jpg",
       "recipe_json": {
         "name": "Chocolate Chip Cookies",
         "summary": "Best cookies ever",
         "servings": "24",
         "prep_time": "15",
         "cook_time": "12",
         "total_time": "27",
         "ingredients": [
           {"amount": "2", "unit": "cups", "name": "flour"}
         ],
         "instructions": ["Mix ingredients", "Bake"]
       },
       "author_id": 1,
       "category_id": 2,
       "status": "published"
     }'
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "title": "Chocolate Chip Cookies",
    "slug": "chocolate-chip-cookies",
    "status": "published",
    "created_at": "2025-12-07 12:00:00"
  },
  "generated_slug": "chocolate-chip-cookies"
}
```

---

#### **PUT /api/recipes**

Update an existing recipe.

**Authentication:** Required

**Required Field:**
- `id` (number) - Recipe ID to update

**Optional Fields** (only include fields you want to update):
- `title`
- `slug`
- `article_content`
- `featured_image`
- `pin_image`
- `pin_description`
- `recipe_json`
- `category_id`
- `status`
- `author_id`

**Example Request (Change Recipe Status):**
```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "status": "published"
     }'
```

**Example Request (Update Multiple Fields):**
```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "title": "Updated Cookie Recipe",
       "status": "published",
       "featured_image": "https://example.com/new-image.jpg"
     }'
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "title": "Updated Cookie Recipe",
    "status": "published",
    "featured_image": "https://example.com/new-image.jpg",
    "updated_at": "2025-12-07 13:00:00"
  }
}
```

---

### 🔀 Redirects API

#### **GET /api/redirects**

Get all redirects or check a specific redirect.

**Authentication:** Required

**Query Parameters:**
- `old_slug` (optional) - Check if a specific old slug has a redirect

**Example Request (Get All Redirects):**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "https://cheftaling.com/api/redirects"
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "old_slug": "chocolate-chip-cookies-v1",
      "new_url": "/chocolate-chip-cookies/",
      "redirect_type": 301,
      "created_at": "2025-12-07 10:00:00"
    },
    {
      "id": 2,
      "old_slug": "old-cookies",
      "new_url": "/chocolate-chip-cookies/",
      "redirect_type": 301,
      "created_at": "2025-12-07 10:05:00"
    }
  ]
}
```

**Example Request (Check Specific Redirect):**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "https://cheftaling.com/api/redirects?old_slug=old-cookies"
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "old_slug": "old-cookies",
    "new_url": "/chocolate-chip-cookies/"
  }
}
```

---

#### **POST /api/redirects**

Add single or multiple redirects.

**Authentication:** Required

**Request Body (Single Redirect):**
```json
{
  "old_slug": "old-recipe-name",
  "new_url": "/new-recipe-name/"
}
```

**Request Body (Multiple Redirects):**
```json
{
  "old_slugs": [
    "chocolate-chip-cookies-v1",
    "chocolate-chip-cookies-v2",
    "old-chocolate-cookies"
  ],
  "new_url": "/chocolate-chip-cookies/"
}
```

**Example Request (Single Redirect):**
```bash
curl -X POST "https://cheftaling.com/api/redirects" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "old_slug": "old-brownies",
       "new_url": "/fudge-brownies/"
     }'
```

**Example Response:**
```json
{
  "success": true,
  "message": "Redirect added: old-brownies → /fudge-brownies/",
  "data": {
    "old_slug": "old-brownies",
    "new_url": "/fudge-brownies/"
  }
}
```

**Example Request (Multiple Redirects):**
```bash
curl -X POST "https://cheftaling.com/api/redirects" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "old_slugs": ["cookies-v1", "cookies-v2", "old-cookies"],
       "new_url": "/chocolate-chip-cookies/"
     }'
```

**Example Response:**
```json
{
  "success": true,
  "message": "Added 3 redirects to /chocolate-chip-cookies/",
  "data": {
    "old_slugs": ["cookies-v1", "cookies-v2", "old-cookies"],
    "new_url": "/chocolate-chip-cookies/",
    "count": 3
  }
}
```

---

#### **DELETE /api/redirects**

Delete a redirect.

**Authentication:** Required

**Query Parameters:**
- `old_slug` (required) - The old slug to remove

**Example Request:**
```bash
curl -X DELETE "https://cheftaling.com/api/redirects?old_slug=old-cookies" \
     -H "Authorization: Bearer YOUR_TOKEN"
```

**Example Response:**
```json
{
  "success": true,
  "message": "Redirect deleted: old-cookies"
}
```

---

### 📂 Categories API

#### **GET /api/categories**

Get all categories.

**Authentication:** Not required

**Example Request:**
```bash
curl "https://cheftaling.com/api/categories"
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Appetizers",
      "slug": "appetizers",
      "description": "Starters and small bites",
      "created_at": "2025-12-01 10:00:00"
    },
    {
      "id": 2,
      "name": "Desserts",
      "slug": "desserts",
      "description": "Sweet treats",
      "created_at": "2025-12-01 10:00:00"
    }
  ]
}
```

---

## Common Use Cases

### 1. Publish a Draft Recipe

Change a recipe from "draft" to "published" status:

```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "status": "published"
     }'
```

---

### 2. Unpublish a Recipe (Soft Delete)

Change status to "draft" to hide from public:

```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "status": "draft"
     }'
```

---

### 3. Delete Recipe and Add Redirect

**Step 1:** Unpublish the recipe
```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"id": 123, "status": "draft"}'
```

**Step 2:** Add redirect from old slug to new URL
```bash
curl -X POST "https://cheftaling.com/api/redirects" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "old_slug": "old-recipe-slug",
       "new_url": "/new-recipe-slug/"
     }'
```

---

### 4. Consolidate Multiple Recipe Versions

Redirect multiple old versions to one canonical recipe:

```bash
curl -X POST "https://cheftaling.com/api/redirects" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "old_slugs": [
         "chocolate-cookies-2023",
         "chocolate-cookies-v1",
         "old-chocolate-cookies"
       ],
       "new_url": "/ultimate-chocolate-cookies/"
     }'
```

---

### 5. Update Recipe Category

Move a recipe to a different category:

```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "category_id": 5
     }'
```

---

### 6. Update Recipe Image

Change the featured image:

```bash
curl -X PUT "https://cheftaling.com/api/recipes" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "id": 123,
       "featured_image": "https://cdn.example.com/new-image.jpg"
     }'
```

---

## Database Direct Access

For advanced operations, you can use Wrangler CLI to directly access the D1 database.

### Execute SQL Commands

**Local Database:**
```bash
wrangler d1 execute recipe-db --local --command "SELECT * FROM recipes WHERE status = 'published'"
```

**Production Database:**
```bash
wrangler d1 execute recipe-db --remote --command "SELECT * FROM recipes WHERE status = 'published'"
```

---

### Common SQL Operations

#### Update Recipe Status
```bash
wrangler d1 execute recipe-db --remote --command "
  UPDATE recipes
  SET status = 'published'
  WHERE id = 123
"
```

#### Add Redirect
```bash
wrangler d1 execute recipe-db --remote --command "
  INSERT INTO redirects (old_slug, new_url, redirect_type)
  VALUES ('old-cookies', '/chocolate-chip-cookies/', 301)
"
```

#### Add Multiple Redirects
```bash
wrangler d1 execute recipe-db --remote --command "
  INSERT INTO redirects (old_slug, new_url, redirect_type) VALUES
    ('cookies-v1', '/chocolate-chip-cookies/', 301),
    ('cookies-v2', '/chocolate-chip-cookies/', 301),
    ('old-cookies', '/chocolate-chip-cookies/', 301)
"
```

#### Get All Redirects
```bash
wrangler d1 execute recipe-db --remote --command "SELECT * FROM redirects"
```

#### Delete Redirect
```bash
wrangler d1 execute recipe-db --remote --command "
  DELETE FROM redirects WHERE old_slug = 'old-cookies'
"
```

---

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message here"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `201` - Created (for POST requests)
- `400` - Bad Request (missing required fields)
- `401` - Unauthorized (invalid or missing API token)
- `404` - Not Found
- `500` - Internal Server Error

---

## Need Help?

- **GitHub Issues:** https://github.com/dropanjani/cheftaling/issues
- **Email:** contact@cheftaling.com

---

**Last Updated:** December 7, 2025
**Version:** 1.0.0
