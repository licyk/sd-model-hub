import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '@/markdown';

describe('renderMarkdown', () => {
  it('renders Markdown structure', () => {
    const html = renderMarkdown('# Title\n\nSome **bold** text.\n\n- one\n- two\n');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<li>one</li>');
  });

  it('renders fenced code as a block, not as Markdown', () => {
    const html = renderMarkdown('```python\nprint("# hi")\n```\n');
    expect(html).toContain('<pre><code');
    expect(html).not.toContain('<h1>');
  });

  /** A model card comes from a third party; raw HTML in it is shown as text, never parsed. */
  it('escapes raw HTML instead of rendering it', () => {
    const html = renderMarkdown('<script>alert(1)</script>\n\n<img src="x" onerror="alert(1)">\n');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('onerror=&quot;alert(1)&quot;');
  });

  it('leaves a script link unlinked', () => {
    const html = renderMarkdown('[click](javascript:alert(1))\n');
    expect(html).not.toContain('<a ');
    expect(html).not.toContain('href');
  });

  it('opens links in a new tab without a window handle', () => {
    const html = renderMarkdown('[hf](https://huggingface.co/)\n');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer nofollow"');
  });

  it('loads images lazily and without a referrer', () => {
    const html = renderMarkdown('![preview](https://example.com/a.png)\n');
    expect(html).toContain('loading="lazy"');
    expect(html).toContain('referrerpolicy="no-referrer"');
  });
});
