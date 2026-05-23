import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

/**
 * GET /api/amazon-products
 * Get all Amazon products or filter by status
 * Query params:
 *   - status: 'active' | 'inactive' (optional)
 */
export const GET: APIRoute = async ({ locals, url }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const status = url.searchParams.get('status') as 'active' | 'inactive' | null;

    const products = await db.getAmazonProducts(status || undefined);

    return new Response(
      JSON.stringify({
        success: true,
        data: products,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=300', // Cache for 5 minutes
        },
      }
    );
  } catch (error) {
    console.error('Error fetching Amazon products:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch products',
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
};

/**
 * POST /api/amazon-products
 * Create a new Amazon product
 * Body:
 *   - title: string (required)
 *   - image_url: string (required)
 *   - amazon_url: string (required)
 *   - price: string (optional)
 *   - description: string (optional)
 *   - status: 'active' | 'inactive' (optional, default: 'active')
 *   - show_globally: boolean (optional, default: false) - Show on all recipe pages
 *   - display_order: number (optional, default: 0)
 */
export const POST: APIRoute = async ({ locals, request }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const body = await request.json();

    // Validate required fields
    if (!body.title || !body.image_url || !body.amazon_url) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Missing required fields: title, image_url, amazon_url',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    const productId = await db.addAmazonProduct({
      title: body.title,
      image_url: body.image_url,
      price: body.price,
      amazon_url: body.amazon_url,
      description: body.description,
      status: body.status || 'active',
      show_globally: body.show_globally || false,
      display_order: body.display_order || 0,
    });

    const product = await db.getAmazonProductById(productId as number);

    return new Response(
      JSON.stringify({
        success: true,
        data: product,
      }),
      {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error creating Amazon product:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to create product',
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
};

/**
 * PUT /api/amazon-products
 * Update an Amazon product
 * Body:
 *   - id: number (required)
 *   - title, image_url, price, amazon_url, description, status, show_globally, display_order (optional)
 */
export const PUT: APIRoute = async ({ locals, request }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const body = await request.json();

    if (!body.id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Product ID is required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    // Check if product exists
    const existing = await db.getAmazonProductById(body.id);
    if (!existing) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Product not found',
        }),
        {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    const updateData: any = {};
    const allowedFields = [
      'title',
      'image_url',
      'price',
      'amazon_url',
      'description',
      'status',
      'show_globally',
      'display_order',
    ];

    allowedFields.forEach((field) => {
      if (body[field] !== undefined) {
        updateData[field] = body[field];
      }
    });

    await db.updateAmazonProduct(body.id, updateData);
    const updatedProduct = await db.getAmazonProductById(body.id);

    return new Response(
      JSON.stringify({
        success: true,
        data: updatedProduct,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error updating Amazon product:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to update product',
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
};

/**
 * DELETE /api/amazon-products
 * Delete an Amazon product
 * Query params:
 *   - id: number (required)
 */
export const DELETE: APIRoute = async ({ locals, url }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const id = url.searchParams.get('id');

    if (!id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Product ID is required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    const productId = parseInt(id);

    // Check if product exists
    const existing = await db.getAmazonProductById(productId);
    if (!existing) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Product not found',
        }),
        {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    await db.deleteAmazonProduct(productId);

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Product deleted successfully',
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error deleting Amazon product:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to delete product',
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
};
