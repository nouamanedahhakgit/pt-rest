-- Create categories table first (referenced by recipes)
CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create recipes table
CREATE TABLE recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,
  pin_description TEXT,
  slug TEXT UNIQUE NOT NULL,
  article_content TEXT NOT NULL,
  featured_image TEXT NOT NULL,
  recipe_json TEXT NOT NULL,
  category_id INTEGER,
  status TEXT DEFAULT 'draft',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
);

-- Create indexes for better performance
CREATE INDEX idx_recipes_slug ON recipes(slug);
CREATE INDEX idx_recipes_category ON recipes(category_id);
CREATE INDEX idx_recipes_status ON recipes(status);
CREATE INDEX idx_categories_slug ON categories(slug);