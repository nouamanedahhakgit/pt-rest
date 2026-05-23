-- Migration: Add custom code injection settings
-- Created: 2025-11-27
-- Purpose: Add settings for custom HTML/JS injection in head, body top, body bottom, and footer

INSERT INTO settings (key, value, description) VALUES
  ('custom_head_code', '', 'Custom HTML/JS code to inject in <head> section (meta tags, tracking, etc.)'),
  ('custom_body_top_code', '', 'Custom HTML/JS code to inject at the top of <body> (right after <body> opens)'),
  ('custom_body_bottom_code', '', 'Custom HTML/JS code to inject at the bottom of <body> (just before </body>)'),
  ('custom_footer_code', '', 'Custom HTML/JS code to inject inside <footer> section');
