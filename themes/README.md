# Themes

Global, project-agnostic static-site themes. Each subfolder is a theme; a project
in `config/sites.json` selects a theme via `theme_slug` and is then deployable to
Cloudflare Pages via the **CF UPLOAD** button.

## Layout

```
themes/<slug>/
  theme.json        Required. Metadata + suggested cloudflare project name.
  index.html        Jinja2 template, rendered once into <build>/index.html
  article.html      Jinja2 template, rendered per row into <build>/article/<slug>/index.html
  static/           Copied as-is into <build>/static/
```

## theme.json schema

```json
{
  "slug": "default",                  // must match folder name
  "display_name": "Default Recipes",
  "description": "...",
  "version": "1.0.0",
  "author": "you",
  "cf_project_name": "",              // optional default CF Pages project; can be overridden per site
  "data_source": {
    "excel": "Recipes.xlsx",
    "required_columns": ["Title", "article", "image_1"],
    "optional_columns": ["pinterest_title", "pinterest_description", "pinterest_image", "categories"]
  }
}
```

## Render context

`index.html` receives:

- `site` — `{ title, description, year, built_at, version }`
- `articles` — list of `{ slug, title, excerpt, featured_image, pinterest_image, category, url, html_body, meta_description }`
- `categories` — distinct category names from the project

`article.html` receives the same `site`, plus `article` (one entry from the
`articles` list).

The `slug` filter (lowercase, hyphenated) is available in both templates.

## Adding a new theme

1. Copy `themes/default/` to `themes/<your-slug>/`.
2. Edit `theme.json` — update `slug`, `display_name`, optionally `cf_project_name`.
3. Edit `index.html`, `article.html`, `static/style.css` to taste.
4. On the dashboard project card, pick the new theme from the **Theme** dropdown.
