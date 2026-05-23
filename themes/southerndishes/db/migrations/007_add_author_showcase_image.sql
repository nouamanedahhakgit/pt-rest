-- Add showcase_image column to authors table for about page display
ALTER TABLE authors ADD COLUMN showcase_image TEXT;

-- Update existing authors with showcase images
UPDATE authors SET showcase_image = 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&h=1000&fit=crop' WHERE id = 1;
UPDATE authors SET showcase_image = 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=800&h=1000&fit=crop' WHERE id = 2;
