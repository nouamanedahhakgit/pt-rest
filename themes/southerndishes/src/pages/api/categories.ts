import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

export const GET: APIRoute = async ({ locals }) => {
  try {
    const db = new DatabaseService(locals.runtime.env.DB);
    const categories = await db.getCategories();

    return new Response(JSON.stringify({
      success: true,
      data: categories
    }), {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=600'
      }
    });
  } catch (error) {
    console.error('Error fetching categories:', error);
    return new Response(JSON.stringify({
      success: false,
      error: 'Failed to fetch categories'
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
};