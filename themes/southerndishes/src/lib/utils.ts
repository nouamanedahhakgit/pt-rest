import type { RecipeData } from '../types/recipe';

export function formatTime(minutes: string | number): string {
  const mins = typeof minutes === 'string' ? parseInt(minutes) : minutes;
  if (mins < 60) {
    return `${mins} min`;
  }
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;

  if (remainingMins === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${remainingMins}m`;
}

export function createSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + '...';
}

export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '').trim();
}

export function generateRecipeJsonLd(recipe: RecipeData, url: string, imageUrl: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Recipe',
    name: recipe.name,
    description: recipe.summary,
    image: imageUrl,
    author: {
      '@type': 'Person',
      name: 'Recipe Website'
    },
    prepTime: `PT${recipe.prep_time}M`,
    cookTime: `PT${recipe.cook_time}M`,
    totalTime: `PT${recipe.total_time}M`,
    recipeYield: recipe.servings,
    nutrition: {
      '@type': 'NutritionInformation',
      calories: `${recipe.calories} calories`
    },
    recipeCategory: recipe.course,
    recipeCuisine: recipe.cuisine,
    keywords: recipe.keywords.join(', '),
    recipeIngredient: recipe.ingredients.map(
      ing => `${ing.amount} ${ing.unit} ${ing.name}`
    ),
    recipeInstructions: recipe.instructions.map((instruction, index) => ({
      '@type': 'HowToStep',
      position: index + 1,
      text: instruction
    })),
    url: url
  };
}

export function formatIngredient(ingredient: { amount: string; unit: string; name: string }): string {
  const { amount, unit, name } = ingredient;

  if (amount === '0' || !amount) {
    return name;
  }

  if (unit === 'to taste' || unit === 'as needed') {
    return `${name}, ${unit}`;
  }

  return `${amount} ${unit} ${name}`;
}

export function calculateReadTime(content: string): number {
  const wordsPerMinute = 200;
  const words = content.split(/\s+/).length;
  return Math.ceil(words / wordsPerMinute);
}

export function getImageUrl(path: string, width?: number, height?: number): string {
  if (path.startsWith('http')) {
    return path;
  }

  let url = path.startsWith('/') ? path : `/${path}`;

  if (width || height) {
    const params = new URLSearchParams();
    if (width) params.set('w', width.toString());
    if (height) params.set('h', height.toString());
    url += `?${params.toString()}`;
  }

  return url;
}

/**
 * Generate responsive image srcset for common image CDNs
 * Supports: Unsplash, Cloudinary, imgix, and Cloudflare Images
 */
export function getResponsiveSrcSet(imageUrl: string, widths: number[]): string {
  if (!imageUrl) return '';

  // Unsplash
  if (imageUrl.includes('unsplash.com')) {
    return widths
      .map(w => `${imageUrl}?w=${w}&q=80&fm=webp ${w}w`)
      .join(', ');
  }

  // Cloudinary
  if (imageUrl.includes('cloudinary.com')) {
    const baseUrl = imageUrl.split('/upload/')[0];
    const imagePath = imageUrl.split('/upload/')[1];
    return widths
      .map(w => `${baseUrl}/upload/w_${w},q_auto,f_auto/${imagePath} ${w}w`)
      .join(', ');
  }

  // imgix
  if (imageUrl.includes('imgix.net')) {
    return widths
      .map(w => `${imageUrl}?w=${w}&auto=format,compress ${w}w`)
      .join(', ');
  }

  // Cloudflare Images
  if (imageUrl.includes('imagedelivery.net')) {
    return widths
      .map(w => `${imageUrl}/w=${w} ${w}w`)
      .join(', ');
  }

  // Generic fallback - try standard width parameter
  const separator = imageUrl.includes('?') ? '&' : '?';
  return widths
    .map(w => `${imageUrl}${separator}w=${w} ${w}w`)
    .join(', ');
}

/**
 * Generate sizes attribute for responsive images
 */
export function getImageSizes(breakpoints: { maxWidth: string; size: string }[]): string {
  return breakpoints
    .map(bp => `(max-width: ${bp.maxWidth}) ${bp.size}`)
    .join(', ');
}

/**
 * Get a clean Pinterest-compatible image URL
 * Removes query parameters that may cause Pinterest validation issues
 */
export function getPinterestImageUrl(imageUrl: string): string {
  if (!imageUrl) return '';

  try {
    // Parse the URL to remove query parameters
    const url = new URL(imageUrl);
    // Return just the origin + pathname without query parameters
    return url.origin + url.pathname;
  } catch (e) {
    // If URL parsing fails (relative URL), just return as-is
    // Remove any query parameters manually
    return imageUrl.split('?')[0];
  }
}

/**
 * Replace template variables in content with settings values
 * Supports: {{site_name}}, {{site_domain}}, {{contact_email}}, {{site_owner}}, {{image_owner}}
 */
export function replaceTemplateVariables(
  content: string,
  settings: Record<string, string>
): string {
  if (!content) return '';

  let result = content;

  // Replace {{site_name}}
  if (settings.site_name) {
    result = result.replace(/\{\{site_name\}\}/g, settings.site_name);
  }

  // Replace {{site_domain}}
  if (settings.site_domain) {
    result = result.replace(/\{\{site_domain\}\}/g, settings.site_domain);
  }

  // Replace {{contact_email}}
  if (settings.contact_email) {
    result = result.replace(/\{\{contact_email\}\}/g, settings.contact_email);
  }


  // Replace {{site_owner}}
  if (settings.site_owner) {
    result = result.replace(/\{\{site_owner\}\}/g, settings.site_owner);
  }

  // Replace {{image_owner}}
  if (settings.image_owner) {
    result = result.replace(/\{\{image_owner\}\}/g, settings.image_owner);
  }
  return result;
}

/**
 * Decode HTML entities in text
 * Converts &#038; to &, &amp; to &, etc.
 */
export function decodeHtmlEntities(text: string): string {
  if (!text) return '';

  const entities: Record<string, string> = {
    '&#038;': '&',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
    '&#039;': "'",
    '&apos;': "'",
    '&nbsp;': ' ',
    '&#8217;': "'",
    '&#8216;': "'",
    '&#8220;': '"',
    '&#8221;': '"',
    '&#8211;': '–',
    '&#8212;': '—'
  };

  return text.replace(/&#?\w+;/g, match => entities[match] || match);
}