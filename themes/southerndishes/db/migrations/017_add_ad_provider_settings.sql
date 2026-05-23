-- Migration: Add Ad Provider Settings
-- Purpose: Add settings for switching between ad providers (Ezoic, HBAgency)

-- Ad provider setting (ezoic, hbagency, none)
INSERT OR IGNORE INTO settings (key, value, description) VALUES
  ('ad_provider', 'ezoic', 'Ad provider to use: ezoic, hbagency, or none');

-- Ezoic specific settings (placement IDs)
INSERT OR IGNORE INTO settings (key, value, description) VALUES
  ('ezoic_id_top', '101', 'Ezoic placement ID for top of page'),
  ('ezoic_id_under_title', '102', 'Ezoic placement ID for under page title'),
  ('ezoic_id_bottom', '103', 'Ezoic placement ID for bottom of page'),
  ('ezoic_id_sidebar', '104', 'Ezoic placement ID for sidebar'),
  ('ezoic_id_sidebar_middle', '105', 'Ezoic placement ID for sidebar middle'),
  ('ezoic_id_in_content_1', '109', 'Ezoic placement ID for in-content ad 1'),
  ('ezoic_id_in_content_2', '110', 'Ezoic placement ID for in-content ad 2'),
  ('ezoic_id_in_content_3', '111', 'Ezoic placement ID for in-content ad 3'),
  ('ezoic_id_in_content_4', '112', 'Ezoic placement ID for in-content ad 4'),
  ('ezoic_id_in_content_5', '113', 'Ezoic placement ID for in-content ad 5'),
  ('ezoic_id_bottom_alt', '118', 'Ezoic placement ID for bottom of page alternative'),
  ('ezoic_id_recipe_card', '120', 'Ezoic placement ID for recipe card');

-- HBAgency specific settings
INSERT OR IGNORE INTO settings (key, value, description) VALUES
  ('hbagency_script_url', '', 'HBAgency script URL to inject in head'),
  ('hbagency_ads_txt_url', '', 'HBAgency ads.txt URL (e.g., https://www.hbagency.it/headerbiddingAgency/resources/ads/XXXXX/XXXXX/ads.txt)'),
  ('hbagency_space_top', '', 'HBAgency space ID for top of page'),
  ('hbagency_space_under_title', '', 'HBAgency space ID for under page title'),
  ('hbagency_space_sidebar', '', 'HBAgency space ID for sidebar'),
  ('hbagency_space_sidebar_middle', '', 'HBAgency space ID for sidebar middle'),
  ('hbagency_space_in_content', '', 'HBAgency space ID for in-content ads (fallback for all)'),
  ('hbagency_space_in_content_1', '', 'HBAgency space ID for in-content ad 1'),
  ('hbagency_space_in_content_2', '', 'HBAgency space ID for in-content ad 2'),
  ('hbagency_space_in_content_3', '', 'HBAgency space ID for in-content ad 3'),
  ('hbagency_space_in_content_4', '', 'HBAgency space ID for in-content ad 4'),
  ('hbagency_space_in_content_5', '', 'HBAgency space ID for in-content ad 5'),
  ('hbagency_space_bottom', '', 'HBAgency space ID for bottom of page'),
  ('hbagency_space_recipe_card', '', 'HBAgency space ID for recipe card'),
  ('hbagency_space_floor', '', 'HBAgency space ID for floor/sticky footer ad'),
  ('hbagency_space_interstitial', '', 'HBAgency space ID for interstitial ad');
