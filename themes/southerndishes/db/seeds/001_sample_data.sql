-- Insert sample categories
INSERT INTO categories (name, slug, description) VALUES
('Desserts', 'desserts', 'Sweet treats and dessert recipes'),
('Main Dishes', 'main-dishes', 'Hearty meals and entrees'),
('Appetizers', 'appetizers', 'Starters and finger foods'),
('Beverages', 'beverages', 'Drinks and cocktails'),
('Breakfast', 'breakfast', 'Morning meals and brunch items');

-- Insert sample recipes
INSERT INTO recipes (
  title,
  pin_image,
  pin_description,
  slug,
  article_content,
  featured_image,
  recipe_json,
  category_id,
  status
) VALUES
(
  'Ultimate Chewy Chocolate Chip Cookies',
  'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=400&h=600&fit=crop',
  'These incredibly soft and chewy chocolate chip cookies are loaded with chocolate chips and have the perfect texture.',
  'ultimate-chewy-chocolate-chip-cookies',
  '<p>There''s nothing quite like the smell of freshly baked chocolate chip cookies wafting through your kitchen. These <strong>Ultimate Chewy Chocolate Chip Cookies</strong> are everything you could want in a cookie - soft, chewy, packed with chocolate chips, and absolutely irresistible.</p>

<h2>What Makes These Cookies So Special?</h2>

<p>The secret to these incredibly chewy cookies lies in the perfect balance of ingredients. We use a combination of brown sugar and granulated sugar to achieve that ideal texture - the brown sugar adds moisture and chewiness, while the granulated sugar helps with spread and crispiness on the edges.</p>

<p>The key techniques that make these cookies extraordinary:</p>
<ul>
<li><strong>Room temperature butter:</strong> This ensures proper creaming with the sugars</li>
<li><strong>Don''t overmix:</strong> Once you add the flour, mix just until combined</li>
<li><strong>Slightly underbake:</strong> The cookies will continue cooking on the hot pan</li>
<li><strong>Rest the dough:</strong> Chilling for at least 30 minutes improves texture</li>
</ul>

<h2>Pro Tips for Perfect Cookies</h2>

<p>For the best results, I recommend using a kitchen scale to measure your flour. Too much flour will make your cookies dry and cakey. Also, don''t skip the resting time - it allows the flour to fully hydrate and results in a better texture.</p>

<p>These cookies freeze beautifully too! You can freeze the dough balls and bake them straight from frozen (just add an extra minute or two to the baking time).</p>',
  'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=800&h=600&fit=crop',
  '{"name":"Ultimate Chewy Chocolate Chip Cookies","summary":"Deliciously chewy chocolate chip cookies that are perfect for any occasion.","servings":"24","prep_time":"15","cook_time":"12","total_time":"30","calories":"150","course":"Dessert","cuisine":"American","keywords":["cookies","chocolate chip","dessert"],"notes":"Serve these cookies stacked on a plate, sprinkled with a pinch of sea salt on top for an extra touch of flavor and presentation. Enjoy with a tall glass of cold milk!","ingredients":[{"amount":"2.25","unit":"cups","name":"all-purpose flour"},{"amount":"1","unit":"teaspoon","name":"baking soda"},{"amount":"1","unit":"teaspoon","name":"salt"},{"amount":"0.75","unit":"cups","name":"unsalted butter, softened"},{"amount":"1","unit":"cup","name":"brown sugar, packed"},{"amount":"0.5","unit":"cups","name":"granulated sugar"},{"amount":"1","unit":"tablespoon","name":"vanilla extract"},{"amount":"2","unit":"large","name":"eggs"},{"amount":"2","unit":"cups","name":"semi-sweet chocolate chips"},{"amount":"0.5","unit":"cups","name":"chopped nuts (optional, walnuts or pecans)"}],"instructions":["Preheat your oven to 350°F (175°C) and line two baking sheets with parchment paper.","In a medium bowl, whisk together the flour, baking soda, and salt. Set aside.","In a large mixing bowl, cream together the softened butter, brown sugar, and granulated sugar using an electric mixer on medium speed until the mixture is light and fluffy (about 2-3 minutes).","Beat in the vanilla extract and one egg at a time, mixing well after each addition until fully incorporated.","Gradually add the dry ingredients to the wet mixture, mixing on low speed until just combined. Avoid over-mixing.","Fold in the semi-sweet chocolate chips and nuts (if using) with a spatula.","Scoop out tablespoons of dough and roll into balls. Place them on the prepared baking sheets about 2 inches apart.","Bake in the preheated oven for 10-12 minutes, or until the edges are golden and the centers have set but still look slightly underbaked (they will continue to cook on the baking sheet).","Remove from the oven and let the cookies cool on the baking sheets for 5 minutes before transferring them to wire racks to cool completely."]}',
  1,
  'published'
),
(
  'Classic Beef Lasagna',
  'https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=400&h=600&fit=crop',
  'A hearty, classic beef lasagna with layers of rich meat sauce, creamy cheese, and tender pasta.',
  'classic-beef-lasagna',
  '<p>This <strong>Classic Beef Lasagna</strong> is the ultimate comfort food - layers upon layers of rich meat sauce, creamy ricotta, melted mozzarella, and tender pasta that will have your family asking for seconds.</p>

<h2>The Perfect Lasagna Every Time</h2>

<p>Making lasagna might seem intimidating, but with the right technique, it''s actually quite straightforward. The key is building those beautiful layers and letting the flavors meld together during baking.</p>

<p>This recipe serves 8-10 people and is perfect for feeding a crowd or meal prep for the week. The leftovers taste even better the next day!</p>

<h2>Layering Tips</h2>

<p>Start with a thin layer of meat sauce on the bottom to prevent sticking. Then alternate between noodles, ricotta mixture, meat sauce, and cheese. Don''t forget to cover with foil for most of the baking time to prevent the top from burning.</p>',
  'https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=800&h=600&fit=crop',
  '{"name":"Classic Beef Lasagna","summary":"A hearty, classic beef lasagna with layers of rich meat sauce, creamy cheese, and tender pasta.","servings":"10","prep_time":"30","cook_time":"45","total_time":"75","calories":"420","course":"Main Course","cuisine":"Italian","keywords":["lasagna","beef","pasta","comfort food"],"notes":"Let the lasagna rest for 10-15 minutes after baking for easier slicing. This also freezes well - just thaw overnight and reheat.","ingredients":[{"amount":"1","unit":"pound","name":"lasagna noodles"},{"amount":"1","unit":"pound","name":"ground beef"},{"amount":"1","unit":"medium","name":"onion, diced"},{"amount":"3","unit":"cloves","name":"garlic, minced"},{"amount":"24","unit":"oz","name":"marinara sauce"},{"amount":"15","unit":"oz","name":"ricotta cheese"},{"amount":"1","unit":"large","name":"egg"},{"amount":"3","unit":"cups","name":"mozzarella cheese, shredded"},{"amount":"0.75","unit":"cups","name":"Parmesan cheese, grated"},{"amount":"2","unit":"tablespoons","name":"fresh basil, chopped"},{"amount":"1","unit":"teaspoon","name":"Italian seasoning"},{"amount":"0.5","unit":"teaspoon","name":"salt"},{"amount":"0.25","unit":"teaspoon","name":"black pepper"}],"instructions":["Preheat oven to 375°F. Cook lasagna noodles according to package directions until al dente. Drain and set aside.","In a large skillet, brown the ground beef over medium-high heat. Add onion and garlic, cook until softened.","Stir in marinara sauce, Italian seasoning, salt, and pepper. Simmer for 10 minutes.","In a bowl, mix ricotta cheese, egg, and fresh basil until well combined.","Spread a thin layer of meat sauce in the bottom of a 9x13 inch baking dish.","Layer 3 noodles, half the ricotta mixture, half the remaining meat sauce, and 1 cup mozzarella.","Repeat layers, then top with remaining noodles, remaining mozzarella, and Parmesan cheese.","Cover with foil and bake for 25 minutes. Remove foil and bake 15-20 minutes until bubbly and golden.","Let rest 10-15 minutes before serving."]}',
  2,
  'published'
),
(
  'Spinach and Artichoke Dip',
  'https://images.unsplash.com/photo-1541014741259-de529411b96a?w=400&h=600&fit=crop',
  'Creamy, cheesy spinach and artichoke dip that''s perfect for parties and gatherings.',
  'spinach-artichoke-dip',
  '<p>This <strong>Spinach and Artichoke Dip</strong> is the ultimate party appetizer! Creamy, cheesy, and loaded with flavor, it''s always the first thing to disappear at any gathering.</p>

<h2>Party Perfect</h2>

<p>Whether you''re hosting a game day party or a casual get-together, this dip is guaranteed to be a hit. Serve it warm with tortilla chips, crusty bread, or fresh vegetables for dipping.</p>

<p>The combination of cream cheese, mayonnaise, and Parmesan creates an incredibly rich and creamy base, while the spinach and artichokes add texture and flavor.</p>',
  'https://images.unsplash.com/photo-1541014741259-de529411b96a?w=800&h=600&fit=crop',
  '{"name":"Spinach and Artichoke Dip","summary":"Creamy, cheesy spinach and artichoke dip that''s perfect for parties and gatherings.","servings":"8","prep_time":"10","cook_time":"25","total_time":"35","calories":"180","course":"Appetizer","cuisine":"American","keywords":["dip","spinach","artichoke","appetizer","party"],"notes":"Can be made ahead and refrigerated. Just reheat in the oven before serving. Also great with pita chips or baguette slices.","ingredients":[{"amount":"8","unit":"oz","name":"cream cheese, softened"},{"amount":"0.5","unit":"cups","name":"mayonnaise"},{"amount":"0.5","unit":"cups","name":"sour cream"},{"amount":"1","unit":"cup","name":"Parmesan cheese, grated"},{"amount":"0.75","unit":"cups","name":"mozzarella cheese, shredded"},{"amount":"3","unit":"cloves","name":"garlic, minced"},{"amount":"10","unit":"oz","name":"frozen spinach, thawed and drained"},{"amount":"1","unit":"cup","name":"artichoke hearts, chopped"},{"amount":"0.25","unit":"teaspoon","name":"red pepper flakes"},{"amount":"1","unit":"teaspoon","name":"salt"},{"amount":"0.5","unit":"teaspoon","name":"black pepper"}],"instructions":["Preheat oven to 375°F.","Squeeze excess water from thawed spinach using paper towels or clean kitchen towel.","In a large bowl, mix cream cheese, mayonnaise, sour cream, 3/4 cup Parmesan, 1/2 cup mozzarella, and garlic.","Stir in spinach, artichoke hearts, red pepper flakes, salt, and pepper until well combined.","Transfer to a greased 8x8 or 9x9 inch baking dish.","Top with remaining mozzarella and Parmesan cheese.","Bake for 20-25 minutes until hot and bubbly with golden top.","Serve immediately with tortilla chips, bread, or vegetables."]}',
  3,
  'published'
);