-- ============================================
-- COMPLETE DATABASE SCHEMA FOR CHEFTALING
-- ============================================
-- This file contains all tables needed for the recipe website
-- Run this to set up a fresh D1 database with all tables

-- ============================================
-- 1. CATEGORIES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);

-- ============================================
-- 2. AUTHORS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  title TEXT,
  image_url TEXT,
  showcase_image TEXT,
  bio TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_authors_slug ON authors(slug);

-- ============================================
-- 3. RECIPES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,
  pin_description TEXT,
  slug TEXT UNIQUE NOT NULL,
  article_content TEXT NOT NULL,
  featured_image TEXT NOT NULL,
  recipe_json TEXT NOT NULL,
  category_id INTEGER,
  author_id INTEGER,
  status TEXT DEFAULT 'draft',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES authors (id)
);

CREATE INDEX IF NOT EXISTS idx_recipes_slug ON recipes(slug);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category_id);
CREATE INDEX IF NOT EXISTS idx_recipes_status ON recipes(status);
CREATE INDEX IF NOT EXISTS idx_recipes_author_id ON recipes(author_id);

-- ============================================
-- 4. SETTINGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);

-- ============================================
-- 5. PAGES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,
  meta_description TEXT,
  status TEXT DEFAULT 'published',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pages_slug ON pages(slug);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);

-- ============================================
-- 6. REDIRECTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS redirects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  old_slug TEXT UNIQUE NOT NULL,
  new_url TEXT NOT NULL,
  redirect_type INTEGER DEFAULT 301,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_redirects_old_slug ON redirects(old_slug);

-- ============================================
-- 7. CONTACT SUBMISSIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS contact_submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT DEFAULT 'new',
  ip_address TEXT,
  user_agent TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact_submissions_status ON contact_submissions(status);
CREATE INDEX IF NOT EXISTS idx_contact_submissions_created_at ON contact_submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_contact_submissions_email ON contact_submissions(email);

-- ============================================
-- DEFAULT SETTINGS DATA
-- ============================================
INSERT OR IGNORE INTO settings (key, value, description) VALUES
  ('site_domain', 'cheftaling.com', 'Main site domain (without https:// or trailing slash)'),
  ('site_name', 'ChefTaling', 'Site name'),
  ('site_description', 'Delicious recipes and cooking inspiration', 'Site description for SEO'),
  ('contact_email', 'contact@cheftaling.com', 'Contact email address'),
  ('site_logo', '', 'Site logo URL (leave empty to use letter icon)'),
  ('facebook_url', 'https://facebook.com', 'Facebook page URL'),
  ('pinterest_url', 'https://pinterest.com', 'Pinterest profile URL'),
  ('custom_head_code', '', 'Custom HTML/JS code to inject in <head> section'),
  ('custom_body_top_code', '', 'Custom HTML/JS code to inject at the top of <body>'),
  ('custom_body_bottom_code', '', 'Custom HTML/JS code to inject at the bottom of <body>'),
  ('custom_footer_code', '', 'Custom HTML/JS code to inject inside <footer> section');

-- ============================================
-- SCHEMA SETUP COMPLETE
-- ============================================
