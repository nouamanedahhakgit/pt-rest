-- Create authors table
CREATE TABLE IF NOT EXISTS authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  image_url TEXT,
  bio TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Add author_id column to recipes table
ALTER TABLE recipes ADD COLUMN author_id INTEGER REFERENCES authors(id);

-- Create index for better query performance
CREATE INDEX idx_recipes_author_id ON recipes(author_id);
CREATE INDEX idx_authors_slug ON authors(slug);
