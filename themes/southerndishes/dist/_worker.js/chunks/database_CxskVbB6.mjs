globalThis.process ??= {}; globalThis.process.env ??= {};
class DatabaseService {
  constructor(db) {
    this.db = db;
  }
  async getRecipeBySlug(slug) {
    const result = await this.db.prepare(`
        SELECT r.*,
               c.name as category_name, c.slug as category_slug,
               a.id as author_id, a.name as author_name, a.slug as author_slug,
               a.title as author_title, a.image_url as author_image_url, a.bio as author_bio,
               a.created_at as author_created_at, a.updated_at as author_updated_at
        FROM recipes r
        LEFT JOIN categories c ON r.category_id = c.id
        LEFT JOIN authors a ON r.author_id = a.id
        WHERE r.slug = ? AND r.status = 'published'
      `).bind(slug).first();
    if (!result) return null;
    return {
      ...result,
      recipe_data: JSON.parse(result.recipe_json),
      category: result.category_name ? {
        id: result.category_id,
        name: result.category_name,
        slug: result.category_slug,
        created_at: result.created_at,
        updated_at: result.updated_at
      } : void 0,
      author: result.author_name ? {
        id: result.author_id,
        name: result.author_name,
        slug: result.author_slug,
        title: result.author_title,
        image_url: result.author_image_url,
        bio: result.author_bio,
        created_at: result.author_created_at,
        updated_at: result.author_updated_at
      } : void 0
    };
  }
  async getRecipes(limit, offset) {
    let query = `
      SELECT r.*, c.name as category_name, c.slug as category_slug
      FROM recipes r
      LEFT JOIN categories c ON r.category_id = c.id
      WHERE r.status = 'published'
      ORDER BY r.created_at DESC
    `;
    if (limit) {
      query += ` LIMIT ${limit}`;
      if (offset) {
        query += ` OFFSET ${offset}`;
      }
    }
    const result = await this.db.prepare(query).all();
    return result.results || [];
  }
  async getRecipesByCategory(categorySlug, limit, offset) {
    let query = `
      SELECT r.*
      FROM recipes r
      JOIN categories c ON r.category_id = c.id
      WHERE c.slug = ? AND r.status = 'published'
      ORDER BY r.created_at DESC
    `;
    if (limit) {
      query += ` LIMIT ${limit}`;
      if (offset) {
        query += ` OFFSET ${offset}`;
      }
    }
    const result = await this.db.prepare(query).bind(categorySlug).all();
    return result.results || [];
  }
  async getFeaturedRecipes(limit = 6) {
    const result = await this.db.prepare(`
        SELECT * FROM recipes
        WHERE status = 'published'
        ORDER BY created_at DESC
        LIMIT ?
      `).bind(limit).all();
    return result.results || [];
  }
  async getCategories() {
    const result = await this.db.prepare("SELECT * FROM categories ORDER BY name ASC").all();
    return result.results || [];
  }
  async getCategoryBySlug(slug) {
    return await this.db.prepare("SELECT * FROM categories WHERE slug = ?").bind(slug).first();
  }
  async getRelatedRecipes(categoryId, excludeId, limit = 3) {
    const result = await this.db.prepare(`
        SELECT * FROM recipes
        WHERE category_id = ? AND id != ? AND status = 'published'
        ORDER BY created_at DESC
        LIMIT ?
      `).bind(categoryId, excludeId, limit).all();
    return result.results || [];
  }
  async searchRecipes(query, limit = 20) {
    const searchTerm = `%${query}%`;
    const result = await this.db.prepare(`
        SELECT r.* FROM recipes r
        WHERE r.title LIKE ?
        AND r.status = 'published'
        ORDER BY r.created_at DESC
        LIMIT ?
      `).bind(searchTerm, limit).all();
    return result.results || [];
  }
  async generateUniqueSlug(baseSlug) {
    let slug = baseSlug;
    let counter = 1;
    while (true) {
      const exists = await this.db.prepare("SELECT id FROM recipes WHERE slug = ?").bind(slug).first();
      if (!exists) {
        return slug;
      }
      slug = `${baseSlug}-${counter}`;
      counter++;
    }
  }
  // Author methods
  async getAuthors() {
    const result = await this.db.prepare("SELECT * FROM authors ORDER BY name ASC").all();
    return result.results || [];
  }
  async getAuthorBySlug(slug) {
    return await this.db.prepare("SELECT * FROM authors WHERE slug = ?").bind(slug).first();
  }
  async getRecipesByAuthor(authorSlug, limit, offset) {
    let query = `
      SELECT r.*
      FROM recipes r
      JOIN authors a ON r.author_id = a.id
      WHERE a.slug = ? AND r.status = 'published'
      ORDER BY r.created_at DESC
    `;
    if (limit) {
      query += ` LIMIT ${limit}`;
      if (offset) {
        query += ` OFFSET ${offset}`;
      }
    }
    const result = await this.db.prepare(query).bind(authorSlug).all();
    return result.results || [];
  }
  async getRecipeCountByAuthor(authorSlug) {
    const result = await this.db.prepare(`
        SELECT COUNT(*) as count
        FROM recipes r
        JOIN authors a ON r.author_id = a.id
        WHERE a.slug = ? AND r.status = 'published'
      `).bind(authorSlug).first();
    return result?.count || 0;
  }
  // Settings methods
  async getSetting(key) {
    const result = await this.db.prepare("SELECT value FROM settings WHERE key = ?").bind(key).first();
    return result?.value || null;
  }
  async getAllSettings() {
    const result = await this.db.prepare("SELECT key, value FROM settings").all();
    const settings = {};
    for (const row of result.results || []) {
      settings[row.key] = row.value;
    }
    return settings;
  }
  async updateSetting(key, value) {
    await this.db.prepare("UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?").bind(value, key).run();
  }
  // Pages methods
  async getPageBySlug(slug) {
    return await this.db.prepare("SELECT * FROM pages WHERE slug = ? AND status = ?").bind(slug, "published").first();
  }
  async getAllPages() {
    const result = await this.db.prepare("SELECT * FROM pages WHERE status = ? ORDER BY title ASC").bind("published").all();
    return result.results || [];
  }
}

export { DatabaseService as D };
