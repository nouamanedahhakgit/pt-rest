-- Add Amazon affiliate products table
-- This table stores Amazon products that can be displayed in recipe articles

CREATE TABLE IF NOT EXISTS amazon_products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  image_url TEXT NOT NULL,
  price TEXT,
  amazon_url TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'active',
  display_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_amazon_products_status ON amazon_products(status);

CREATE INDEX IF NOT EXISTS idx_amazon_products_display_order ON amazon_products(display_order);

CREATE TABLE IF NOT EXISTS recipe_products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recipe_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  display_order INTEGER DEFAULT 0,
  placement TEXT DEFAULT 'both',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES amazon_products(id) ON DELETE CASCADE,
  UNIQUE(recipe_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_products_recipe_id ON recipe_products(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_products_product_id ON recipe_products(product_id);
CREATE INDEX IF NOT EXISTS idx_recipe_products_placement ON recipe_products(placement);
ALTER TABLE amazon_products ADD COLUMN show_globally INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_amazon_products_show_globally ON amazon_products(show_globally);
