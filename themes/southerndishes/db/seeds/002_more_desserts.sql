-- Add more dessert recipes for testing
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
  'Decadent Chocolate Brownies',
  'https://images.unsplash.com/photo-1607920591413-4ec007e70023?w=400&h=600&fit=crop',
  'Rich, fudgy chocolate brownies with a crackly top and gooey center.',
  'decadent-chocolate-brownies',
  '<p>These <strong>Decadent Chocolate Brownies</strong> are the ultimate chocolate lover''s dream. With a crispy top and an incredibly fudgy center, these brownies are pure indulgence.</p>

<h2>The Perfect Brownie Texture</h2>

<p>The secret to these amazing brownies is using high-quality cocoa powder and melted chocolate. The combination creates an intense chocolate flavor that''s simply irresistible.</p>

<p>Don''t overbake these! They should still look slightly underdone in the center when you take them out of the oven.</p>',
  'https://images.unsplash.com/photo-1607920591413-4ec007e70023?w=800&h=600&fit=crop',
  '{"name":"Decadent Chocolate Brownies","summary":"Rich, fudgy chocolate brownies with a crackly top and gooey center.","servings":"16","prep_time":"15","cook_time":"30","total_time":"45","calories":"220","course":"Dessert","cuisine":"American","keywords":["brownies","chocolate","dessert","baking"],"notes":"Cut into squares when completely cool for cleaner edges. Store in an airtight container.","ingredients":[{"amount":"1","unit":"cup","name":"unsalted butter"},{"amount":"2","unit":"cups","name":"granulated sugar"},{"amount":"4","unit":"large","name":"eggs"},{"amount":"1.5","unit":"cups","name":"all-purpose flour"},{"amount":"1","unit":"cup","name":"cocoa powder"},{"amount":"1","unit":"teaspoon","name":"salt"},{"amount":"1","unit":"teaspoon","name":"vanilla extract"},{"amount":"1","unit":"cup","name":"chocolate chips"}],"instructions":["Preheat oven to 350°F. Grease a 9x13 inch baking pan.","Melt butter and mix with sugar. Beat in eggs and vanilla.","Sift together flour, cocoa powder, and salt. Stir into wet mixture.","Fold in chocolate chips. Pour into prepared pan.","Bake for 25-30 minutes until edges are set but center is still slightly soft.","Cool completely before cutting into squares."]}',
  1,
  'published'
),
(
  'Classic Vanilla Cupcakes',
  'https://images.unsplash.com/photo-1614707267537-b85aaf00c4b7?w=400&h=600&fit=crop',
  'Light and fluffy vanilla cupcakes topped with creamy buttercream frosting.',
  'classic-vanilla-cupcakes',
  '<p>These <strong>Classic Vanilla Cupcakes</strong> are perfectly moist, tender, and topped with silky vanilla buttercream. They''re the perfect base for any celebration!</p>

<h2>Perfect for Any Occasion</h2>

<p>Whether it''s a birthday party, baby shower, or just because, these vanilla cupcakes are always a crowd-pleaser. You can easily customize them with food coloring or different flavored frostings.</p>

<p>The key to light and fluffy cupcakes is not overmixing the batter and filling the cups only 2/3 full.</p>',
  'https://images.unsplash.com/photo-1614707267537-b85aaf00c4b7?w=800&h=600&fit=crop',
  '{"name":"Classic Vanilla Cupcakes","summary":"Light and fluffy vanilla cupcakes topped with creamy buttercream frosting.","servings":"12","prep_time":"20","cook_time":"18","total_time":"38","calories":"280","course":"Dessert","cuisine":"American","keywords":["cupcakes","vanilla","dessert","baking","frosting"],"notes":"Cupcakes can be made a day ahead. Frost just before serving for best results.","ingredients":[{"amount":"1.5","unit":"cups","name":"all-purpose flour"},{"amount":"1.5","unit":"teaspoons","name":"baking powder"},{"amount":"0.5","unit":"teaspoon","name":"salt"},{"amount":"0.5","unit":"cups","name":"unsalted butter, softened"},{"amount":"1","unit":"cup","name":"granulated sugar"},{"amount":"2","unit":"large","name":"eggs"},{"amount":"2","unit":"teaspoons","name":"vanilla extract"},{"amount":"0.5","unit":"cups","name":"whole milk"},{"amount":"2","unit":"cups","name":"powdered sugar"},{"amount":"0.25","unit":"cups","name":"butter, softened"},{"amount":"2","unit":"tablespoons","name":"heavy cream"}],"instructions":["Preheat oven to 350°F. Line muffin tin with cupcake liners.","Whisk together flour, baking powder, and salt.","Cream butter and sugar until fluffy. Beat in eggs and vanilla.","Alternately add dry ingredients and milk, beginning and ending with dry.","Fill cupcake liners 2/3 full. Bake 16-18 minutes.","Cool completely. Beat butter, powdered sugar, and cream for frosting.","Frost cooled cupcakes and serve."]}',
  1,
  'published'
),
(
  'New York Cheesecake',
  'https://images.unsplash.com/photo-1533134242116-8de7e903ff3b?w=400&h=600&fit=crop',
  'Creamy, rich New York-style cheesecake with a graham cracker crust.',
  'new-york-cheesecake',
  '<p>This <strong>New York Cheesecake</strong> is the gold standard - ultra-creamy, rich, and dense with a buttery graham cracker crust. It''s everything a cheesecake should be!</p>

<h2>The Ultimate Cheesecake</h2>

<p>New York-style cheesecake is known for its dense, smooth texture and rich flavor. The secret is using plenty of cream cheese and baking it in a water bath to prevent cracks.</p>

<p>This cheesecake is best when made a day ahead, allowing it to fully chill and set in the refrigerator.</p>',
  'https://images.unsplash.com/photo-1533134242116-8de7e903ff3b?w=800&h=600&fit=crop',
  '{"name":"New York Cheesecake","summary":"Creamy, rich New York-style cheesecake with a graham cracker crust.","servings":"12","prep_time":"30","cook_time":"60","total_time":"90","calories":"450","course":"Dessert","cuisine":"American","keywords":["cheesecake","dessert","New York","baking"],"notes":"Best made a day ahead. Serve with fresh berries or fruit compote. Store covered in refrigerator.","ingredients":[{"amount":"2","unit":"cups","name":"graham cracker crumbs"},{"amount":"0.5","unit":"cups","name":"melted butter"},{"amount":"32","unit":"oz","name":"cream cheese, softened"},{"amount":"1.25","unit":"cups","name":"granulated sugar"},{"amount":"4","unit":"large","name":"eggs"},{"amount":"1","unit":"cup","name":"sour cream"},{"amount":"2","unit":"teaspoons","name":"vanilla extract"},{"amount":"0.25","unit":"cups","name":"all-purpose flour"}],"instructions":["Preheat oven to 325°F. Mix graham cracker crumbs with melted butter.","Press into bottom of 9-inch springform pan. Bake 10 minutes.","Beat cream cheese until smooth. Add sugar and beat until fluffy.","Add eggs one at a time, beating after each. Mix in sour cream and vanilla.","Stir in flour. Pour over crust.","Place pan in larger roasting pan. Fill roasting pan with hot water halfway up sides.","Bake 60-70 minutes until edges are set but center jiggles slightly.","Cool completely, then refrigerate overnight before serving."]}',
  1,
  'published'
);
