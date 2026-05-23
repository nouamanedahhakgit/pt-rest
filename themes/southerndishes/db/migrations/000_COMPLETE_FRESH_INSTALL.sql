-- ====================================================================
-- COMPLETE FRESH INSTALL MIGRATION FOR RECIPE WEBSITE
-- ====================================================================
-- This is a comprehensive migration file that creates ALL tables
-- Use this for brand new projects - run this ONE file instead of
-- running migrations 001 through 010 individually
-- ====================================================================
-- Version: 1.0
-- Last Updated: December 11, 2025
-- Includes: All tables, indexes, default settings, and enhancements
-- ====================================================================

-- ====================================================================
-- 1. CATEGORIES TABLE
-- ====================================================================
CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  image TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_categories_slug ON categories(slug);

-- ====================================================================
-- 2. AUTHORS TABLE
-- ====================================================================
CREATE TABLE authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  title TEXT,                    -- e.g., "Recipe Creator", "Food Blogger"
  image_url TEXT,
  showcase_image TEXT,           -- For about page display
  bio TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_authors_slug ON authors(slug);

-- ====================================================================
-- 3. RECIPES TABLE
-- ====================================================================
CREATE TABLE recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,                -- Pinterest-specific image
  pin_description TEXT,          -- Pinterest-specific description
  board_name TEXT,               -- Board name for RSS feeds and organization
  slug TEXT UNIQUE NOT NULL,
  article_content TEXT NOT NULL, -- HTML article content
  featured_image TEXT NOT NULL,
  recipe_json TEXT NOT NULL,     -- JSON-encoded recipe data (ingredients, instructions, etc.)
  category_id INTEGER,
  author_id INTEGER,
  status TEXT DEFAULT 'draft',   -- 'draft' or 'published'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES authors(id)
);

-- Indexes for recipes table
CREATE INDEX idx_recipes_slug ON recipes(slug);
CREATE INDEX idx_recipes_category ON recipes(category_id);
CREATE INDEX idx_recipes_status ON recipes(status);
CREATE INDEX idx_recipes_author_id ON recipes(author_id);

-- ====================================================================
-- 4. SETTINGS TABLE
-- ====================================================================
CREATE TABLE settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_settings_key ON settings(key);

-- Insert default settings
INSERT INTO settings (key, value, description) VALUES
  ('site_domain', 'cheftaling.com', 'Main site domain (without https:// or trailing slash)'),
  ('site_name', 'ChefTaling', 'Site name'),
  ('site_description', 'Delicious recipes and cooking inspiration', 'Site description for SEO'),
  ('contact_email', 'contact@cheftaling.com', 'Contact email address'),
  ('site_logo', '', 'Site logo URL (leave empty to use letter icon)'),
  ('custom_head_code', '', 'Custom HTML/JS code to inject in <head> section (meta tags, tracking, etc.)'),
  ('custom_body_top_code', '', 'Custom HTML/JS code to inject at the top of <body> (right after <body> opens)'),
  ('custom_body_bottom_code', '', 'Custom HTML/JS code to inject at the bottom of <body> (just before </body>)'),
  ('custom_footer_code', '', 'Custom HTML/JS code to inject inside <footer> section');

-- ====================================================================
-- 5. PAGES TABLE
-- ====================================================================
CREATE TABLE pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,         -- Supports {{site_name}}, {{site_domain}}, {{contact_email}} variables
  meta_description TEXT,
  status TEXT DEFAULT 'published', -- 'draft' or 'published'
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pages_slug ON pages(slug);
CREATE INDEX idx_pages_status ON pages(status);

-- ====================================================================
-- 6. REDIRECTS TABLE
-- ====================================================================
CREATE TABLE redirects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  old_slug TEXT UNIQUE NOT NULL,
  new_url TEXT NOT NULL,
  redirect_type INTEGER DEFAULT 301,  -- 301 permanent, 302 temporary
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_redirects_old_slug ON redirects(old_slug);

-- ====================================================================
-- 7. CONTACT SUBMISSIONS TABLE
-- ====================================================================
CREATE TABLE contact_submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT DEFAULT 'new',      -- 'new', 'read', 'replied', 'archived'
  ip_address TEXT,
  user_agent TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contact_submissions_status ON contact_submissions(status);
CREATE INDEX idx_contact_submissions_created_at ON contact_submissions(created_at);
CREATE INDEX idx_contact_submissions_email ON contact_submissions(email);

-- ====================================================================
-- 8. SAMPLE DATA (Optional - can be removed for production)
-- ====================================================================

-- Sample Categories
INSERT INTO categories (name, slug, description, image) VALUES
  ('Desserts', 'desserts', 'Sweet treats and desserts', 'https://cheftaling.b-cdn.net/Untitled%20design%20(3)-min.png'),
  ('Dinners', 'dinners', 'Main course meals and dinner recipes', 'https://cheftaling.b-cdn.net/Untitled%20design%20(7)-min.png'),
  ('Appetizers', 'appetizers', 'Starters and appetizers', 'https://cheftaling.b-cdn.net/Untitled%20design%20(4)-min.png'),
  ('Drinks', 'drinks', 'Beverages and drink recipes', 'https://cheftaling.b-cdn.net/Untitled%20design%20(5)-min.png');

-- Sample Author
INSERT INTO authors (name, slug, title, bio) VALUES
  ('Chef Sarah', 'chef-sarah', 'Recipe Creator & Food Blogger',
   'Passionate about creating delicious and easy-to-follow recipes for home cooks.');

-- ====================================================================
-- MIGRATION COMPLETE!
-- ====================================================================
--
-- Next Steps:
-- 1. Update settings table with your site information
-- 2. Add your authors
-- 3. Create categories
-- 4. Add recipes
-- 5. Create policy pages (privacy-policy, terms-of-use, etc.)
--
-- Features Included:
-- ✅ Complete database schema (7 tables)
-- ✅ All indexes for performance
-- ✅ Default settings
-- ✅ RSS feed support via board_name
-- ✅ Template variables support ({{site_name}}, etc.)
-- ✅ Contact form with submissions tracking
-- ✅ URL redirects system
-- ✅ Custom code injection
-- ✅ Author showcase images
-- ✅ Pinterest optimization (pin_image, pin_description)
--
-- ====================================================================
