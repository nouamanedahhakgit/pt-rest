# Deployment Guide

This guide walks you through deploying your Recipe Website to Cloudflare Pages with D1 Database.

## Prerequisites

1. **Cloudflare Account**: Sign up at [cloudflare.com](https://cloudflare.com)
2. **Wrangler CLI**: Install with `npm install -g wrangler`
3. **Git Repository**: Your code should be in a Git repository

## Step-by-Step Deployment

### 1. Set Up Wrangler CLI

```bash
# Install Wrangler globally
npm install -g wrangler

# Authenticate with Cloudflare
wrangler auth login
```

### 2. Create D1 Database

```bash
# Create the production database
wrangler d1 create recipe-db
```

**Important**: Copy the database ID from the output and update your `wrangler.toml`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "recipe-db"
database_id = "YOUR-ACTUAL-DATABASE-ID-HERE"  # Replace this
```

### 3. Run Database Migrations

```bash
# Create tables in production database
wrangler d1 execute recipe-db --file=./db/migrations/001_initial_schema.sql

# Add sample data
wrangler d1 execute recipe-db --file=./db/seeds/001_sample_data.sql
```

### 4. Build and Deploy

```bash
# Build the project
npm run build

# Deploy to Cloudflare Pages
wrangler pages deploy
```

### 5. Configure Pages Project

After first deployment, set up your project:

1. **Go to Cloudflare Dashboard** → Pages
2. **Find your project** and click on it
3. **Go to Settings** → Environment variables
4. **Add variables** (if needed):
   ```
   NODE_ENV = production
   ```

### 6. Set Up Custom Domain (Optional)

1. **In Cloudflare Pages Dashboard**:
   - Go to your project
   - Click "Custom domains"
   - Add your domain
2. **Update DNS**:
   - Add CNAME record pointing to your Pages URL

## Environment Configuration

### Production Environment

Your `wrangler.toml` should look like this for production:

```toml
name = "recipe-website"
main = "dist/_worker.js"
compatibility_date = "2023-05-18"

[build]
command = "npm run build"

[vars]
NODE_ENV = "production"

[[d1_databases]]
binding = "DB"
database_name = "recipe-db"
database_id = "your-production-database-id"
```

### Local Development

For local development with live database:

```bash
# Start dev server with database binding
wrangler pages dev dist --d1 DB=recipe-db

# Or use local D1 (recommended for testing)
wrangler pages dev dist --d1 DB=recipe-db --local
```

## Continuous Deployment

### Using Git Integration

1. **Connect Repository**:
   - In Cloudflare Pages Dashboard
   - Create new project from Git
   - Connect your repository

2. **Build Settings**:
   ```
   Build command: npm run build
   Build output directory: dist
   Root directory: /
   ```

3. **Environment Variables**:
   - Set any required environment variables
   - Database binding is handled automatically

### Manual Deployment

For manual deployments:

```bash
# Build and deploy in one command
npm run deploy

# Or step by step
npm run build
wrangler pages deploy
```

## Database Management

### Adding New Data

```bash
# Add new recipe via SQL
wrangler d1 execute recipe-db --command="INSERT INTO recipes (...) VALUES (...)"

# Run custom SQL file
wrangler d1 execute recipe-db --file=./path/to/your-file.sql
```

### Backup and Restore

```bash
# Export data (backup)
wrangler d1 export recipe-db --output=backup.sql

# View database info
wrangler d1 info recipe-db
```

### Development vs Production

```bash
# Local development database
wrangler d1 execute recipe-db --local --file=./db/migrations/001_initial_schema.sql

# Production database
wrangler d1 execute recipe-db --file=./db/migrations/001_initial_schema.sql
```

## Domain and SSL

### Custom Domain Setup

1. **Add Domain in Pages**:
   - Go to Custom domains in Pages dashboard
   - Add your domain (e.g., `recipes.yourdomain.com`)

2. **DNS Configuration**:
   ```
   Type: CNAME
   Name: recipes (or @)
   Content: your-pages-url.pages.dev
   ```

3. **SSL Certificate**:
   - Automatically provided by Cloudflare
   - Usually takes 5-15 minutes to provision

## Analytics and Monitoring

### Cloudflare Web Analytics

Add to your `Layout.astro`:

```astro
<!-- In the <head> section -->
{import.meta.env.PROD && (
  <script defer src='https://static.cloudflareinsights.com/beacon.min.js'
          data-cf-beacon='{"token": "your-token-here"}'></script>
)}
```

### Pages Functions Analytics

View in Cloudflare Dashboard:
- Go to your Pages project
- Click on "Functions" tab
- View analytics and logs

## Performance Optimization

### Image Optimization

Use Cloudflare Images (optional):

```astro
<!-- Use Cloudflare Images for better performance -->
<img src={`/cdn-cgi/image/width=800,height=600,quality=85/${imageUrl}`} alt="Recipe" />
```

### Caching Strategy

Headers are automatically set by Cloudflare:
- Static assets: Long-term caching
- API endpoints: Custom cache headers in your functions

## Troubleshooting

### Common Issues

**Database not found**:
```bash
# Check if database exists
wrangler d1 list

# Verify database ID in wrangler.toml
cat wrangler.toml
```

**Build failures**:
```bash
# Clear dependencies and rebuild
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Function errors**:
```bash
# Check function logs
wrangler pages deployment tail

# Local testing
wrangler pages dev dist
```

### Debugging

1. **Check build logs** in Cloudflare Pages dashboard
2. **View function logs** in real-time with `wrangler pages deployment tail`
3. **Test locally** with `npm run dev` or `wrangler pages dev`

## Security Considerations

### Environment Variables

- Never commit sensitive data to your repository
- Use Cloudflare Pages environment variables for secrets
- Database credentials are handled automatically by Wrangler

### HTTPS

- All Cloudflare Pages projects use HTTPS by default
- Automatic certificate management
- HSTS headers included

## Scaling

### Database Limits

Cloudflare D1 limits (as of 2024):
- 25 GB storage per database
- 25 million rows per database
- 1,000 databases per account

### Pages Limits

- 25 MB per deployment
- 20,000 files per deployment
- 500 requests per second (can be increased)

## Support

If you encounter issues:

1. **Check Cloudflare Status**: [cloudflarestatus.com](https://cloudflarestatus.com)
2. **Cloudflare Community**: [community.cloudflare.com](https://community.cloudflare.com)
3. **Wrangler Documentation**: [developers.cloudflare.com/workers/wrangler](https://developers.cloudflare.com/workers/wrangler)

---

**Your recipe website is now live! 🎉**