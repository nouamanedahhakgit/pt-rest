-- Add title column to authors table
ALTER TABLE authors ADD COLUMN title TEXT;

-- Update existing authors with titles
UPDATE authors SET title = 'Dessert Specialist & Pastry Chef' WHERE slug = 'chef-emma-williams';
UPDATE authors SET title = 'Professional Chef & Fusion Cuisine Expert' WHERE slug = 'chef-michael-chen';
UPDATE authors SET title = 'Home Cook & Food Blogger' WHERE slug = 'chef-sarah-johnson';
