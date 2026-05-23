# Amazon Affiliate Products Widget Documentation

## Overview

This feature allows you to display Amazon affiliate products on your recipe pages. Products are stored in a database and can be shown **globally on all recipe pages** or linked to specific recipes.

### Two Display Modes

1. **Global Products** (Recommended): Mark products with `show_globally: true` to display them on ALL recipe pages automatically
   - ✅ Simple - just add products and they appear everywhere
   - ✅ No need to link products to individual recipes
   - ✅ Perfect for general cooking products that apply to most recipes

2. **Recipe-Specific Products**: Link products to specific recipes for targeted displays (advanced usage)
   - Use when you want different products on different recipes
   - Requires manual linking via API

## Features

- ✅ **Global Products**: Show products on ALL recipe pages automatically
- ✅ Database-driven product management
- ✅ Beautiful product grid with Amazon branding
- ✅ Responsive design (mobile, tablet, desktop)
- ✅ Display order customization
- ✅ Full CRUD API for managing products
- ✅ Active/inactive status for products
- ✅ Automatic Amazon affiliate link handling
- ✅ Optional recipe-specific linking for advanced use cases

## Database Schema

### Tables Created

1. **amazon_products** - Stores product information
   - `id` - Auto-incrementing primary key
   - `title` - Product title
   - `image_url` - Product image URL
   - `price` - Product price (e.g., "$ 9.98")
   - `amazon_url` - Full Amazon URL with affiliate tag
   - `description` - Optional product description
   - `status` - 'active' or 'inactive'
   - `show_globally` - 0 or 1 (show on all recipe pages)
   - `display_order` - Order for sorting
   - `created_at`, `updated_at` - Timestamps

2. **recipe_products** - Junction table linking products to recipes
   - `id` - Auto-incrementing primary key
   - `recipe_id` - Foreign key to recipes table
   - `product_id` - Foreign key to amazon_products table
   - `display_order` - Order within the recipe
   - `placement` - 'article', 'sidebar', or 'both'
   - `created_at` - Timestamp

## API Endpoints

### 1. Manage Amazon Products

**Base URL:** `/api/amazon-products`

#### GET - List All Products
```bash
# Get all products
GET /api/amazon-products

# Get only active products
GET /api/amazon-products?status=active

# Get only inactive products
GET /api/amazon-products?status=inactive
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "Product Name",
      "image_url": "https://m.media-amazon.com/images/I/...",
      "price": "$ 9.98",
      "amazon_url": "https://www.amazon.com/dp/B07G8LPQMF?tag=youraffid-20&linkCode=ll1&linkId=...",
      "description": "Product description",
      "status": "active",
      "show_globally": 1,
      "display_order": 0,
      "created_at": "2024-01-01T00:00:00.000Z",
      "updated_at": "2024-01-01T00:00:00.000Z"
    }
  ]
}
```

#### POST - Create New Product
```bash
POST /api/amazon-products
Content-Type: application/json

{
  "title": "Jordan's Skinny Mixes Sugar Free Coffee Syrup",
  "image_url": "https://m.media-amazon.com/images/I/41jWOp0dIlL._SL500_.jpg",
  "price": "$ 9.98",
  "amazon_url": "https://www.amazon.com/dp/B07G8LPQMF?tag=youraffid-20&linkCode=ll1&linkId=9710b2212dce18500210087882e6fecd",
  "description": "Sugar-free coffee flavoring syrup",
  "status": "active",
  "show_globally": true,
  "display_order": 0
}
```

**Required Fields:**
- `title` (string)
- `image_url` (string)
- `amazon_url` (string)

**Important Optional Field:**
- `show_globally` (boolean) - Set to `true` to show on ALL recipe pages

**Optional Fields:**
- `price` (string)
- `description` (string)
- `status` ('active' | 'inactive', default: 'active')
- `show_globally` (boolean, default: false) - **Set to true to show on all recipes**
- `display_order` (number, default: 0)

#### PUT - Update Product
```bash
PUT /api/amazon-products
Content-Type: application/json

{
  "id": 1,
  "price": "$ 12.99",
  "status": "inactive"
}
```

**Required Field:**
- `id` (number)

**Optional Fields:** Any of the product fields

#### DELETE - Delete Product
```bash
DELETE /api/amazon-products?id=1
```

### 2. Link Products to Recipes

**Base URL:** `/api/recipe-products`

