-- Create redirects table for handling deleted recipe URLs
-- Multiple old slugs can redirect to the same new URL
CREATE TABLE redirects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  old_slug TEXT UNIQUE NOT NULL,
  new_url TEXT NOT NULL,
  redirect_type INTEGER DEFAULT 301,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create index on old_slug for fast lookups
CREATE INDEX idx_redirects_old_slug ON redirects(old_slug);

-- Example: Multiple old slugs redirecting to one new URL
-- INSERT INTO redirects (old_slug, new_url) VALUES ('chocolate-chip-cookies-v1', '/chocolate-chip-cookies/');
-- INSERT INTO redirects (old_slug, new_url) VALUES ('chocolate-chip-cookies-v2', '/chocolate-chip-cookies/');
-- INSERT INTO redirects (old_slug, new_url) VALUES ('old-chocolate-cookies', '/chocolate-chip-cookies/');
