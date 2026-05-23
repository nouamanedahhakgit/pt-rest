# Authors API Documentation

## Overview
The Authors API provides full CRUD (Create, Read, Update, Delete) operations for managing recipe authors. It follows the same security and architectural patterns as the Recipe API.

**Base URL:** `/api/authors`

**Authentication:** All endpoints require Bearer token authentication using the `API_TOKEN` environment variable.

---

## 🔒 Authentication

All requests must include an Authorization header:

```bash
Authorization: Bearer YOUR_API_TOKEN
```

Replace `YOUR_API_TOKEN` with your actual API token from Cloudflare environment variables.

---

## 📋 Endpoints

### 1. GET /api/authors
**List all authors with optional pagination**

#### Request
```bash
GET /api/authors?page=1&limit=50
Authorization: Bearer YOUR_API_TOKEN
```

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | `1` | Page number for pagination |
| `limit` | integer | `50` | Number of authors per page |

#### Response (200 OK)
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Chef Sarah",
      "slug": "chef-sarah",
      "title": "Recipe Creator & Food Blogger",
      "image_url": "https://example.com/sarah.jpg",
      "showcase_image": "https://example.com/sarah-showcase.jpg",
      "bio": "Passionate about creating delicious recipes...",
      "created_at": "2025-01-13 10:00:00",
      "updated_at": "2025-01-13 10:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 5,
    "hasMore": false
  }
}
```

#### Error Response (401 Unauthorized)
```json
{
  "success": false,
  "error": "Unauthorized"
}
```

---

### 2. POST /api/authors
**Create a new author with automatic slug incrementing**

#### Request
```bash
POST /api/authors
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

#### Request Body
```json
{
  "name": "John Doe",
  "slug": "john-doe",
  "title": "Pastry Chef",
  "image_url": "https://example.com/john.jpg",
  "showcase_image": "https://example.com/john-showcase.jpg",
  "bio": "Award-winning pastry chef specializing in French desserts."
}
```

#### Required Fields
- `name` (string) - Author's full name
- `slug` (string) - URL-friendly identifier

#### Optional Fields
- `title` (string|null) - Author's title/role
- `image_url` (string|null) - Profile image URL
- `showcase_image` (string|null) - Featured/banner image URL
- `bio` (string|null) - Author biography

#### Auto-Slug Incrementing
If the provided slug already exists, the API will automatically append a number:
- `john-doe` → `john-doe-1`
- `john-doe-1` → `john-doe-2`
- And so on...

#### Response (201 Created)
```json
{
  "success": true,
  "data": {
    "id": 2,
    "name": "John Doe",
    "slug": "john-doe",
    "title": "Pastry Chef",
    "image_url": "https://example.com/john.jpg",
    "showcase_image": "https://example.com/john-showcase.jpg",
    "bio": "Award-winning pastry chef...",
    "created_at": "2025-01-13 12:30:00",
    "updated_at": "2025-01-13 12:30:00"
  },
  "generated_slug": "john-doe",
  "url": "https://momdishmagic.com/author/john-doe/"
}
```

#### Error Response (400 Bad Request)
```json
{
  "success": false,
  "error": "Missing required fields (name, slug)"
}
```

---

### 3. PUT /api/authors
**Update an existing author**

#### Request
```bash
PUT /api/authors
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

#### Request Body
```json
{
  "id": 2,
  "title": "Executive Pastry Chef",
  "bio": "Updated biography with new achievements..."
}
```

#### Required Fields
- `id` (integer) - Author ID to update

#### Optional Fields (partial updates supported)
- `name` (string)
- `slug` (string)
- `title` (string|null)
- `image_url` (string|null)
- `showcase_image` (string|null)
- `bio` (string|null)

**Note:** Only include fields you want to update. The `updated_at` timestamp is automatically set.

#### Response (200 OK)
```json
{
  "success": true,
  "data": {
    "id": 2,
    "name": "John Doe",
    "slug": "john-doe",
    "title": "Executive Pastry Chef",
    "image_url": "https://example.com/john.jpg",
    "showcase_image": "https://example.com/john-showcase.jpg",
    "bio": "Updated biography with new achievements...",
    "created_at": "2025-01-13 12:30:00",
    "updated_at": "2025-01-13 14:15:00"
  }
}
```

#### Error Responses
**404 Not Found**
```json
{
  "success": false,
  "error": "Author not found"
}
```

**400 Bad Request**
```json
{
  "success": false,
  "error": "No fields to update"
}
```

---

### 4. DELETE /api/authors
**Delete an author by ID**

#### Request
```bash
DELETE /api/authors
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

#### Request Body
```json
{
  "id": 2
}
```

#### Protection Against Orphaned Recipes
The API prevents deletion of authors who have recipes. You must first:
1. Reassign their recipes to another author, OR
2. Delete their recipes

#### Response (200 OK)
```json
{
  "success": true,
  "message": "Author deleted successfully"
}
```

#### Error Response (400 Bad Request)
```json
{
  "success": false,
  "error": "Cannot delete author. This author has 15 recipe(s) associated. Please reassign or delete those recipes first."
}
```

---

## 📝 cURL Examples