#### GET - Get Products for a Recipe
```bash
# Get all products for recipe ID 5
GET /api/recipe-products?recipe_id=5

# Get only article products
GET /api/recipe-products?recipe_id=5&placement=article

# Get only sidebar products
GET /api/recipe-products?recipe_id=5&placement=sidebar
```

#### POST - Link Product to Recipe
```bash
POST /api/recipe-products
Content-Type: application/json

{
  "recipe_id": 5,
  "product_id": 1,
  "placement": "article",
  "display_order": 0
}
```

**Required Fields:**
- `recipe_id` (number)
- `product_id` (number)

**Optional Fields:**
- `placement` ('article' | 'sidebar' | 'both', default: 'article')
- `display_order` (number, default: 0)

#### PUT - Update Product Placement
```bash
PUT /api/recipe-products
Content-Type: application/json

{
  "recipe_id": 5,
  "product_id": 1,
  "placement": "sidebar",
  "display_order": 1
}
```

#### DELETE - Unlink Product from Recipe
```bash
DELETE /api/recipe-products?recipe_id=5&product_id=1
```

## Using the API with cURL Examples

### Create a Global Product (Shows on ALL Recipes)
```bash
curl -X POST http://localhost:4321/api/amazon-products \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Torani Toasted Marshmallow Syrup",
    "image_url": "https://m.media-amazon.com/images/I/31wWZKJyZTL._SL500_.jpg",
    "price": "$ 18.02",
    "amazon_url": "https://www.amazon.com/dp/B000GZCWDC?tag=youraffid-20&linkCode=ll1&linkId=abc123",
    "status": "active",
    "show_globally": true
  }'
```

**That's all you need!** This product will now appear on every recipe page.

### Link Product to Specific Recipe (Advanced - Optional)
**Note**: This is only needed if you want to show different products on specific recipes. For most users, using `show_globally: true` is simpler.

```bash
curl -X POST http://localhost:4321/api/recipe-products \
  -H "Content-Type: application/json" \
  -d '{
    "recipe_id": 1,
    "product_id": 1,
    "placement": "article"
  }'
```

### Get All Products for a Recipe (Advanced)
```bash
curl http://localhost:4321/api/recipe-products?recipe_id=1
```

## Using the Component Directly

You can also use the `AmazonProductGrid` component in any Astro page:

```astro
---
import AmazonProductGrid from '../components/AmazonProductGrid.astro';
import type { AmazonProduct } from '../types/recipe';

const products: AmazonProduct[] = [
  {
    id: 1,
    title: 'Product Name',
    image_url: 'https://m.media-amazon.com/images/I/image.jpg',
    price: '$ 9.98',
    amazon_url: 'https://www.amazon.com/dp/B07G8LPQMF?tag=youraffid-20&linkCode=ll1&linkId=abc123',
    description: 'Product description',
    status: 'active',
    display_order: 0,
    created_at: '',
    updated_at: ''
  }
];
---

<AmazonProductGrid products={products} columns={3} />
```

### Component Props

- `products` (AmazonProduct[], required) - Array of products to display
- `columns` (2 | 3 | 4, optional, default: 3) - Number of columns in grid
- `className` (string, optional) - Additional CSS classes

## How Products Appear on Recipe Pages

Products linked to a recipe will automatically appear:

1. **In the article** - Products with placement 'article' or 'both' appear after the article content and before the recipe card
2. **In the sidebar** - Products with placement 'sidebar' or 'both' appear in the sidebar above the author box

### Responsive Grid Behavior

- **Mobile (< 640px):** 1 column
- **Tablet (640px - 767px):** 2 columns
- **Desktop (≥ 768px):**
  - 2-column grid: 2 columns
  - 3-column grid: 3 columns
  - 4-column grid: 3 columns
- **Large Desktop (≥ 1024px):**
  - 4-column grid: 4 columns

## Widget Styling

The widget includes:
- ✅ Amazon logo
- ✅ Coral/orange gradient background
- ✅ Product image with hover zoom effect
- ✅ Product title (3-line truncation)
- ✅ Price display with chevron icon
- ✅ "Shop" button
- ✅ Hover effects (shadow, transform)
- ✅ Responsive layout

## Example Workflow

