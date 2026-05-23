import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

// ───────────────── GET /api/redirects ─────────────────
// Get all redirects or check a specific old_slug

export const GET: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const apiToken = runtimeEnv.API_TOKEN as string | undefined;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const db = new DatabaseService(runtimeEnv.DB);
    const searchParams = new URL(url).searchParams;
    const oldSlug = searchParams.get('old_slug');

    // If old_slug is provided, check for specific redirect
    if (oldSlug) {
      const redirectUrl = await db.getRedirect(oldSlug);

      if (redirectUrl) {
        return new Response(
          JSON.stringify({
            success: true,
            data: { old_slug: oldSlug, new_url: redirectUrl }
          }),
          {
            headers: {
              'Content-Type': 'application/json',
              'Cache-Control': 'public, max-age=300',
            },
          }
        );
      } else {
        return new Response(
          JSON.stringify({
            success: false,
            error: 'Redirect not found'
          }),
          {
            status: 404,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
    }

    // Otherwise, get all redirects
    const result = await runtimeEnv.DB
      .prepare('SELECT * FROM redirects ORDER BY created_at DESC')
      .all();

    return new Response(
      JSON.stringify({
        success: true,
        data: result.results || []
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=300',
        },
      }
    );
  } catch (error) {
    console.error('Error fetching redirects:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch redirects',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── POST /api/redirects ─────────────────
// Add single or multiple redirects

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = new DatabaseService(runtimeEnv.DB);
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const body = await request.json() as {
      old_slug?: string;
      old_slugs?: string[];
      new_url: string;
    };

    // Validate required fields
    if (!body.new_url) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'new_url is required'
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    if (!body.old_slug && !body.old_slugs) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Either old_slug or old_slugs is required'
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Handle multiple old slugs
    if (body.old_slugs && Array.isArray(body.old_slugs)) {
      await db.addMultipleRedirects(body.old_slugs, body.new_url);

      return new Response(
        JSON.stringify({
          success: true,
          message: `Added ${body.old_slugs.length} redirects to ${body.new_url}`,
          data: {
            old_slugs: body.old_slugs,
            new_url: body.new_url,
            count: body.old_slugs.length
          }
        }),
        {
          status: 201,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Handle single old slug
    if (body.old_slug) {
      await db.addRedirect(body.old_slug, body.new_url);

      return new Response(
        JSON.stringify({
          success: true,
          message: `Redirect added: ${body.old_slug} → ${body.new_url}`,
          data: {
            old_slug: body.old_slug,
            new_url: body.new_url
          }
        }),
        {
          status: 201,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    return new Response(
      JSON.stringify({
        success: false,
        error: 'Invalid request'
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error creating redirect:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message || 'Failed to create redirect'
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
};

// ───────────────── DELETE /api/redirects ─────────────────
// Delete a redirect by old_slug

export const DELETE: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = new DatabaseService(runtimeEnv.DB);
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const searchParams = new URL(url).searchParams;
    const oldSlug = searchParams.get('old_slug');

    if (!oldSlug) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'old_slug query parameter is required'
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    await db.deleteRedirect(oldSlug);

    return new Response(
      JSON.stringify({
        success: true,
        message: `Redirect deleted: ${oldSlug}`
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error deleting redirect:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to delete redirect'
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
};
