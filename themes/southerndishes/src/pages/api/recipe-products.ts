import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

/**
 * GET /api/recipe-products
 * Get products linked to a recipe
 * Query params:
 *   - recipe_id: number (required)
 *   - placement: 'article' | 'sidebar' | 'both' (optional)
 */
export const GET: APIRoute = async ({ locals, url }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const recipeId = url.searchParams.get('recipe_id');
    const placement = url.searchParams.get('placement') as 'article' | 'sidebar' | 'both' | null;

    if (!recipeId) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'recipe_id is required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    const products = await db.getRecipeProducts(
      parseInt(recipeId),
      placement || undefined
    );

    return new Response(
      JSON.stringify({
        success: true,
        data: products,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=300',
        },
      }
    );
  } catch (error) {
    console.error('Error fetching recipe products:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch recipe products',
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
 * POST /api/recipe-products
 * Link a product to a recipe
 * Body:
 *   - recipe_id: number (required)
 *   - product_id: number (required)
 *   - placement: 'article' | 'sidebar' | 'both' (optional, default: 'article')
 *   - display_order: number (optional, default: 0)
 */
export const POST: APIRoute = async ({ locals, request }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const body = await request.json();

    if (!body.recipe_id || !body.product_id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'recipe_id and product_id are required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    await db.linkProductToRecipe(
      body.recipe_id,
      body.product_id,
      body.placement || 'article',
      body.display_order || 0
    );

    const products = await db.getRecipeProducts(body.recipe_id);

    return new Response(
      JSON.stringify({
        success: true,
        data: products,
      }),
      {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error linking product to recipe:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to link product to recipe',
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
 * PUT /api/recipe-products
 * Update product placement in recipe
 * Body:
 *   - recipe_id: number (required)
 *   - product_id: number (required)
 *   - placement: 'article' | 'sidebar' | 'both' (optional)
 *   - display_order: number (optional)
 */
export const PUT: APIRoute = async ({ locals, request }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const body = await request.json();

    if (!body.recipe_id || !body.product_id) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'recipe_id and product_id are required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    await db.updateRecipeProductPlacement(
      body.recipe_id,
      body.product_id,
      body.placement,
      body.display_order
    );

    const products = await db.getRecipeProducts(body.recipe_id);

    return new Response(
      JSON.stringify({
        success: true,
        data: products,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error updating recipe product:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to update recipe product',
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
 * DELETE /api/recipe-products
 * Unlink a product from a recipe
 * Query params:
 *   - recipe_id: number (required)
 *   - product_id: number (required)
 */
export const DELETE: APIRoute = async ({ locals, url }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const recipeId = url.searchParams.get('recipe_id');
    const productId = url.searchParams.get('product_id');

    if (!recipeId || !productId) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'recipe_id and product_id are required',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    await db.unlinkProductFromRecipe(parseInt(recipeId), parseInt(productId));

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Product unlinked from recipe successfully',
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  } catch (error) {
    console.error('Error unlinking product from recipe:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to unlink product from recipe',
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
