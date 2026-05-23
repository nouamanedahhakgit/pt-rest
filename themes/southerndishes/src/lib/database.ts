import type { D1Database } from '../types/cloudflare';
import type { Recipe, Category, RecipeData, RecipeWithData, Author } from '../types/recipe';

export class DatabaseService {
  constructor(private db: D1Database) {}

  async getRecipeBySlug(slug: string): Promise<RecipeWithData | null> {
    const result = await this.db
      .prepare(`
        SELECT r.*,
               c.name as category_name, c.slug as category_slug,
               a.id as author_id, a.name as author_name, a.slug as author_slug,
               a.title as author_title, a.image_url as author_image_url, a.bio as author_bio,
               a.created_at as author_created_at, a.updated_at as author_updated_at
        FROM recipes r
        LEFT JOIN categories c ON r.category_id = c.id
        LEFT JOIN authors a ON r.author_id = a.id
        WHERE r.slug = ? AND r.status = 'published'
      `)
      .bind(slug)
      .first<Recipe & {
        category_name?: string;
        category_slug?: string;
        author_name?: string;
        author_slug?: string;
        author_title?: string;
        author_image_url?: string;
        author_bio?: string;
        author_created_at?: string;
        author_updated_at?: string;
      }>();

    if (!result) return null;

    return {
      ...result,
      recipe_data: JSON.parse(result.recipe_json) as RecipeData,
      category: result.category_name ? {
        id: result.category_id!,
        name: result.category_name,
        slug: result.category_slug!,
        created_at: result.created_at,
        updated_at: result.updated_at
      } : undefined,
      author: result.author_name ? {
        id: result.author_id!,
        name: result.author_name,
        slug: result.author_slug!,
        title: result.author_title,
        image_url: result.author_image_url,
        bio: result.author_bio,
        created_at: result.author_created_at!,
        updated_at: result.author_updated_at!
      } : undefined
    };
  }

  async getRecipes(limit?: number, offset?: number): Promise<Recipe[]> {
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

    const result = await this.db.prepare(query).all<Recipe>();
    return result.results || [];
  }

