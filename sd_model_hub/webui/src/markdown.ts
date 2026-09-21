/**
 * Render a model card (README) written in Markdown.
 *
 * The text comes from a third party, so raw HTML stays off: anything that looks like a tag is
 * escaped and shown, never parsed. Every attribute in the result is written by markdown-it's own
 * renderer, and markdown-it rejects `javascript:`-style link targets, so the output needs no
 * further sanitising. See `markdown.test.ts`, which holds these two promises.
 */
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({ html: false, linkify: true, breaks: false, typographer: false });

// Links leave the app, so they open in a new tab and carry no referrer or window handle.
const renderLink = md.renderer.rules.link_open ?? ((tokens, i, options, _env, self) => self.renderToken(tokens, i, options));
md.renderer.rules.link_open = (tokens, i, options, env, self) => {
  tokens[i].attrSet('target', '_blank');
  tokens[i].attrSet('rel', 'noopener noreferrer nofollow');
  return renderLink(tokens, i, options, env, self);
};

/** Images are often broken or huge in a README; they load lazily and never block the text. */
const renderImage = md.renderer.rules.image ?? ((tokens, i, options, _env, self) => self.renderToken(tokens, i, options));
md.renderer.rules.image = (tokens, i, options, env, self) => {
  tokens[i].attrSet('loading', 'lazy');
  tokens[i].attrSet('referrerpolicy', 'no-referrer');
  return renderImage(tokens, i, options, env, self);
};

export function renderMarkdown(text: string): string {
  return md.render(text);
}
