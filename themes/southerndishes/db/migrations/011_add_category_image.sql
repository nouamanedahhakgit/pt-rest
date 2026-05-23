-- Add image column to categories table
ALTER TABLE categories ADD COLUMN image TEXT;

-- Update existing categories with their images
UPDATE categories SET image = 'https://cheftaling.b-cdn.net/Untitled%20design%20(4)-min.png' WHERE slug = 'appetizers';
UPDATE categories SET image = 'https://cheftaling.b-cdn.net/Untitled%20design%20(3)-min.png' WHERE slug = 'desserts';
UPDATE categories SET image = 'https://cheftaling.b-cdn.net/Untitled%20design%20(7)-min.png' WHERE slug = 'dinners';
UPDATE categories SET image = 'https://cheftaling.b-cdn.net/Untitled%20design%20(5)-min.png' WHERE slug = 'drinks';
