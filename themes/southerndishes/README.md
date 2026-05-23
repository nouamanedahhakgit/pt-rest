# Recipe Website

A modern, production-ready food recipe website built with Astro, Cloudflare Pages, and D1 Database. Features a clean, responsive design optimized for SEO and social sharing.

## ✨ Features

- **Modern Tech Stack**: Astro + Cloudflare Pages + D1 Database
- **Responsive Design**: Mobile-first design with Tailwind CSS
- **SEO Optimized**: JSON-LD schema markup, Open Graph, and Twitter Cards
- **Recipe Management**: Full CRUD operations with automatic slug handling
- **Category System**: Organize recipes by categories
- **Print-Friendly**: Optimized recipe cards for printing
- **Social Sharing**: Built-in sharing for Pinterest, Facebook, and Twitter
- **Fast Performance**: Static generation with dynamic API endpoints
- **TypeScript**: Full type safety throughout the application

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- npm or yarn
- Wrangler CLI (for Cloudflare development)

### Installation

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Install Wrangler CLI** (if not already installed)
   ```bash
   npm install -g wrangler
   ```

3. **Login to Cloudflare**
   ```bash
   wrangler auth login
   ```

### Database Setup

1. **Create D1 database**
   ```bash
   npm run db:create
   ```

2. **Update wrangler.toml** with your database ID:
   ```toml
   [[d1_databases]]
   binding = "DB"
   database_name = "recipe-db"
   database_id = "your-actual-database-id-here"
   ```

3. **Run migrations**
   ```bash
   # For production
   npm run db:migrate

   # For local development
   npm run db:migrate:local
   ```

4. **Seed sample data**
   ```bash
   # For production
   npm run db:seed

   # For local development
   npm run db:seed:local
   ```

### Development

1. **Start development server**
   ```bash
   npm run dev
   ```

2. **Visit your local site**
   ```
   http://localhost:4321
   ```

### Production Build

1. **Build the project**
   ```bash
   npm run build
   ```

2. **Deploy to Cloudflare Pages**
   ```bash
   npm run deploy
   ```

## 📁 Project Structure

```
recipe-website/
├── src/
│   ├── components/          # Reusable Astro components
│   │   ├── RecipeCard.astro    # Individual recipe card
│   │   ├── RecipeDetails.astro # Complete recipe display
│   │   └── RecipeGrid.astro    # Grid layout for recipes
│   ├── layouts/            # Page layouts
│   │   └── Layout.astro       # Main site layout
│   ├── pages/              # Route pages
│   │   ├── api/              # API endpoints
│   │   ├── category/         # Category pages
│   │   ├── index.astro       # Homepage
│   │   ├── recipes.astro     # All recipes page
│   │   └── [slug].astro      # Individual recipe pages
│   ├── lib/                # Utilities and services
│   │   ├── database.ts       # Database service layer
│   │   └── utils.ts          # Helper functions
│   ├── types/              # TypeScript type definitions
│   │   ├── recipe.ts         # Recipe-related types
│   │   └── cloudflare.ts     # Cloudflare-specific types
│   └── styles/             # Global styles
│       └── global.css        # Tailwind + custom styles
├── db/
│   ├── migrations/         # Database migrations
│   └── seeds/              # Sample data
├── public/                 # Static assets
├── astro.config.mjs       # Astro configuration
├── tailwind.config.mjs    # Tailwind CSS configuration
├── wrangler.toml         # Cloudflare configuration
└── package.json
```

## 🗃️ Database Schema

### Categories Table
```sql
CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Recipes Table
```sql
CREATE TABLE recipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  pin_image TEXT,
  pin_description TEXT,
  slug TEXT UNIQUE NOT NULL,
  article_content TEXT NOT NULL,
  featured_image TEXT NOT NULL,
  recipe_json TEXT NOT NULL,
  category_id INTEGER,
  status TEXT DEFAULT 'draft',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories (id)
);
```

## 📝 Recipe JSON Structure

Each recipe's detailed information is stored as JSON in the `recipe_json` field:

```json
{
  "name": "Ultimate Chewy Chocolate Chip Cookies",
  "summary": "Deliciously chewy chocolate chip cookies...",
  "servings": "24",
  "prep_time": "15",
  "cook_time": "12",
  "total_time": "30",
  "calories": "150",
  "course": "Dessert",
  "cuisine": "American",
  "keywords": ["cookies", "chocolate chip", "dessert"],
  "notes": "Serve with milk for best experience...",
  "ingredients": [
    {
      "amount": "2.25",
      "unit": "cups",
      "name": "all-purpose flour"
    }
  ],
  "instructions": [
    "Preheat oven to 350°F...",
    "Mix dry ingredients..."
  ]
}
```

## 🛠️ Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run db:create` | Create D1 database |
| `npm run db:migrate` | Run migrations (production) |
| `npm run db:seed` | Seed data (production) |
| `npm run db:migrate:local` | Run migrations (local) |
| `npm run db:seed:local` | Seed data (local) |
| `npm run deploy` | Deploy to Cloudflare Pages |

## 🌐 Deployment

### Cloudflare Pages

1. **Build and deploy**
   ```bash
   npm run build
   wrangler pages deploy
   ```

2. **Set up custom domain** (optional)
   - Configure in Cloudflare Pages dashboard
   - Update DNS settings

### Environment Variables

This project primarily uses `wrangler.toml` for configuration, but you can optionally use `.env` files:

#### **For Local Development:**
```bash
# Copy the example file
cp .env.example .env

# Edit with your local settings (optional)
nano .env
```

#### **For Production:**
Set environment variables in **Cloudflare Pages Dashboard**:
1. Go to your Pages project
2. Navigate to **Settings** → **Environment variables**
3. Add any required variables

#### **Important Notes:**
- **Database connection** is handled automatically via `wrangler.toml`
- **Most configurations** don't need environment variables
- **Never commit** `.env` files with real secrets
- **Use `.env` only** for optional third-party integrations

### Environment Setup

For production deployment, ensure these are configured:

- **D1 Database**: Created and migrated with production data
- **Custom Domain**: Set up in Cloudflare Pages (optional)
- **Analytics**: Add tracking codes to Layout.astro (optional)

## 🔧 Troubleshooting

### Common Issues

**Database connection errors:**
- Verify wrangler.toml has correct database ID
- Ensure you're logged into Cloudflare with `wrangler auth login`
- Check database exists with `wrangler d1 list`

**Build errors:**
- Clear node_modules and reinstall dependencies
- Update all packages to latest versions
- Check for TypeScript errors

**Development server issues:**
- Ensure port 4321 is available
- Check for conflicting processes
- Restart with `npm run dev`

## 📄 License

This project is licensed under the MIT License.

---

**Happy cooking! 👨‍🍳👩‍🍳**
