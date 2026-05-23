import type { APIRoute } from 'astro';
import { DatabaseService } from '../../lib/database';

// ───────────────── POST /api/contact ─────────────────
// Submit a contact form

export const POST: APIRoute = async ({ request, locals, clientAddress }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const db = new DatabaseService(runtimeEnv.DB);

    // Get IP address
    const ipAddress = clientAddress || request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || 'unknown';

    // Rate Limiting: Check if IP has exceeded submission limit
    // Default: 3 submissions per hour
    const isLimited = await db.isRateLimited(ipAddress, 3, 60);
    if (isLimited) {
      const recentCount = await db.getRecentSubmissionCount(ipAddress, 60);
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Too many submissions. Please try again later.',
          details: `You have submitted ${recentCount} messages in the last hour. Please wait before submitting again.`
        }),
        {
          status: 429, // Too Many Requests
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': '3600' // Retry after 1 hour
          }
        }
      );
    }

    // Parse form data
    const body = await request.json() as {
      name: string;
      email: string;
      subject: string;
      message: string;
    };

    // Validate request body exists and is not too large
    const contentLength = request.headers.get('Content-Length');
    if (contentLength && parseInt(contentLength) > 10000) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Request body too large'
        }),
        {
          status: 413, // Payload Too Large
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Validate required fields
    if (!body.name || !body.email || !body.subject || !body.message) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'All fields are required',
          fields: {
            name: !body.name ? 'Name is required' : null,
            email: !body.email ? 'Email is required' : null,
            subject: !body.subject ? 'Subject is required' : null,
            message: !body.message ? 'Message is required' : null,
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Sanitize inputs - trim whitespace
    body.name = body.name.trim();
    body.email = body.email.trim().toLowerCase();
    body.subject = body.subject.trim();
    body.message = body.message.trim();

    // Check for suspicious patterns (common spam indicators)
    const spamPatterns = [
      /\b(viagra|cialis|pharmacy|casino|lottery|prize)\b/i,
      /(http|https):\/\/.*\.(ru|cn|tk)/i, // Suspicious domains
      /<script|<iframe|javascript:/i, // Script injection attempts
      /\[url=|BBCode/i // Forum spam
    ];

    const suspiciousContent = [body.name, body.email, body.subject, body.message].join(' ');
    for (const pattern of spamPatterns) {
      if (pattern.test(suspiciousContent)) {
        // Log but don't tell the spammer
        console.warn('Potential spam detected from IP:', ipAddress);
        // Return success to not reveal detection
        return new Response(
          JSON.stringify({
            success: true,
            message: 'Your message has been sent successfully! We\'ll get back to you soon.'
          }),
          {
            status: 201,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      }
    }

    // Validate minimum message length (prevent junk submissions)
    if (body.message.length < 10) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Message is too short',
          fields: {
            message: 'Please provide a more detailed message (at least 10 characters)'
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(body.email)) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Invalid email address',
          fields: {
            email: 'Please enter a valid email address'
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Validate field lengths
    if (body.name.length > 100) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Name is too long',
          fields: {
            name: 'Name must be less than 100 characters'
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    if (body.subject.length > 200) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Subject is too long',
          fields: {
            subject: 'Subject must be less than 200 characters'
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    if (body.message.length > 5000) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Message is too long',
          fields: {
            message: 'Message must be less than 5000 characters'
          }
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Get user agent
    const userAgent = request.headers.get('User-Agent') || 'unknown';

    // Save to database
    await db.addContactSubmission(
      body.name,
      body.email,
      body.subject,
      body.message,
      ipAddress,
      userAgent
    );

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Your message has been sent successfully! We\'ll get back to you soon.'
      }),
      {
        status: 201,
        headers: { 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error submitting contact form:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to send message. Please try again later.'
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
};

// ───────────────── GET /api/contact ─────────────────
// Get all contact submissions (admin only)

export const GET: APIRoute = async ({ url, locals, request }) => {
  try {
    const runtimeEnv = (locals as any).runtime?.env ?? {};
    const apiToken = runtimeEnv.API_TOKEN as string | undefined;

    // Authorization - require API token for admin access
    const authHeader = request.headers.get('Authorization');
    if (apiToken && authHeader !== `Bearer ${apiToken}`) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const db = new DatabaseService(runtimeEnv.DB);
    const searchParams = new URL(url).searchParams;

    const status = searchParams.get('status') || undefined;
    const limit = searchParams.get('limit') ? parseInt(searchParams.get('limit')!) : 50;
    const offset = searchParams.get('offset') ? parseInt(searchParams.get('offset')!) : 0;

    const [submissions, totalCount] = await Promise.all([
      db.getContactSubmissions(status, limit, offset),
      db.getContactSubmissionCount(status)
    ]);

    return new Response(
      JSON.stringify({
        success: true,
        data: submissions,
        pagination: {
          total: totalCount,
          limit,
          offset,
          hasMore: offset + limit < totalCount
        }
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'private, no-cache'
        }
      }
    );

  } catch (error) {
    console.error('Error fetching contact submissions:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: 'Failed to fetch contact submissions'
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
};
