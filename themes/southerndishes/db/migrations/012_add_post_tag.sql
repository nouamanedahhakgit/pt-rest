-- Migration: Add post_tag column to recipes table
-- Date: 2026-01-03
-- Description: Adds post_tag field to store tags/keywords for recipes

ALTER TABLE recipes ADD COLUMN post_tag TEXT;

-- Create index for post_tag search optimization
CREATE INDEX IF NOT EXISTS idx_recipes_post_tag ON recipes(post_tag);
