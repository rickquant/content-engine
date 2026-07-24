/**
 * Code node: "Keep latest only"
 *
 * Runs right after the RSS node and before the model. The feed returns ~20
 * articles; without this cap, one run means ~20 LLM calls.
 *
 * This file is the source of truth for readers; n8n runs the copy stored
 * inside workflow/content-engine.workflow.json. Keep them in sync.
 */

// Only the most recent article (MVP: one post per run)
return $input.all().slice(0, 1);
