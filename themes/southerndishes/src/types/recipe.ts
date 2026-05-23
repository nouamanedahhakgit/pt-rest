export interface RecipeIngredient {
  amount: string;
  unit: string;
  name: string;
}

export interface RecipeData {
  name: string;
  summary: string;
  servings: string;
  prep_time: string;
  cook_time: string;
  total_time: string;
  calories: string;
  course: string;
  cuisine: string;
  keywords: string[];
  notes: string;
  ingredients: RecipeIngredient[];
  instructions: string[];
}

export interface Recipe {
  id: number;
  title: string;
  pin_image?: string;
  pin_description?: string;
  board_name?: string;
  slug: string;
  article_content: string;
  featured_image: string;
  recipe_json: string;
  post_tag?: string;
  category_id?: number;
  author_id?: number;
  status: 'draft' | 'published';
  created_at: string;
  updated_at: string;
  category?: Category;
  author?: Author;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description?: string;
  image?: string;
  created_at: string;
  updated_at: string;
}

export interface Author {
  id: number;
  name: string;
  slug: string;
  title?: string;
  image_url?: string;
  showcase_image?: string;
  image_owner?: string;
  bio?: string;
  created_at: string;
  updated_at: string;
}

export interface RecipeWithData extends Omit<Recipe, 'recipe_json'> {
  recipe_data: RecipeData;
}

export interface DatabaseSchema {
  recipes: Recipe;
  categories: Category;
  authors: Author;
}

export interface RecipeCardProps {
  recipe: Recipe | RecipeWithData;
  showCategory?: boolean;
  className?: string;
}

export interface RecipePageProps {
  recipe: RecipeWithData;
  relatedRecipes?: Recipe[];
}

export interface CategoryPageProps {
  category: Category;
  recipes: Recipe[];
  currentPage: number;
  totalPages: number;
}

export interface AuthorPageProps {
  author: Author;
  recipes: Recipe[];
  currentPage: number;
  totalPages: number;
}

export interface HomePageProps {
  featuredRecipes: Recipe[];
  latestRecipes: Recipe[];
  categories: Category[];
}