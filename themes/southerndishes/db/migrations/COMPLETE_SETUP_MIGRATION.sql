-- ====================================================================
-- COMPLETE SETUP MIGRATION FOR NEW RECIPE PROJECTS
-- ====================================================================
-- This migration includes all enhancements made to the recipe website
-- Run this after your initial schema is set up
-- ====================================================================

-- 1. Add board_name column to recipes table for Pinterest board organization
-- This allows you to create separate RSS feeds for each board name
ALTER TABLE recipes ADD COLUMN board_name TEXT;

-- ====================================================================
-- That's it for database changes!
-- ====================================================================
--
-- Additional setup required (see SETUP_GUIDE.md):
-- - Add RSS feed routes (src/pages/rss/)
-- - Add replaceTemplateVariables() utility function
-- - Update policy pages to use template variables
-- - Update API endpoints to include board_name
--
-- ====================================================================
