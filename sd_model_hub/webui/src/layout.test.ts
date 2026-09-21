import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Rows that pair a name with a control must let the name shrink.
 *
 * A model file name is one long unbreakable word, so the row's min-content width is the whole
 * name. A flex item keeps `min-width: auto` by default and refuses to go below that, which pushed
 * the overflow menu out of the card (clipped away, so the model could not be renamed or deleted)
 * and the snackbar's buttons off the screen. `min-width: 0` on the item that holds the text is
 * what makes the ellipsis work and keeps the control in place.
 */
const SRC = join(process.cwd(), 'src');
const ROWS: [file: string, selector: string][] = [
  ['components/ModelCard.vue', '.body'],
  ['components/DownloadItem.vue', '.main'],
  ['components/DownloadsDrawer.vue', '.main'],
  ['components/RepoFileTree.vue', '.name'],
  ['ui/Snackbar.vue', '.text'],
  ['views/LibraryView.vue', '.folder-text'],
];

function rule(file: string, selector: string): string {
  const css = readFileSync(join(SRC, file), 'utf8');
  const match = new RegExp(String.raw`(?:^|\n)\s*${selector.replace('.', '\\.')}\s*\{([^}]*)\}`).exec(css);
  expect(match, `${file} has no rule for ${selector}`).not.toBeNull();
  return match![1];
}

describe('rows that hold a file name', () => {
  it.each(ROWS)('%s %s can shrink below the name', (file, selector) => {
    expect(rule(file, selector)).toContain('min-width: 0');
  });
});