  async getRecipeCount(): Promise<number> {
    const result = await this.db
      .prepare(`
        SELECT COUNT(*) as count
        FROM recipes
        WHERE status = 'published'
      `)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  async getRecipesByCategory(categorySlug: string, limit?: number, offset?: number): Promise<Recipe[]> {
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

    const result = await this.db.prepare(query).bind(categorySlug).all<Recipe>();
    return result.results || [];
  }

  async getRecipeCountByCategory(categorySlug: string): Promise<number> {
    const result = await this.db
      .prepare(`
        SELECT COUNT(*) as count
        FROM recipes r
        JOIN categories c ON r.category_id = c.id
        WHERE c.slug = ? AND r.status = 'published'
      `)
      .bind(categorySlug)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  async getFeaturedRecipes(limit = 6): Promise<Recipe[]> {
    const result = await this.db
      .prepare(`
        SELECT * FROM recipes
        WHERE status = 'published'
        ORDER BY created_at DESC
        LIMIT ?
      `)
      .bind(limit)
      .all<Recipe>();

    return result.results || [];
  }

  async getCategories(): Promise<Category[]> {
    const result = await this.db
      .prepare('SELECT * FROM categories ORDER BY name ASC')
      .all<Category>();

    return result.results || [];
  }

  async getCategoryBySlug(slug: string): Promise<Category | null> {
    return await this.db
      .prepare('SELECT * FROM categories WHERE slug = ?')
      .bind(slug)
      .first<Category>();
  }

  async getRelatedRecipes(categoryId: number, excludeId: number, limit = 3): Promise<Recipe[]> {
    const result = await this.db
      .prepare(`
        SELECT * FROM recipes
        WHERE category_id = ? AND id != ? AND status = 'published'
        ORDER BY created_at DESC
        LIMIT ?
      `)
      .bind(categoryId, excludeId, limit)
      .all<Recipe>();

    return result.results || [];
  }

  async searchRecipes(query: string, limit = 20): Promise<Recipe[]> {
    const searchTerm = `%${query}%`;
    const result = await this.db
      .prepare(`
        SELECT r.* FROM recipes r
        WHERE r.title LIKE ?
        AND r.status = 'published'
        ORDER BY r.created_at DESC
        LIMIT ?
      `)
      .bind(searchTerm, limit)
      .all<Recipe>();

    return result.results || [];
  }

  async generateUniqueSlug(baseSlug: string): Promise<string> {
    let slug = baseSlug;
    let counter = 1;

    while (true) {
      const exists = await this.db
        .prepare('SELECT id FROM recipes WHERE slug = ?')
        .bind(slug)
        .first();

      if (!exists) {
        return slug;
      }

      slug = `${baseSlug}-${counter}`;
      counter++;
    }
  }

  // Author methods
  async getAuthors(): Promise<Author[]> {
    const result = await this.db
      .prepare('SELECT * FROM authors ORDER BY name ASC')
      .all<Author>();

    return result.results || [];
  }

  async getAuthorBySlug(slug: string): Promise<Author | null> {
    return await this.db
      .prepare('SELECT * FROM authors WHERE slug = ?')
      .bind(slug)
      .first<Author>();
  }

  async getAuthorById(id: number): Promise<Author | null> {
    return await this.db
      .prepare('SELECT * FROM authors WHERE id = ?')
      .bind(id)
      .first<Author>();
  }

  async getRecipesByAuthor(authorSlug: string, limit?: number, offset?: number): Promise<Recipe[]> {
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

    const result = await this.db.prepare(query).bind(authorSlug).all<Recipe>();
    return result.results || [];
  }

  async getRecipeCountByAuthor(authorSlug: string): Promise<number> {
    const result = await this.db
      .prepare(`
        SELECT COUNT(*) as count
        FROM recipes r
        JOIN authors a ON r.author_id = a.id
        WHERE a.slug = ? AND r.status = 'published'
      `)
      .bind(authorSlug)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  // Board name methods
  async getRecipesByBoardName(boardName: string, limit?: number, offset?: number): Promise<Recipe[]> {
    let query = `
      SELECT r.*, c.name as category_name, c.slug as category_slug
      FROM recipes r
      LEFT JOIN categories c ON r.category_id = c.id
      WHERE r.board_name = ?
        AND r.status = 'published'
        AND (r.pin_image IS NOT NULL AND r.pin_image != ''
             OR r.featured_image IS NOT NULL AND r.featured_image != '')
      ORDER BY r.updated_at DESC
    `;

    if (limit) {
      query += ` LIMIT ${limit}`;
      if (offset) {
        query += ` OFFSET ${offset}`;
      }
    }

    const result = await this.db.prepare(query).bind(boardName).all<Recipe>();
    return result.results || [];
  }

  async getRecipeCountByBoardName(boardName: string): Promise<number> {
    const result = await this.db
      .prepare(`
        SELECT COUNT(*) as count
        FROM recipes
        WHERE board_name = ? AND status = 'published'
      `)
      .bind(boardName)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  async getAllBoardNames(): Promise<string[]> {
    const result = await this.db
      .prepare(`
        SELECT DISTINCT board_name
        FROM recipes
        WHERE board_name IS NOT NULL AND board_name != '' AND status = 'published'
        ORDER BY board_name ASC
      `)
      .all<{ board_name: string }>();

    return (result.results || []).map(r => r.board_name);
  }

  // Settings methods
  async getSetting(key: string): Promise<string | null> {
    const result = await this.db
      .prepare('SELECT value FROM settings WHERE key = ?')
      .bind(key)
      .first<{ value: string }>();

    return result?.value || null;
  }

  async getAllSettings(): Promise<Record<string, string>> {
    const result = await this.db
      .prepare('SELECT key, value FROM settings')
      .all<{ key: string; value: string }>();

    const settings: Record<string, string> = {};
    for (const row of result.results || []) {
      settings[row.key] = row.value;
    }

    return settings;
  }

  async updateSetting(key: string, value: string): Promise<void> {
    await this.db
      .prepare('UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?')
      .bind(value, key)
      .run();
  }

  // Pages methods
  async getPageBySlug(slug: string): Promise<any | null> {
    return await this.db
      .prepare('SELECT * FROM pages WHERE slug = ? AND status = ?')
      .bind(slug, 'published')
      .first();
  }

  async getAllPages(): Promise<any[]> {
    const result = await this.db
      .prepare('SELECT * FROM pages WHERE status = ? ORDER BY title ASC')
      .bind('published')
      .all();

    return result.results || [];
  }

  // ==========================================
  // REDIRECTS METHODS
  // ==========================================

  /**
   * Check if a slug has a redirect
   * @param oldSlug - The old recipe slug to check
   * @returns The redirect URL if found, null otherwise
   */
  async getRedirect(oldSlug: string): Promise<string | null> {
    if (!this.db) return null;

    const result = await this.db
      .prepare('SELECT new_url FROM redirects WHERE old_slug = ?')
      .bind(oldSlug)
      .first<{ new_url: string }>();

    return result?.new_url || null;
  }

  /**
   * Add a new redirect
   * @param oldSlug - The old recipe slug
   * @param newUrl - The new URL to redirect to
   */
  async addRedirect(oldSlug: string, newUrl: string): Promise<void> {
    if (!this.db) return;

    await this.db
      .prepare('INSERT INTO redirects (old_slug, new_url) VALUES (?, ?)')
      .bind(oldSlug, newUrl)
      .run();
  }

  /**
   * Add multiple redirects to the same URL
   * @param oldSlugs - Array of old recipe slugs
   * @param newUrl - The new URL to redirect to
   */
  async addMultipleRedirects(oldSlugs: string[], newUrl: string): Promise<void> {
    if (!this.db) return;

    for (const oldSlug of oldSlugs) {
      await this.addRedirect(oldSlug, newUrl);
    }
  }

  /**
   * Delete a redirect
   * @param oldSlug - The old slug to remove
   */
  async deleteRedirect(oldSlug: string): Promise<void> {
    if (!this.db) return;

    await this.db
      .prepare('DELETE FROM redirects WHERE old_slug = ?')
      .bind(oldSlug)
      .run();
  }

  // ==========================================
  // CONTACT SUBMISSIONS METHODS
  // ==========================================

  /**
   * Add a new contact form submission
   * @param name - The sender's name
   * @param email - The sender's email
   * @param subject - The message subject
   * @param message - The message content
   * @param ipAddress - Optional IP address
   * @param userAgent - Optional user agent string
   */
  async addContactSubmission(
    name: string,
    email: string,
    subject: string,
    message: string,
    ipAddress?: string,
    userAgent?: string
  ): Promise<void> {
    if (!this.db) return;

    await this.db
      .prepare(
        'INSERT INTO contact_submissions (name, email, subject, message, ip_address, user_agent) VALUES (?, ?, ?, ?, ?, ?)'
      )
      .bind(name, email, subject, message, ipAddress || null, userAgent || null)
      .run();
  }

  /**
   * Get all contact submissions with optional filtering
   * @param status - Optional status filter ('new', 'read', 'replied', 'archived')
   * @param limit - Maximum number of results
   * @param offset - Offset for pagination
   */
  async getContactSubmissions(
    status?: string,
    limit?: number,
    offset?: number
  ): Promise<any[]> {
    if (!this.db) return [];

    let query = 'SELECT * FROM contact_submissions';
    const params: any[] = [];

    if (status) {
      query += ' WHERE status = ?';
      params.push(status);
    }

    query += ' ORDER BY created_at DESC';

    if (limit) {
      query += ' LIMIT ?';
      params.push(limit);
      if (offset) {
        query += ' OFFSET ?';
        params.push(offset);
      }
    }

    const result = await this.db.prepare(query).bind(...params).all();
    return result.results || [];
  }

  /**
   * Get a single contact submission by ID
   * @param id - The submission ID
   */
  async getContactSubmissionById(id: number): Promise<any | null> {
    if (!this.db) return null;

    return await this.db
      .prepare('SELECT * FROM contact_submissions WHERE id = ?')
      .bind(id)
      .first();
  }

  /**
   * Update contact submission status
   * @param id - The submission ID
   * @param status - New status ('new', 'read', 'replied', 'archived')
   */
  async updateContactSubmissionStatus(id: number, status: string): Promise<void> {
    if (!this.db) return;

    await this.db
      .prepare(
        'UPDATE contact_submissions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
      )
      .bind(status, id)
      .run();
  }

  /**
   * Get count of contact submissions by status
   * @param status - Optional status filter
   */
  async getContactSubmissionCount(status?: string): Promise<number> {
    if (!this.db) return 0;

    let query = 'SELECT COUNT(*) as count FROM contact_submissions';
    const params: any[] = [];

    if (status) {
      query += ' WHERE status = ?';
      params.push(status);
    }

    const result = await this.db
      .prepare(query)
      .bind(...params)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  /**
   * Delete a contact submission
   * @param id - The submission ID
   */
  async deleteContactSubmission(id: number): Promise<void> {
    if (!this.db) return;

    await this.db
      .prepare('DELETE FROM contact_submissions WHERE id = ?')
      .bind(id)
      .run();
  }

  /**
   * Check if IP address is rate limited
   * @param ipAddress - The IP address to check
   * @param maxSubmissions - Maximum submissions allowed
   * @param timeWindowMinutes - Time window in minutes
   * @returns true if rate limited, false otherwise
   */
  async isRateLimited(
    ipAddress: string,
    maxSubmissions: number = 3,
    timeWindowMinutes: number = 60
  ): Promise<boolean> {
    if (!this.db || !ipAddress || ipAddress === 'unknown') return false;

    // Calculate the time threshold
    const timeThreshold = new Date();
    timeThreshold.setMinutes(timeThreshold.getMinutes() - timeWindowMinutes);
    const timeThresholdStr = timeThreshold.toISOString();

    const result = await this.db
      .prepare(
        `SELECT COUNT(*) as count FROM contact_submissions
         WHERE ip_address = ? AND created_at > ?`
      )
      .bind(ipAddress, timeThresholdStr)
      .first<{ count: number }>();

    return (result?.count || 0) >= maxSubmissions;
  }

  /**
   * Get recent submission count for an IP
   * @param ipAddress - The IP address to check
   * @param timeWindowMinutes - Time window in minutes
   */
  async getRecentSubmissionCount(
    ipAddress: string,
    timeWindowMinutes: number = 60
  ): Promise<number> {
    if (!this.db || !ipAddress) return 0;

    const timeThreshold = new Date();
    timeThreshold.setMinutes(timeThreshold.getMinutes() - timeWindowMinutes);
    const timeThresholdStr = timeThreshold.toISOString();

    const result = await this.db
      .prepare(
        `SELECT COUNT(*) as count FROM contact_submissions
         WHERE ip_address = ? AND created_at > ?`
      )
      .bind(ipAddress, timeThresholdStr)
      .first<{ count: number }>();

    return result?.count || 0;
  }

  // ============================================================
  // AMAZON PRODUCTS METHODS
  // ============================================================

  /**
   * Get all Amazon products
   * @param statusFilter - Filter by status (optional)
   */
  async getAmazonProducts(statusFilter?: 'active' | 'inactive') {
    if (!this.db) return [];

    let query = 'SELECT * FROM amazon_products';
    const params: string[] = [];

    if (statusFilter) {
      query += ' WHERE status = ?';
      params.push(statusFilter);
    }

    query += ' ORDER BY display_order ASC, created_at DESC';

    const stmt = this.db.prepare(query);
    const result = params.length > 0
      ? await stmt.bind(...params).all()
      : await stmt.all();

    return result.results || [];
  }

  /**
   * Get Amazon product by ID
   * @param id - Product ID
   */
  async getAmazonProductById(id: number) {
    if (!this.db) return null;

    const result = await this.db
      .prepare('SELECT * FROM amazon_products WHERE id = ?')
      .bind(id)
      .first();

    return result || null;
  }

  /**
   * Get global Amazon products (products marked to show on all recipes)
   * @param placement - Filter by placement (optional)
   */
  async getGlobalAmazonProducts(placement?: 'article' | 'sidebar') {
    if (!this.db) return [];

    let query = `
      SELECT * FROM amazon_products
      WHERE status = 'active' AND show_globally = 1
    `;

    query += ' ORDER BY display_order ASC, created_at DESC';

    const result = await this.db.prepare(query).all();

    const products = result.results || [];

    // If placement is specified, filter products
    // For now, we'll return all global products regardless of placement
    // You can extend this later to add a placement field to products if needed
    return products;
  }

  /**
   * Add a new Amazon product
   * @param product - Product data
   */
  async addAmazonProduct(product: {
    title: string;
    image_url: string;
    price?: string;
    amazon_url: string;
    description?: string;
    status?: 'active' | 'inactive';
    show_globally?: boolean;
    display_order?: number;
  }) {
    if (!this.db) return null;

    const result = await this.db
      .prepare(
        `INSERT INTO amazon_products
        (title, image_url, price, amazon_url, description, status, show_globally, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .bind(
        product.title,
        product.image_url,
        product.price || null,
        product.amazon_url,
        product.description || null,
        product.status || 'active',
        product.show_globally ? 1 : 0,
        product.display_order || 0
      )
      .run();

    return result.meta.last_row_id;
  }

  /**
   * Update Amazon product
   * @param id - Product ID
   * @param product - Product data to update
   */
  async updateAmazonProduct(
    id: number,
    product: Partial<{
      title: string;
      image_url: string;
      price: string;
      amazon_url: string;
      description: string;
      status: 'active' | 'inactive';
      show_globally: boolean;
      display_order: number;
    }>
  ) {
    if (!this.db) return false;

    const updates: string[] = [];
    const values: any[] = [];

    Object.entries(product).forEach(([key, value]) => {
      updates.push(`${key} = ?`);
      // Convert boolean to 0/1 for show_globally
      if (key === 'show_globally') {
        values.push(value ? 1 : 0);
      } else {
        values.push(value);
      }
    });

    if (updates.length === 0) return false;

    updates.push('updated_at = CURRENT_TIMESTAMP');
    values.push(id);

    await this.db
      .prepare(
        `UPDATE amazon_products SET ${updates.join(', ')} WHERE id = ?`
      )
      .bind(...values)
      .run();

    return true;
  }

  /**
   * Delete Amazon product
   * @param id - Product ID
   */
  async deleteAmazonProduct(id: number) {
    if (!this.db) return false;

    await this.db
      .prepare('DELETE FROM amazon_products WHERE id = ?')
      .bind(id)
      .run();

    return true;
  }

  /**
   * Get products linked to a recipe
   * @param recipeId - Recipe ID
   * @param placement - Filter by placement (optional)
   */
  async getRecipeProducts(
    recipeId: number,
    placement?: 'article' | 'sidebar' | 'both'
  ) {
    if (!this.db) return [];

    let query = `
      SELECT
        rp.*,
        ap.id as product_id,
        ap.title,
        ap.image_url,
        ap.price,
        ap.amazon_url,
        ap.description,
        ap.status
      FROM recipe_products rp
      INNER JOIN amazon_products ap ON rp.product_id = ap.id
      WHERE rp.recipe_id = ? AND ap.status = 'active'
    `;

    const params: any[] = [recipeId];

    if (placement) {
      query += ' AND (rp.placement = ? OR rp.placement = "both")';
      params.push(placement);
    }

    query += ' ORDER BY rp.display_order ASC';

    const stmt = this.db.prepare(query);
    const result = await stmt.bind(...params).all();

    return result.results || [];
  }

  /**
   * Link products to a recipe
   * @param recipeId - Recipe ID
   * @param productId - Product ID
   * @param placement - Where to display the product
   * @param displayOrder - Display order
   */
  async linkProductToRecipe(
    recipeId: number,
    productId: number,
    placement: 'article' | 'sidebar' | 'both' = 'article',
    displayOrder: number = 0
  ) {
    if (!this.db) return null;

    const result = await this.db
      .prepare(
        `INSERT OR REPLACE INTO recipe_products
        (recipe_id, product_id, placement, display_order)
        VALUES (?, ?, ?, ?)`
      )
      .bind(recipeId, productId, placement, displayOrder)
      .run();

    return result.meta.last_row_id;
  }

  /**
   * Unlink product from recipe
   * @param recipeId - Recipe ID
   * @param productId - Product ID
   */
  async unlinkProductFromRecipe(recipeId: number, productId: number) {
    if (!this.db) return false;

    await this.db
      .prepare(
        'DELETE FROM recipe_products WHERE recipe_id = ? AND product_id = ?'
      )
      .bind(recipeId, productId)
      .run();

    return true;
  }

  /**
   * Update product placement in recipe
   * @param recipeId - Recipe ID
   * @param productId - Product ID
   * @param placement - New placement
   * @param displayOrder - New display order
   */
  async updateRecipeProductPlacement(
    recipeId: number,
    productId: number,
    placement?: 'article' | 'sidebar' | 'both',
    displayOrder?: number
  ) {
    if (!this.db) return false;

    const updates: string[] = [];
    const values: any[] = [];

    if (placement) {
      updates.push('placement = ?');
      values.push(placement);
    }

    if (displayOrder !== undefined) {
      updates.push('display_order = ?');
      values.push(displayOrder);
    }

    if (updates.length === 0) return false;

    values.push(recipeId, productId);

    await this.db
      .prepare(
        `UPDATE recipe_products SET ${updates.join(', ')}
         WHERE recipe_id = ? AND product_id = ?`
      )
      .bind(...values)
      .run();

    return true;
  }
}