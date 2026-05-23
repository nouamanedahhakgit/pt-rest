-- Create settings table for site configuration
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Insert default domain setting
INSERT INTO settings (key, value, description) VALUES
  ('site_domain', 'cheftaling.com', 'Main site domain (without https:// or trailing slash)'),
  ('site_name', 'ChefTaling', 'Site name'),
  ('site_description', 'Delicious recipes and cooking inspiration', 'Site description for SEO'),
  ('contact_email', 'contact@cheftaling.com', 'Contact email address'),
  ('site_logo', '', 'Site logo URL (leave empty to use letter icon)');

-- Create index for faster key lookups
CREATE INDEX idx_settings_key ON settings(key);
