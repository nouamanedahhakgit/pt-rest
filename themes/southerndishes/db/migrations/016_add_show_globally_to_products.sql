-- Add show_globally field to amazon_products table
-- This allows products to be displayed on all recipe pages automatically

ALTER TABLE amazon_products ADD COLUMN show_globally INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_amazon_products_show_globally ON amazon_products(show_globally);
