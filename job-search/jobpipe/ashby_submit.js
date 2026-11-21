// Fills an Ashby application form from a plan (jobpipe/ashby.py) and submits it.
// Usage: node ashby_submit.js <plan.json> <out_dir> [--dry-run]
// Prints one JSON line: {"status": submitted|filled|error|captcha|validation, ...}
// Never works around CAPTCHA or spam checks: those end as status "captcha".
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [planPath, out] = process.argv.slice(2);
const DRY = process.argv.includes('--dry-run');
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const esc = (s) => s.replace(/"/g, '\\"');
let browser;

function done(status, extra = {}) {
  console.log(JSON.stringify({ status, ...extra }));
  if (browser) browser.close().catch(() => {});
  process.exit(0);
}

(async () => {
  browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  await page.goto(plan.url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2000);

  const box = async (p) => {
    const a = page.locator(`[data-field-path="${esc(p)}"]`);
    if (await a.count()) return a.first();
    return page.locator(`fieldset:has(label[for="${esc(p)}"])`).first();
  };
  const notes = [];

  for (const f of plan.fields) {
    const c = await box(f.path);
    if (f.kind === 'text' || f.kind === 'textarea') {
      await c.locator(`[id="${esc(f.path)}"]`).fill(String(f.value));
    } else if (f.kind === 'file') {
      await page.locator(`input[type=file][id="${esc(f.path)}"]`).setInputFiles(f.value);
      await page.waitForTimeout(4000); // Ashby parses the resume and may autofill fields; values are re-set below
    } else if (f.kind === 'location') {
      const inp = c.locator('input[role=combobox]');
      await inp.click();
      await inp.pressSequentially(f.value, { delay: 80 });
      const opt = page.getByRole('option').first();
      await opt.waitFor({ timeout: 15000 });
      notes.push('location: ' + (await opt.innerText()).trim());
      await opt.click();
    } else if (f.kind === 'boolean') {
      await c.locator(`button[data-option="${f.value[0].toLowerCase()}"]`).click();
    } else if (f.kind === 'select' || f.kind === 'multi') {
      for (const v of f.value) {
        const lab = c.locator('label', { hasText: v }).filter({ hasText: new RegExp('^\\s*' + v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*$') });
        if (await lab.count()) { await lab.first().click(); continue; }
        const cb = c.locator('input[role=combobox]');
        if (await cb.count()) {
          await cb.click(); await cb.fill(v);
          await page.getByRole('option', { name: v, exact: true }).first().click();
          continue;
        }
        return done('error', { detail: `opsi "${v}" tidak ditemukan untuk ${f.label.slice(0, 80)}` });
      }
    }
  }
  // Resume parsing can overwrite text fields after they were filled: set text values again.
  for (const f of plan.fields.filter((x) => x.kind === 'text' || x.kind === 'textarea')) {
    const inp = (await box(f.path)).locator(`[id="${esc(f.path)}"]`);
    if ((await inp.inputValue()) !== String(f.value)) await inp.fill(String(f.value));
  }
  await page.waitForTimeout(1000);

  // Read every value back. Any mismatch: do not submit.
  const wrong = [];
  for (const f of plan.fields) {
    const c = await box(f.path);
    if (f.kind === 'text' || f.kind === 'textarea') {
      if ((await c.locator(`[id="${esc(f.path)}"]`).inputValue()) !== String(f.value)) wrong.push(f.label.slice(0, 60));
    } else if (f.kind === 'boolean') {
      if ((await c.locator(`button[data-option="${f.value[0].toLowerCase()}"]`).getAttribute('aria-pressed')) !== 'true') wrong.push(f.label.slice(0, 60));
    } else if (f.kind === 'select' || f.kind === 'multi') {
      for (const v of f.value) {
        const ok = await c.evaluate((el, v) => {
          for (const l of el.querySelectorAll('label')) {
            if (l.textContent.trim() === v) { const i = document.getElementById(l.getAttribute('for')); if (i) return i.checked; }
          }
          return el.textContent.includes(v); // combobox: chosen value is shown as text
        }, v);
        if (!ok) wrong.push(f.label.slice(0, 60));
      }
    } else if (f.kind === 'file') {
      const n = await page.locator(`input[type=file][id="${esc(f.path)}"]`).evaluate((i) => i.files.length);
      if (!n && !(await c.innerText()).includes(path.basename(f.value))) wrong.push('resume');
    }
  }
  await page.screenshot({ path: path.join(out, 'filled.png'), fullPage: true });
  if (wrong.length) return done('error', { detail: 'nilai di halaman tidak sama dengan plan: ' + wrong.join(', '), notes });
  if (DRY) return done('filled', { screenshot: path.join(out, 'filled.png'), notes });

  await page.getByRole('button', { name: /submit application/i }).click();
  const outcome = await Promise.race([
    page.getByText(/thank you for applying|application was successfully submitted|successfully submitted|we.ve received your application/i).first()
      .waitFor({ timeout: 45000 }).then(() => 'submitted'),
    page.getByText(/spam|recaptcha|captcha|couldn.t be submitted|could not be submitted/i).first()
      .waitFor({ timeout: 45000 }).then(() => 'captcha'),
    page.locator('iframe[title*="challenge" i], iframe[src*="recaptcha/api2/bframe"], iframe[src*="hcaptcha"]').first()
      .waitFor({ state: 'visible', timeout: 45000 }).then(() => 'captcha'),
    page.locator('[class*=error], [role=alert]').filter({ hasText: /required|invalid|please/i }).first()
      .waitFor({ timeout: 45000 }).then(() => 'validation'),
  ]).catch(() => 'error');
  await page.screenshot({ path: path.join(out, outcome === 'submitted' ? 'submitted.png' : 'after_submit.png'), fullPage: true });
  const msg = outcome === 'submitted' ? '' : (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 400);
  return done(outcome, { detail: msg, notes });
})().catch((e) => done('error', { detail: String(e).slice(0, 400) }));
