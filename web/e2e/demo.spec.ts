import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

const FIXED_APPLICATION = fileURLToPath(new URL('../../data/packets/packet_01_fixed/inherited_ira_application_b2.pdf', import.meta.url));

// Demo path against local services (docker compose up). Best case first, then the flawed case.
// Document reading takes several seconds, so waits are generous.
const READ_TIMEOUT = 60_000;

async function startCase(page: Page, sample: string) {
  await page.goto('/');
  await page.getByTestId('case-select').click();
  await page.getByTestId(`sample-${sample}`).click();
  await expect(page.getByTestId('reading-progress')).toBeVisible();
  await expect(page.getByTestId('reading-progress')).toBeHidden({ timeout: READ_TIMEOUT });
}

async function openDrawer(page: Page, tab: string) {
  const drawer = page.getByTestId('under-the-hood');
  if (!(await drawer.getByTestId(`tab-btn-${tab}`).isVisible())) await page.getByTestId('toggle-under-the-hood').click();
  await drawer.getByTestId(`tab-btn-${tab}`).click();
}

test.describe.configure({ mode: 'serial' });

test('1. best case: packet_01_fixed runs straight through to a prefilled application', async ({ page }) => {
  await startCase(page, 'packet_01_fixed');

  const checks = page.locator('[data-testid^="check-"]');
  await expect(checks.first()).toBeVisible();
  await expect(page.locator('[data-testid^="check-"][data-status="fail"]')).toHaveCount(0);
  await expect(page.locator('[data-testid^="check-"][data-status="needs_review"]')).toHaveCount(0);
  // Extracted values are shown, never editable.
  await expect(page.locator('[data-testid^="field-"]').first()).toBeVisible();
  await expect(page.locator('input[data-testid^="field-"], textarea[data-testid^="field-"]')).toHaveCount(0);

  await openDrawer(page, 'ops');
  await page.getByTestId('approve').click();
  await expect(page.getByText('Your documents are approved')).toBeVisible();

  await page.getByTestId('input-income').fill('95000');
  await page.getByTestId('compare-options').click();
  await expect(page.getByTestId('schedule-table')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('options-summary')).toBeVisible();

  await page.getByTestId('choice-keep').click();
  const dialog = page.getByTestId('keep-dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByTestId('prefill-application').click();
  const rows = dialog.getByTestId('prefill-row');
  await expect(rows.first()).toBeVisible({ timeout: 30_000 });
  const n = await rows.count();
  expect(n).toBeGreaterThan(0);
  await expect(dialog.getByTestId('source-chip')).toHaveCount(n);
  await expect(dialog.getByText(/Entered by heir at signing/).first()).toBeVisible();
  await dialog.getByRole('button', { name: 'Close' }).click();

  await expect(page.getByTestId('after-section').getByTestId('optin-status')).toBeVisible();
});

test('2. flawed case: packet_01_flawed is caught, reasons shown under the hood, then fixed', async ({ page }) => {
  await startCase(page, 'packet_01_flawed');

  await expect(page.locator('[data-testid="check-shares_total_100"][data-status="fail"]').first()).toBeVisible();

  await openDrawer(page, 'rules');
  const rule = page.getByTestId('tab-rules').locator('[data-testid="rule-shares_total_100"][data-status="fail"]').first();
  await expect(rule).toBeVisible();
  await expect(rule.getByTestId('writer-reason')).not.toBeEmpty();

  await openDrawer(page, 'ops');
  await expect(page.getByTestId('approve')).toBeDisabled();

  // Fix: values are never edited, so upload the corrected application, then re-check.
  await expect(page.locator('[data-testid$="-share_percent"][data-bad="true"]').first()).toBeVisible();
  await page.locator('[data-testid^="dropzone-"] input').last().setInputFiles(FIXED_APPLICATION);
  await expect(page.getByText('inherited_ira_application_b2.pdf added')).toBeVisible();
  await page.getByTestId('recheck').click();
  await expect(page.getByTestId('reading-progress')).toBeHidden({ timeout: READ_TIMEOUT });

  await expect(page.locator('[data-testid^="check-"][data-status="fail"]')).toHaveCount(0);
  await openDrawer(page, 'ops');
  await expect(page.getByTestId('approve')).toBeEnabled();
});

test('3. no case chosen: dropping the documents opens the case and finds the account on file', async ({ page }) => {
  await page.goto('/');
  const dir = fileURLToPath(new URL('../../data/packets/packet_01_fixed/', import.meta.url));
  const files = ['death_certificate.pdf', 'inherited_ira_application_b1.pdf', 'inherited_ira_application_b2.pdf'].map((f) => dir + f);
  await page.getByTestId('upload-dropzone').locator('input').setInputFiles(files);
  await page.getByTestId('upload-submit').click();
  await expect(page.getByTestId('reading-progress')).toBeVisible();
  await expect(page.getByTestId('reading-progress')).toBeHidden({ timeout: READ_TIMEOUT });
  await expect(page.locator('[data-testid^="beneficiary-"]')).toHaveCount(2);
  await expect(page.locator('[data-testid^="check-"][data-status="fail"]')).toHaveCount(0);
});
