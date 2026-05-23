globalThis.process ??= {}; globalThis.process.env ??= {};
function formatTime(minutes) {
  const mins = typeof minutes === "string" ? parseInt(minutes) : minutes;
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
function truncateText(text, maxLength) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + "...";
}
function stripHtml(html) {
  return html.replace(/<[^>]*>/g, "").trim();
}
function generateRecipeJsonLd(recipe, url, imageUrl) {
  return {
    "@context": "https://schema.org",
    "@type": "Recipe",
    name: recipe.name,
    description: recipe.summary,
    image: imageUrl,
    author: {
      "@type": "Person",
      name: "Recipe Website"
    },
    prepTime: `PT${recipe.prep_time}M`,
    cookTime: `PT${recipe.cook_time}M`,
    totalTime: `PT${recipe.total_time}M`,
    recipeYield: recipe.servings,
    nutrition: {
      "@type": "NutritionInformation",
      calories: `${recipe.calories} calories`
    },
    recipeCategory: recipe.course,
    recipeCuisine: recipe.cuisine,
    keywords: recipe.keywords.join(", "),
    recipeIngredient: recipe.ingredients.map(
      (ing) => `${ing.amount} ${ing.unit} ${ing.name}`
    ),
    recipeInstructions: recipe.instructions.map((instruction, index) => ({
      "@type": "HowToStep",
      position: index + 1,
      text: instruction
    })),
    url
  };
}
function formatIngredient(ingredient) {
  const { amount, unit, name } = ingredient;
  if (amount === "0" || !amount) {
    return name;
  }
  if (unit === "to taste" || unit === "as needed") {
    return `${name}, ${unit}`;
  }
  return `${amount} ${unit} ${name}`;
}
function calculateReadTime(content) {
  const wordsPerMinute = 200;
  const words = content.split(/\s+/).length;
  return Math.ceil(words / wordsPerMinute);
}
function getResponsiveSrcSet(imageUrl, widths) {
  if (!imageUrl) return "";
  if (imageUrl.includes("unsplash.com")) {
    return widths.map((w) => `${imageUrl}?w=${w}&q=80&fm=webp ${w}w`).join(", ");
  }
  if (imageUrl.includes("cloudinary.com")) {
    const baseUrl = imageUrl.split("/upload/")[0];
    const imagePath = imageUrl.split("/upload/")[1];
    return widths.map((w) => `${baseUrl}/upload/w_${w},q_auto,f_auto/${imagePath} ${w}w`).join(", ");
  }
  if (imageUrl.includes("imgix.net")) {
    return widths.map((w) => `${imageUrl}?w=${w}&auto=format,compress ${w}w`).join(", ");
  }
  if (imageUrl.includes("imagedelivery.net")) {
    return widths.map((w) => `${imageUrl}/w=${w} ${w}w`).join(", ");
  }
  const separator = imageUrl.includes("?") ? "&" : "?";
  return widths.map((w) => `${imageUrl}${separator}w=${w} ${w}w`).join(", ");
}
function getImageSizes(breakpoints) {
  return breakpoints.map((bp) => `(max-width: ${bp.maxWidth}) ${bp.size}`).join(", ");
}
function getPinterestImageUrl(imageUrl) {
  if (!imageUrl) return "";
  try {
    const url = new URL(imageUrl);
    return url.origin + url.pathname;
  } catch (e) {
    return imageUrl.split("?")[0];
  }
}

export { formatIngredient as a, generateRecipeJsonLd as b, calculateReadTime as c, getResponsiveSrcSet as d, getImageSizes as e, formatTime as f, getPinterestImageUrl as g, stripHtml as s, truncateText as t };
