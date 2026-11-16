// Fills one Greenhouse application form from a plan.json and submits it.
// usage: node gh_submit.js <plan.json> [--dry-run]     last stdout line = JSON result
// A CAPTCHA challenge or email security code is reported, never worked around.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const DRY = process.argv.includes('--dry-run');
const out = plan.out_dir;
fs.mkdirSync(out, { recursive: true });
const notes = [];
const done = (status, extra = {}) => { console.log(JSON.stringify({ status, notes, ...extra })); };
const q = id => `[id="${id.replace(/(["\\])/g, '\\$1')}"]`;

async function pick(page, input, label) {
  await input.scrollIntoViewIfNeeded();
  await input.click();
  await input.fill(label.slice(0, 50));
  const opt = page.getByRole('option', { name: label, exact: true }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
}

async function fill(page, f) {
  if (f.kind === 'file') return page.locator(q(f.name)).setInputFiles(f.value);
  if (f.kind === 'text' || f.kind === 'textarea') return page.locator(q(f.name)).fill(String(f.value));
  if (f.kind === 'phone') {
    const country = page.locator('#country');
    if (await country.count()) {
      await country.click();
      await country.fill(plan.phone_country);
      const opt = page.getByRole('option', { name: new RegExp('^' + plan.phone_country, 'i') }).first();
      await opt.waitFor({ timeout: 8000 });
      await opt.click();
    }
    return page.locator('#phone').fill(String(f.value));
  }
  if (f.kind === 'check') {
    const box = page.locator(q(f.name));
    if (await box.count()) await box.check({ force: true }); else notes.push('checkbox tidak ada di halaman: ' + f.name);
    return;
  }
  if (f.kind === 'select') return pick(page, page.locator(q(f.name)), f.value[0]);
  if (f.kind === 'multi') {
    for (let i = 0; i < f.value.length; i++) {
      const box = page.locator(q(`${f.name}_${f.value_ids[i]}`));
      if (await box.count()) await box.check({ force: true });
      else await pick(page, page.locator(q(f.name)), f.value[i]);
    }
    return;
  }
  throw new Error('unknown kind ' + f.kind);
}

async function errors(page) {
  return page.evaluate(() => [...document.querySelectorAll('[id$="-error"], .helper-text--error, [role="alert"]')]
    .map(e => e.textContent.trim()).filter(Boolean).slice(0, 12));
}

(async () => {
  const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1800 }, locale: 'en-US', timezoneId: 'Asia/Jakarta' });
  const page = await ctx.newPage();
  try {
    await page.goto(plan.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.locator('#first_name').waitFor({ timeout: 30000 });
    // React hydration resets anything typed too early: wait for it, then prove a typed value sticks.
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    for (let i = 0; i < 10; i++) {
      await page.locator('#first_name').fill('x');
      await page.waitForTimeout(1500);
      if (await page.locator('#first_name').inputValue() === 'x') break;
    }
    for (const f of plan.fields) {
      try { await fill(page, f); } catch (e) {
        await page.screenshot({ path: path.join(out, 'error.png'), fullPage: true });
        return done('error', { detail: `field ${f.name} (${f.label}): ${e.message.split('\n')[0]}` });
      }
    }
    if (plan.location_search) {
      const loc = page.locator('#candidate-location');
      if (await loc.count()) {
        await loc.click();
        await loc.pressSequentially(plan.location_search, { delay: 60 });
        const opt = page.getByRole('option').first();
        await opt.waitFor({ timeout: 15000 });
        notes.push('location: ' + (await opt.textContent()).trim());
        await opt.click();
      }
    }
    await page.waitForTimeout(1500);
    // Read every value back from the page. A mismatch means the form is not what the plan says: do not submit.
    const wrong = [];
    for (const f of plan.fields) {
      if (f.kind === 'text' || f.kind === 'textarea' || f.kind === 'phone') {
        if (await page.locator(q(f.name)).inputValue() !== String(f.value)) wrong.push(f.name);
      } else if (f.kind === 'select' || f.kind === 'multi') {
        const boxes = f.kind === 'multi' && await page.locator(q(`${f.name}_${f.value_ids[0]}`)).count();
        for (let i = 0; i < f.value.length; i++) {
          const ok = boxes ? await page.locator(q(`${f.name}_${f.value_ids[i]}`)).isChecked()
            : await page.locator(q(f.name)).evaluate((el, v) => (el.closest('.select__control') || el.parentElement.parentElement.parentElement).textContent.includes(v), f.value[i]);
          if (!ok) wrong.push(f.name);
        }
      }
    }
    await page.screenshot({ path: path.join(out, 'filled.png'), fullPage: true });
    if (wrong.length) return done('error', { detail: 'nilai di halaman tidak sama dengan plan: ' + wrong.join(', ') });
    if (DRY) return done('filled', { screenshot: path.join(out, 'filled.png'), errors: await errors(page) });

    await page.getByRole('button', { name: /submit application/i }).click();
    const deadline = Date.now() + 60000;
    let state = null;
    while (Date.now() < deadline && !state) {
      await page.waitForTimeout(1500);
      const body = (await page.locator('body').innerText().catch(() => '')) || '';
      if (/confirmation/.test(page.url()) || /thank you for applying|application (has been|was) (submitted|received)|we.ve received your application/i.test(body)) state = 'submitted';
      else if (await page.locator('input[id^="security-input"]').count()) state = 'needs_code';
      else if ((await errors(page)).length) state = 'validation';
      else if (await page.locator('iframe[src*="recaptcha"][src*="bframe"]').evaluateAll(fs => fs.some(f => f.getBoundingClientRect().height > 100)).catch(() => false)) state = 'captcha';
    }
    if (state === 'needs_code') {
      // Greenhouse emailed a verification code to the applicant. Wait for someone to drop it into code.txt.
      const codeFile = path.join(out, 'code.txt');
      fs.writeFileSync(path.join(out, 'NEED_CODE'), new Date().toISOString());
      const until = Date.now() + (plan.code_wait_s || 0) * 1000;
      while (Date.now() < until && !fs.existsSync(codeFile)) await page.waitForTimeout(3000);
      if (fs.existsSync(codeFile)) {
        const code = fs.readFileSync(codeFile, 'utf8').trim();
        const boxes = page.locator('input[id^="security-input"]');
        for (let i = 0; i < code.length && i < await boxes.count(); i++) await boxes.nth(i).fill(code[i]);
        await page.getByRole('button', { name: /submit application/i }).click();
        await page.waitForTimeout(8000);
        const body = await page.locator('body').innerText().catch(() => '');
        state = (/confirmation/.test(page.url()) || /thank you for applying|application (has been|was) (submitted|received)/i.test(body)) ? 'submitted' : 'needs_code';
        fs.rmSync(codeFile, { force: true });
      }
      fs.rmSync(path.join(out, 'NEED_CODE'), { force: true });
    }
    await page.screenshot({ path: path.join(out, (state || 'unknown') + '.png'), fullPage: true });
    done(state || 'error', { url: page.url(), errors: state === 'validation' ? await errors(page) : undefined,
      detail: state ? undefined : 'tidak ada halaman konfirmasi dalam 60 detik' });
  } catch (e) {
    await page.screenshot({ path: path.join(out, 'error.png'), fullPage: true }).catch(() => {});
    done('error', { detail: e.message.split('\n')[0] });
  } finally {
    await browser.close();
  }
})();
