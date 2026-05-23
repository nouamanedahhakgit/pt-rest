# Database Setup Guide

This guide will help you set up all database tables in your Cloudflare D1 database.

## Option 1: Quick Setup (Recommended)

Use the complete schema file to set up everything at once:

### For Local Development:
```bash
wrangler d1 execute recipe-db --local --file=./db/complete_schema.sql
```

### For Production:
```bash
wrangler d1 execute recipe-db --remote --file=./db/complete_schema.sql
```

## Option 2: Run Migrations Sequentially

If you prefer to run migrations one by one:

### For Local Development:
```bash
wrangler d1 execute recipe-db --local --file=./db/migrations/001_initial_schema.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/002_add_authors.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/003_add_author_title.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/004_add_settings.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/005_add_pages.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/006_add_code_injection_settings.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/007_add_author_showcase_image.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/008_add_redirects_table.sql
wrangler d1 execute recipe-db --local --file=./db/migrations/009_add_contact_submissions.sql
```

### For Production:
```bash
wrangler d1 execute recipe-db --remote --file=./db/migrations/001_initial_schema.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/002_add_authors.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/003_add_author_title.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/004_add_settings.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/005_add_pages.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/006_add_code_injection_settings.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/007_add_author_showcase_image.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/008_add_redirects_table.sql
wrangler d1 execute recipe-db --remote --file=./db/migrations/009_add_contact_submissions.sql
```

## Option 3: Add Sample Data

After setting up the schema, add sample recipes and categories:

### For Local Development:
```bash
wrangler d1 execute recipe-db --local --file=./db/seeds/001_sample_data.sql
```

### For Production:
```bash
wrangler d1 execute recipe-db --remote --file=./db/seeds/001_sample_data.sql
```

## Verify Your Setup

Check if tables were created successfully:

### For Local Development:
```bash
wrangler d1 execute recipe-db --local --command="SELECT name FROM sqlite_master WHERE type='table'"
```

### For Production:
```bash
wrangler d1 execute recipe-db --remote --command="SELECT name FROM sqlite_master WHERE type='table'"
```

You should see these tables:
- categories
- authors
- recipes
- settings
- pages
- redirects
- contact_submissions

## Check Table Contents

### View all categories:
```bash
wrangler d1 execute recipe-db --local --command="SELECT * FROM categories"
```

### View all recipes:
```bash
wrangler d1 execute recipe-db --local --command="SELECT id, title, slug, status FROM recipes"
```

### View all settings:
```bash
wrangler d1 execute recipe-db --local --command="SELECT key, value FROM settings"
```

## Troubleshooting

### Error: "table already exists"
If you get this error, the table is already created. You can either:
1. Skip that migration
2. Drop the table first: `DROP TABLE IF EXISTS table_name;`
3. Use the complete schema (it has `IF NOT EXISTS` checks)

### Error: "database not found"
Make sure your database exists:
```bash
wrangler d1 list
```

If not listed, create it:
```bash
wrangler d1 create recipe-db
```

Then update the `database_id` in `wrangler.toml` with the ID from the output.

### Error: "no such column"
This means you're trying to add data to a column that doesn't exist yet. Run the migrations in order (001, 002, 003, etc.).

## Database Schema Overview

Your database will have these tables:

1. **categories** - Recipe categories (Desserts, Main Dishes, etc.)
2. **authors** - Recipe creators with bio and images
3. **recipes** - Main recipe content with JSON data
4. **settings** - Site configuration (name, domain, social links)
5. **pages** - Static content pages (About, Privacy, etc.)
6. **redirects** - URL redirects for SEO (301/302)
7. **contact_submissions** - Contact form submissions with spam protection

## Next Steps

After setting up the database:

1. **Start development server:**
   ```bash
   npm run dev
   ```

2. **Test the API:**
   ```bash
   # Get all recipes (requires API token)
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:4321/api/recipes
   
   # Get categories (public)
   curl http://localhost:4321/api/categories
   ```

3. **Set up API token:**
   ```bash
   wrangler secret put API_TOKEN
   # Enter a secure random token when prompted
   ```

4. **Deploy to production:**
   ```bash
   npm run build
   npm run deploy
   ```

## Need Help?

- Check the main README.md for full documentation
- Review DATABASE_API_DOCUMENTATION.md for API usage
- See API_SECURITY_AUDIT.md for security details
