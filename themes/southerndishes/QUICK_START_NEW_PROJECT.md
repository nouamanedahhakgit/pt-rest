# 🚀 Quick Start Guide for New Recipe Projects

Use these files to quickly set up a new recipe website with all features.

## 📦 What You Get

This setup includes **everything** from cheftaling/momdishmagic:

✅ **7 Database Tables** - Categories, Recipes, Authors, Settings, Pages, Redirects, Contact Submissions
✅ **RSS Feeds by Board Name** - Create separate feeds for Pinterest boards
✅ **Template Variables** - Use `{{site_name}}`, `{{site_domain}}`, `{{contact_email}}` in pages
✅ **Contact Form** - With rate limiting and submission tracking
✅ **URL Redirects** - Handle old recipe URLs gracefully
✅ **Custom Code Injection** - Add tracking codes, ads, etc.
✅ **Pinterest Optimization** - Pin images, descriptions, board names
✅ **API Endpoints** - Full REST API for recipes

---

## 🎯 Quick Setup (3 Files)

### 1. **Database Migration** → `000_COMPLETE_FRESH_INSTALL.sql`

**One command to create everything:**

```bash
# Local
wrangler d1 execute YOUR_DB_NAME --local --file=./db/migrations/000_COMPLETE_FRESH_INSTALL.sql

# Production
wrangler d1 execute YOUR_DB_NAME --remote --file=./db/migrations/000_COMPLETE_FRESH_INSTALL.sql
```

**What it creates:**
- ✅ 7 tables (categories, recipes, authors, settings, pages, redirects, contact_submissions)
- ✅ All indexes for performance
- ✅ Default settings (update with your info)
- ✅ Sample categories (Desserts, Dinners, Appetizers, Drinks)
- ✅ Sample author

---

### 2. **Code Implementation** → `SETUP_GUIDE.md`

Follow the detailed guide to implement:
- RSS feed routes (`src/pages/rss/`)
- Template variable utility (`src/lib/utils.ts`)
- Updated policy pages
- API endpoints with board_name support

**Time: ~15 minutes** of copy-paste from guide

---

### 3. **Incremental Changes** → `COMPLETE_SETUP_MIGRATION.sql`

For **existing projects**, use this file to add only the new features:
- Adds `board_name` column to recipes
- Safe to run on existing databases

---

## 📋 Database Schema Overview

### Tables Created

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **categories** | Recipe categories | name, slug |
| **recipes** | Recipe content & data | title, slug, board_name, recipe_json |
| **authors** | Recipe creators | name, slug, title, bio, showcase_image |
| **settings** | Site configuration | key, value (site_name, site_domain, etc.) |
| **pages** | Static pages (Privacy, Terms) | slug, content (supports variables) |
| **redirects** | URL redirects | old_slug, new_url |
| **contact_submissions** | Contact form data | name, email, subject, message, status |

### Key Features

**Recipes Table:**
```sql
- board_name TEXT        -- For RSS feeds (e.g., "desserts-board")
- pin_image TEXT         -- Pinterest-specific image
- pin_description TEXT   -- Pinterest-specific description
- recipe_json TEXT       -- Structured recipe data (JSON)
- article_content TEXT   -- Article HTML content
- author_id INTEGER      -- Links to authors table
- category_id INTEGER    -- Links to categories table
- status TEXT            -- 'draft' or 'published'
```

**Settings Table** (Pre-populated):
```
site_name              → "ChefTaling"
site_domain            → "cheftaling.com"
site_description       → "Delicious recipes..."
contact_email          → "contact@cheftaling.com"
site_logo              → (URL or empty for letter icon)
custom_head_code       → Custom <head> code
custom_body_top_code   → Code after <body>
custom_body_bottom_code → Code before </body>
custom_footer_code     → Code in <footer>
```

---

## 🎨 Customization After Install

### 1. Update Settings
```sql
UPDATE settings SET value = 'YourSiteName' WHERE key = 'site_name';
UPDATE settings SET value = 'yourdomain.com' WHERE key = 'site_domain';
UPDATE settings SET value = 'hello@yourdomain.com' WHERE key = 'contact_email';
```

### 2. Add Your Categories
```sql
INSERT INTO categories (name, slug, description) VALUES
  ('Your Category', 'your-category', 'Description here');
```

### 3. Add Your Authors
```sql
INSERT INTO authors (name, slug, title, bio, image_url) VALUES
  ('Your Name', 'your-name', 'Your Title', 'Your bio...', 'image-url');
```

### 4. Create Policy Pages
```sql
INSERT INTO pages (title, slug, content) VALUES
  ('Privacy Policy', 'privacy-policy', '<h2>Privacy Policy</h2><p>Welcome to {{site_name}}...</p>');
```

---

## 🔥 Advanced Features

### RSS Feeds by Board Name

**Set board names on recipes:**
```sql
UPDATE recipes SET board_name = 'pinterest-desserts' WHERE category_id = 1;
UPDATE recipes SET board_name = 'instagram-meals' WHERE category_id = 2;
```

**Access RSS feeds:**
- Index: `https://yourdomain.com/rss/`
- Feed: `https://yourdomain.com/rss/pinterest-desserts.xml`

### Template Variables in Pages

Use in page content (pages table):
- `{{site_name}}` → Replaced with site name
- `{{site_domain}}` → Replaced with domain
- `{{contact_email}}` → Replaced with email

### URL Redirects

```sql
INSERT INTO redirects (old_slug, new_url) VALUES
  ('old-recipe-name', '/new-recipe-name/');
```

Automatically redirects `/old-recipe-name/` → `/new-recipe-name/`

### Contact Form Submissions

View submissions:
```sql
SELECT * FROM contact_submissions ORDER BY created_at DESC;
```

Update status:
```sql
UPDATE contact_submissions SET status = 'read' WHERE id = 1;
```

---

## 📊 Verification Commands

**Check tables were created:**
```bash
wrangler d1 execute YOUR_DB_NAME --local --command="SELECT name FROM sqlite_master WHERE type='table';"
```

**Check default settings:**
```bash
wrangler d1 execute YOUR_DB_NAME --local --command="SELECT * FROM settings;"
```

**Check sample data:**
```bash
wrangler d1 execute YOUR_DB_NAME --local --command="SELECT * FROM categories;"
```

---

## 🆘 Troubleshooting

### Error: "table already exists"
You already have tables. Use `COMPLETE_SETUP_MIGRATION.sql` instead (adds only board_name).

### Error: "no such table"
Run the fresh install migration first.

### Settings not showing
Check: `await db.getAllSettings()` in your Astro pages.

---

## 📚 Files Reference

- **`000_COMPLETE_FRESH_INSTALL.sql`** - Full database setup (187 lines)
- **`COMPLETE_SETUP_MIGRATION.sql`** - Adds board_name only (for existing DBs)
- **`SETUP_GUIDE.md`** - Complete code implementation guide
- **`QUICK_START_NEW_PROJECT.md`** - This file!

---

## ✨ You're Ready!

After running the migration and following SETUP_GUIDE.md, your new project will have:

✅ Complete recipe database with all features
✅ RSS feeds for each board name
✅ Template variables in pages
✅ Contact form with tracking
✅ URL redirects
✅ Pinterest optimization
✅ Custom code injection
✅ API endpoints

**Time to first recipe:** ~20 minutes! 🎉

---

**Need help?** Check the reference projects:
- `/Users/anjani/Desktop/cheftaling/`
- `/Users/anjani/Desktop/momdishmagic/`
