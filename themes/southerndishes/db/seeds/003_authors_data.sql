-- Insert sample authors
INSERT INTO authors (name, slug, image_url, bio) VALUES
(
  'Chef Sarah Johnson',
  'chef-sarah-johnson',
  'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=400&fit=crop',
  'Passionate home cook and food blogger specializing in comfort food and family-friendly recipes. Over 10 years of experience sharing delicious recipes.'
),
(
  'Chef Michael Chen',
  'chef-michael-chen',
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop',
  'Professional chef with a love for fusion cuisine. Bringing restaurant-quality dishes to your home kitchen with easy-to-follow instructions.'
),
(
  'Chef Emma Williams',
  'chef-emma-williams',
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop',
  'Dessert specialist and pastry chef. Creating sweet masterpieces that are both beautiful and delicious. Follow along for baking tips and tricks!'
);

-- Update existing recipes to assign authors
UPDATE recipes SET author_id = 3 WHERE category_id = 1; -- Desserts to Emma (dessert specialist)
UPDATE recipes SET author_id = 2 WHERE category_id = 2; -- Main Dishes to Michael
UPDATE recipes SET author_id = 1 WHERE category_id = 3; -- Appetizers to Sarah
