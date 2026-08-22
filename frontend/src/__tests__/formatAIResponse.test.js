import { describe, it, expect } from 'vitest';
import { formatAIResponse } from '../lib/formatAIResponse';

/**
 * The AI Research Assistant emits markdown the old formatter did not
 * understand, so it reached the user as literal `###`, `|` pipes and
 * `[text](url)`. Fixtures below mirror real stored ai_research_feedback rows.
 */
describe('formatAIResponse', () => {
  it('keeps escaping HTML', () => {
    const html = formatAIResponse('<script>alert(1)</script> & more');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('&amp;');
  });

  it('renders bold and italic', () => {
    const html = formatAIResponse('The **verdict** is *partially* accurate.');
    expect(html).toContain('<strong>verdict</strong>');
    expect(html).toContain('<em>partially</em>');
    expect(html).not.toContain('*partially*');
  });

  it('does not mistake bold for italic', () => {
    const html = formatAIResponse('**Verdict: Confirmed**');
    expect(html).toContain('<strong>Verdict: Confirmed</strong>');
    expect(html).not.toContain('<em>');
  });

  it('renders headings', () => {
    const html = formatAIResponse('### 1. Claim: "Asset-light"');
    expect(html).toMatch(/<h[456][^>]*>1\. Claim: "Asset-light"<\/h[456]>/);
    expect(html).not.toContain('###');
  });

  it('renders links, opening them safely in a new tab', () => {
    const html = formatAIResponse('Source: [Copart 10-K](https://www.sec.gov/ix?doc=a&b=2)');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('>Copart 10-K</a>');
    expect(html).not.toContain('](');
  });

  it('refuses javascript: and data: URLs', () => {
    // The unsafe link must not become an anchor. Leaving the markdown as
    // escaped text is fine — it is inert; what matters is that no href
    // carrying a non-http(s) scheme is ever emitted.
    for (const bad of ['javascript:alert(1)', 'data:text/html;base64,PHN2Zz4=']) {
      const html = formatAIResponse(`[click](${bad})`);
      expect(html).not.toContain('<a ');
      expect(html).not.toMatch(/href=/i);
    }
  });

  it('still linkifies an ordinary https URL alongside a rejected one', () => {
    const html = formatAIResponse('[bad](javascript:x) and [good](https://sec.gov/a)');
    expect(html).toContain('href="https://sec.gov/a"');
    expect((html.match(/<a /g) || []).length).toBe(1);
  });

  it('renders pipe tables', () => {
    const src = [
      '| Revenue Category | Revenue | % of Total |',
      '| :--- | :--- | :--- |',
      '| Service Revenues | $3.18 Billion | 82.1% |',
    ].join('\n');
    const html = formatAIResponse(src);
    expect(html).toContain('<table');
    expect(html).toContain('<th>Revenue Category</th>');
    expect(html).toContain('<td>$3.18 Billion</td>');
    expect(html).not.toContain('| :--- |');
  });

  it('does not put prose inside a <ul> when a paragraph mixes both', () => {
    const src = 'What I found: it depends.\n* Inventory: consignment.\n* Infrastructure: owns yards.';
    const html = formatAIResponse(src);
    // The prose must be its own block, not a stray text child of <ul>.
    expect(html).not.toMatch(/<ul>\s*[^<]/);
    expect(html).toContain('What I found: it depends.');
    expect(html).toContain('<li>Inventory: consignment.</li>');
    expect(html).toContain('<li>Infrastructure: owns yards.</li>');
  });

  it('still renders plain bullet and numbered lists', () => {
    expect(formatAIResponse('- one\n- two')).toContain('<ul>');
    expect(formatAIResponse('1. one\n2. two')).toContain('<ol>');
    expect(formatAIResponse('1. one\n2. two')).toContain('<li>one</li>');
  });

  it('renders horizontal rules', () => {
    expect(formatAIResponse('above\n\n---\n\nbelow')).toContain('<hr');
  });

  it('keeps separate paragraphs separate', () => {
    const html = formatAIResponse('First para.\n\nSecond para.');
    expect(html).toContain('<p>First para.</p>');
    expect(html).toContain('<p>Second para.</p>');
  });

  // Elaboration mode returns "1.\n\n2.\n\n3." — blank lines between items are
  // spacing, not the end of the list. Splitting there restarts every <ol>, so
  // all five questions rendered as "1.".
  it('keeps a blank-line-separated numbered list as one list', () => {
    const html = formatAIResponse('1. first\n\n2. second\n\n3. third');
    expect((html.match(/<ol/g) || []).length).toBe(1);
    expect(html).toContain('<li>first</li>');
    expect(html).toContain('<li>second</li>');
    expect(html).toContain('<li>third</li>');
  });

  it('keeps a blank-line-separated bullet list as one list', () => {
    const html = formatAIResponse('- one\n\n- two');
    expect((html.match(/<ul/g) || []).length).toBe(1);
  });

  it('preserves a list that does not start at 1', () => {
    const html = formatAIResponse('3. third\n\n4. fourth');
    expect(html).toContain('start="3"');
  });

  // Fact-check nests detail under each numbered point. Treating the indented
  // bullets as the end of the list restarted the numbering, so "2." showed as "1.".
  it('keeps numbering across items that contain nested bullets', () => {
    const src = [
      '1. First point',
      '   - nested detail',
      '   - another nested detail',
      '2. Second point',
      '   - more nested detail',
    ].join('\n');
    const html = formatAIResponse(src);

    expect((html.match(/<ol/g) || []).length).toBe(1);
    expect(html).toContain('First point');
    expect(html).toContain('Second point');
    // The nested detail survives, inside the item it belongs to.
    expect(html).toMatch(/<li>[\s\S]*?<ul>[\s\S]*?nested detail/);
  });

  it('still ends the list when prose follows', () => {
    const html = formatAIResponse('1. first\n\n2. second\n\nA closing thought.');
    expect((html.match(/<ol/g) || []).length).toBe(1);
    expect(html).toContain('<p>A closing thought.</p>');
    expect(html).not.toMatch(/<li>A closing thought/);
  });
});
