import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

interface SettingBody {
  key: string;
  value: string;
  description?: string;
}

// ───────────────── GET /api/settings ─────────────────
// Fetch all settings or a specific setting by key
// Protected with Authorization: Bearer <API_TOKEN>

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
    const key = searchParams.get('key');

    // If key is provided, return single setting
    if (key) {
      const setting = await db.getSetting(key);

      if (!setting) {
        return new Response(
          JSON.stringify({
            success: false,
            error: `Setting with key '${key}' not found`,
          }),
          {
            status: 404,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      return new Response(
        JSON.stringify({
          success: true,
          data: setting,
        }),
        {
          headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'private, max-age=60',
          },
        }
      );
    }

    // Otherwise, return all settings
    const settings = await db.getAllSettings();

    return new Response(
      JSON.stringify({
        success: true,
        data: settings,
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'private, max-age=60',
        },
      }
    );
  } catch (error) {
    console.error('Error fetching settings:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch settings',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── POST /api/settings ─────────────────
// Create or update a setting (UPSERT)
// Protected with Authorization: Bearer <API_TOKEN>

export const POST: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const body = (await request.json()) as SettingBody;

    // Validate required fields
    if (!body.key || !body.value) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Missing required fields (key, value)',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Check if setting exists
    const { results: existing } = await db
      .prepare('SELECT * FROM settings WHERE key = ?1')
      .bind(body.key)
      .all();

    let result;

    if (existing.length > 0) {
      // Update existing setting
      await db
        .prepare(
          'UPDATE settings SET value = ?1, description = ?2, updated_at = CURRENT_TIMESTAMP WHERE key = ?3'
        )
        .bind(body.value, body.description || existing[0].description, body.key)
        .run();

      // Fetch updated setting
      const { results } = await db
        .prepare('SELECT * FROM settings WHERE key = ?1')
        .bind(body.key)
        .all();

      result = results[0];
    } else {
      // Insert new setting
      await db
        .prepare(
          'INSERT INTO settings (key, value, description) VALUES (?1, ?2, ?3)'
        )
        .bind(body.key, body.value, body.description || null)
        .run();

      // Fetch newly created setting
      const { results } = await db
        .prepare('SELECT * FROM settings WHERE key = ?1')
        .bind(body.key)
        .all();

      result = results[0];
    }

    return new Response(
      JSON.stringify({
        success: true,
        data: result,
        message: existing.length > 0 ? 'Setting updated' : 'Setting created',
      }),
      {
        status: existing.length > 0 ? 200 : 201,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error creating/updating setting:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to create/update setting',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── PUT /api/settings ─────────────────
// Update an existing setting
// Protected with Authorization: Bearer <API_TOKEN>

export const PUT: APIRoute = async ({ request, locals }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const body = (await request.json()) as Partial<SettingBody> & { key: string };

    // Key is required for updates
    if (!body.key) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Setting key is required for updates',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Check if setting exists
    const { results: existing } = await db
      .prepare('SELECT * FROM settings WHERE key = ?1')
      .bind(body.key)
      .all();

    if (existing.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: `Setting with key '${body.key}' not found`,
        }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Build update query dynamically based on provided fields
    const updateFields: string[] = [];
    const values: any[] = [];

    if (body.value !== undefined) {
      updateFields.push('value = ?');
      values.push(body.value);
    }
    if (body.description !== undefined) {
      updateFields.push('description = ?');
      values.push(body.description);
    }

    if (updateFields.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'No fields to update',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Add updated_at timestamp
    updateFields.push('updated_at = CURRENT_TIMESTAMP');

    // Add key as the last parameter
    values.push(body.key);

    // Execute update
    const updateQuery = `UPDATE settings SET ${updateFields.join(', ')} WHERE key = ?${values.length}`;
    await db.prepare(updateQuery).bind(...values).run();

    // Fetch updated setting
    const { results } = await db
      .prepare('SELECT * FROM settings WHERE key = ?1')
      .bind(body.key)
      .all();

    return new Response(
      JSON.stringify({
        success: true,
        data: results[0],
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error updating setting:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to update setting',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};

// ───────────────── DELETE /api/settings ─────────────────
// Delete a setting by key
// Protected with Authorization: Bearer <API_TOKEN>

export const DELETE: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = runtimeEnv.DB;
    const apiToken = runtimeEnv.API_TOKEN;

    // Authorization
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const searchParams = new URL(url).searchParams;
    const key = searchParams.get('key');

    if (!key) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Setting key is required',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Check if setting exists
    const { results: existing } = await db
      .prepare('SELECT * FROM settings WHERE key = ?1')
      .bind(key)
      .all();

    if (existing.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: `Setting with key '${key}' not found`,
        }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Delete setting
    await db.prepare('DELETE FROM settings WHERE key = ?1').bind(key).run();

    return new Response(
      JSON.stringify({
        success: true,
        message: `Setting '${key}' deleted successfully`,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error deleting setting:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to delete setting',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};