### Get All Authors
```bash
curl -X GET "https://momdishmagic.com/api/authors?page=1&limit=10" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Create New Author
```bash
curl -X POST "https://momdishmagic.com/api/authors" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emily Chen",
    "slug": "emily-chen",
    "title": "Asian Fusion Chef",
    "image_url": "https://example.com/emily.jpg",
    "bio": "Specializing in modern Asian cuisine with traditional roots."
  }'
```

### Update Author
```bash
curl -X PUT "https://momdishmagic.com/api/authors" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 3,
    "title": "Head Chef",
    "bio": "Now leading the culinary team at Michelin-starred restaurant."
  }'
```

### Delete Author
```bash
curl -X DELETE "https://momdishmagic.com/api/authors" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 3
  }'
```

---

## 🔧 JavaScript/TypeScript Examples

### Using Fetch API

```typescript
const API_TOKEN = 'your_api_token_here';
const BASE_URL = 'https://momdishmagic.com/api/authors';

// Get all authors
async function getAuthors(page = 1, limit = 50) {
  const response = await fetch(`${BASE_URL}?page=${page}&limit=${limit}`, {
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`
    }
  });
  return await response.json();
}

// Create author
async function createAuthor(authorData) {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(authorData)
  });
  return await response.json();
}

// Update author
async function updateAuthor(id, updates) {
  const response = await fetch(BASE_URL, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ id, ...updates })
  });
  return await response.json();
}

// Delete author
async function deleteAuthor(id) {
  const response = await fetch(BASE_URL, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ id })
  });
  return await response.json();
}

// Usage examples
const authors = await getAuthors(1, 10);
console.log(authors);

const newAuthor = await createAuthor({
  name: 'Maria Rodriguez',
  slug: 'maria-rodriguez',
  title: 'Mexican Cuisine Expert',
  bio: 'Bringing authentic Mexican flavors to home kitchens.'
});
console.log(newAuthor);

const updated = await updateAuthor(4, {
  title: 'Award-Winning Mexican Cuisine Expert'
});
console.log(updated);
```

---

## 🚀 Integration with Recipes

### Get Author's Recipes
Use the Recipe API with author filtering:
```bash
GET /api/recipes?author={author_slug}
```

### When Creating Recipes
Use the `author_id` field to associate a recipe with an author:
```json
{
  "title": "Chocolate Chip Cookies",
  "slug": "chocolate-chip-cookies",
  "author_id": 2,
  ...
}
```

---

## 🎯 Best Practices

### 1. Slug Generation
- Use lowercase letters
- Replace spaces with hyphens
- Remove special characters
- Example: "Chef Sarah Jones" → `chef-sarah-jones`

### 2. Image URLs
- Use absolute URLs (starting with `https://`)
- Recommend CDN-hosted images for performance
- Suggested sizes:
  - `image_url`: 300x300px (profile avatar)
  - `showcase_image`: 1200x400px (banner/header)

### 3. Biography Length
- Recommended: 100-500 characters
- Keep it concise and engaging
- Highlight expertise and credentials

### 4. Error Handling
Always check the `success` field in responses:
```javascript
const result = await createAuthor(data);
if (!result.success) {
  console.error('Error:', result.error);
  // Handle error
} else {
  console.log('Created:', result.data);
}
```

---

## 🔐 Security Notes

1. **Keep API Token Secret** - Never commit `API_TOKEN` to version control
2. **Use HTTPS** - Always use secure connections
3. **Validate Input** - Sanitize all user input before sending
4. **Rate Limiting** - Consider implementing rate limiting for production
5. **CORS** - Configure CORS headers if accessing from browser

---

## 📊 Database Schema Reference

```sql
CREATE TABLE authors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  title TEXT,
  image_url TEXT,
  showcase_image TEXT,
  bio TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_authors_slug ON authors(slug);
```

---

## ❓ Troubleshooting

### "Unauthorized" Error
- Check that `API_TOKEN` environment variable is set in Cloudflare
- Verify the Authorization header format: `Bearer YOUR_TOKEN`
- Ensure there's no extra whitespace in the token

### "Author not found" (404)
- Verify the author ID exists in the database
- Check that you're using the correct ID (not slug)

### "Cannot delete author" (400)
- Author has associated recipes
- Query: `SELECT * FROM recipes WHERE author_id = X`
- Update recipes to different author or delete them first

### "Missing required fields" (400)
- POST requires: `name` and `slug`
- PUT requires: `id`
- DELETE requires: `id`

---

## 🔗 Related Endpoints

- **Recipes API:** `/api/recipes` - Manage recipes
- **Categories API:** `/api/categories` - Manage categories
- **Settings API:** `/api/settings` - Site configuration
- **Pages API:** `/api/pages` - CMS pages

---

## 📚 Additional Resources

- [Recipe API Documentation](https://github.com/your-repo/RECIPE_API_DOCS.md)
- [Database Schema](https://github.com/your-repo/db/migrations/)
- [Astro Documentation](https://docs.astro.build)
- [Cloudflare D1 Documentation](https://developers.cloudflare.com/d1/)

---

**Version:** 1.0.0
**Last Updated:** January 13, 2025
**Maintainer:** MomDishMagic Development Team
