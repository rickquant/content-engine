/**
 * Code node: "Build the draft"
 *
 * Bundles the generated post with the headline and link it came from, so the
 * draft can be verified against its source before anyone approves it.
 *
 * This file is the source of truth for readers; n8n runs the copy stored
 * inside workflow/content-engine.workflow.json. Keep them in sync.
 */

// Bundle the post with its source so it can be verified before publishing.
const article = $('Keep latest only').first().json;

const draft = [
  '📝 DRAFT FOR IG',
  '',
  $json.text.trim(),
  '',
  '— — —',
  'Source: ' + article.title,
  article.link,
].join('\n');

return { json: { draft } };