### Step 1: Create Products
```bash
# Create product 1
curl -X POST http://localhost:4321/api/amazon-products \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product 1",
    "image_url": "https://...",
    "price": "$ 9.98",
    "amazon_url": "https://www.amazon.com/dp/B07G8LPQMF?tag=youraffid-20&linkCode=ll1&linkId=abc123"
  }'

# Create product 2
curl -X POST http://localhost:4321/api/amazon-products \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product 2",
    "image_url": "https://...",
    "price": "$ 12.99",
    "amazon_url": "https://www.amazon.com/dp/B000GZCWDC?tag=youraffid-20&linkCode=ll1&linkId=xyz789"
  }'
```

### Step 2: Get Recipe ID
You need to know the recipe ID. You can find it by:
1. Looking in your database
2. Using the recipes API: `GET /api/recipes`
3. Checking the recipe URL slug

### Step 3: Link Products to Recipe
```bash
# Link product 1 to recipe (in article)
curl -X POST http://localhost:4321/api/recipe-products \
  -H "Content-Type: application/json" \
  -d '{
    "recipe_id": 1,
    "product_id": 1,
    "placement": "article",
    "display_order": 0
  }'

# Link product 2 to recipe (in sidebar)
curl -X POST http://localhost:4321/api/recipe-products \
  -H "Content-Type: application/json" \
  -d '{
    "recipe_id": 1,
    "product_id": 2,
    "placement": "sidebar",
    "display_order": 0
  }'
```

### Step 4: View Your Recipe Page
Visit your recipe page and you'll see:
- Product 1 in the article (after content, before recipe card)
- Product 2 in the sidebar (above author box)

## Database Service Methods

If you're working directly with the database service:

```typescript
import { DatabaseService } from './lib/database';

const db = new DatabaseService(DB);

// Get all active products
const products = await db.getAmazonProducts('active');

// Get product by ID
const product = await db.getAmazonProductById(1);

// Add product
const productId = await db.addAmazonProduct({
  title: 'Product Name',
  image_url: 'https://...',
  amazon_url: 'https://www.amazon.com/dp/...'
});

// Update product
await db.updateAmazonProduct(1, {
  price: '$ 14.99',
  status: 'active'
});

// Delete product
await db.deleteAmazonProduct(1);

// Get products for recipe
const recipeProducts = await db.getRecipeProducts(1, 'article');

// Link product to recipe
await db.linkProductToRecipe(1, 1, 'article', 0);

// Unlink product from recipe
await db.unlinkProductFromRecipe(1, 1);
```

## Tips & Best Practices

1. **Use High-Quality Images**: Amazon product images work best (use their CDN URLs)
2. **Keep Titles Concise**: Product titles truncate after 3 lines
3. **Test Affiliate Links**: Ensure your affiliate tag is correct in the full URL
4. **Use Full Amazon URLs**: Include all tracking parameters (tag, linkCode, linkId, etc.)
5. **Use Display Order**: Order products by relevance or priority
6. **Article vs Sidebar**:
   - Article: 3-column grid, more prominent
   - Sidebar: 2-column grid, less intrusive
7. **Status Management**: Use 'inactive' to hide products without deleting them

## Production Deployment

To deploy to production, run the migration on your remote database:

```bash
npx wrangler d1 execute momdishmagic --remote --file=./db/migrations/015_add_amazon_products.sql
```

## Troubleshooting

### Products Not Showing
1. Check product status is 'active'
2. Verify recipe_id is correct
3. Check placement is set correctly
4. Ensure database migration ran successfully

### API Errors
1. Check request body format (JSON)
2. Verify required fields are present
3. Check for ASIN duplicates
4. Look at browser console for errors

### Styling Issues
1. Clear browser cache
2. Check for CSS conflicts
3. Verify responsive breakpoints

## Files Created/Modified

### New Files
- `db/migrations/015_add_amazon_products.sql`
- `src/pages/api/amazon-products.ts`
- `src/pages/api/recipe-products.ts`
- `src/components/AmazonProductGrid.astro`

### Modified Files
- `src/types/recipe.ts` (added AmazonProduct types)
- `src/lib/database.ts` (added product methods)
- `src/pages/[slug].astro` (integrated product widgets)

## Support

For issues or questions, refer to:
- Amazon Associates: https://affiliate-program.amazon.com/
- Get Full Product URL: Use Amazon Associates SiteStripe or Product Links tools
- Image URLs: Use Amazon CDN images for best performance (right-click on product image → Copy image address)
