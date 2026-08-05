import { chromium } from "playwright-core";

const EXECUTABLE =
  "/Users/hanifrestian/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch({ executablePath: EXECUTABLE, headless: true });
const page = await browser.newPage();
const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(String(err)));

await page.goto("http://127.0.0.1:8082/admin", { waitUntil: "networkidle" });

// --- 10. Server status pill ---
const pill = page.locator("#serverStatusPill");
await pill.waitFor({ state: "visible", timeout: 5000 });
const pillText = (await pill.textContent()).trim();
check("Server status pill renders", /Running on :8082 v\d+\.\d+\.\d+/.test(pillText), pillText);
check("Server status pill has ok class", (await pill.getAttribute("class")).includes("ok"));

// --- 8. Onboarding card (hidden when keys configured) ---
const onboarding = page.locator("#onboardingCard");
check("Onboarding hidden when keys configured", await onboarding.isHidden());

// Force-render onboarding via the app's own function with no keys
await page.evaluate(() => {
  localStorage.clear();
  renderOnboarding(
    state.config.provider_status.map((p) =>
      p.kind === "connected_account" ? p : { ...p, status: "missing_key" },
    ),
  );
});
check("Onboarding visible with no keys", await onboarding.isVisible());
const steps = page.locator(".onboarding-step");
check("Onboarding has 3 steps", (await steps.count()) === 3);
check("Onboarding uses hans-claude command", (await onboarding.locator("code").textContent()) === "hans-claude");

// copy button
const copyBtn = onboarding.locator(".copy-command");
await copyBtn.click();
await page.waitForTimeout(300);
check("Copy button shows Copied!", (await copyBtn.textContent()) === "Copied!");
check("Copy toast shown", (await page.locator(".toast").count()) >= 1);

// dismiss
await onboarding.locator(".onboarding-dismiss").click();
check("Onboarding dismissible", await onboarding.isHidden());
check("Dismiss flag persisted", (await page.evaluate(() => localStorage.getItem("claudey.onboarding.dismissed"))) === "1");

// --- 9. Provider cards ---
const cards = page.locator("#providerGrid .provider-card");
const cardCount = await cards.count();
check("Provider cards render", cardCount > 10, `${cardCount} cards`);
const firstCard = cards.first();
check("Card has logo", (await firstCard.locator(".provider-logo").count()) === 1);
check("Card has status pill", (await firstCard.locator(".status-pill").count()) === 1);
check("Card has Configure button", (await firstCard.locator("button", { hasText: "Configure" }).count()) === 1);
check("Configured pill is green", (await firstCard.locator(".status-pill").getAttribute("class")).includes("ok"));
// Configure scrolls & focuses
await firstCard.locator("button", { hasText: "Configure" }).click();
await page.waitForTimeout(700);
const focused = await page.evaluate(() => document.activeElement?.id || "");
check("Configure focuses provider field", focused.startsWith("field-"), focused);

// --- 11. Model Config role cards ---
await page.locator(".nav-link", { hasText: "Model Config" }).click();
await page.waitForTimeout(300);
const roleCards = page.locator(".role-card");
check("Role cards render (5)", (await roleCards.count()) === 5, `${await roleCards.count()} cards`);
const headers = page.locator(".role-card-header");
const headerLabels = await headers.allTextContents();
check(
  "Role headers Fable/Opus/Sonnet/Haiku/Fallback",
  ["Fable", "Opus", "Sonnet", "Haiku", "Fallback"].every((r) => headerLabels.some((t) => t.includes(r))),
  headerLabels.map((t) => t.split(" ")[0]).join(","),
);
check("Sticky header CSS applied", await headers.first().evaluate((el) => getComputedStyle(el).position === "sticky"));
check("Fallback description mentions /model", (await headers.first().textContent()).includes("/model"));
// Reset button
const reset = page.locator(".field-reset").first();
check("Reset button exists", (await reset.count()) === 1);
await reset.click();
await page.waitForTimeout(100);
const dirty = await page.locator("#dirtyState").textContent();
check("Reset marks dirty state", !dirty.includes("No changes"), dirty.trim());
// placeholder
const ph = await page.evaluate(() => document.querySelector('#field-MODEL_FABLE')?.placeholder || "");
check("Placeholder uses provider default", ph === "Uses provider default", ph);

// --- 12. Keyboard shortcuts + toasts ---
const applyBtn = page.locator("#applyButton");
const validateBtn = page.locator("#validateButton");
check("aria-keyshortcuts on Apply", (await applyBtn.getAttribute("aria-keyshortcuts"))?.includes("Control+Enter"));
check("aria-keyshortcuts on Validate", (await validateBtn.getAttribute("aria-keyshortcuts"))?.includes("Control+S"));
await page.keyboard.press("Control+Enter");
await page.waitForTimeout(1800);
check("Ctrl+Enter applies when dirty", (await page.locator(".toast").count()) >= 1, "toast appeared");
// Fresh page (apply may have reloaded), then Ctrl+S
await page.goto("http://127.0.0.1:8082/admin", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
await page.keyboard.press("Control+s");
await page.waitForTimeout(700);
check("Ctrl+S validates", (await page.locator(".toast").count()) >= 1, "toast appeared");

// --- 13. Messaging segmented control ---
await page.locator(".nav-link", { hasText: "Messaging" }).click();
await page.waitForTimeout(300);
const group = page.locator('.segmented-control[role="radiogroup"]');
check("Segmented control renders", (await group.count()) === 1);
check("radiogroup role", (await group.getAttribute("role")) === "radiogroup");
const segments = group.locator('[role="radio"]');
check("Segments Discord/Telegram", (await segments.allTextContents()).join(",").includes("Discord") && (await segments.allTextContents()).join(",").includes("Telegram"));
await segments.first().focus();
await page.keyboard.press("ArrowRight");
await page.waitForTimeout(100);
const checked = await group.locator('[aria-checked="true"]').textContent();
check("Arrow key selects next segment", checked.trim().toLowerCase() !== "discord", checked.trim());
const hiddenVal = await page.evaluate(() => document.querySelector("#field-MESSAGING_PLATFORM")?.value || "");
check("Hidden select synced", hiddenVal === "telegram", `${hiddenVal} (segment: ${checked.trim()})`);
// Voice notes subheader
check("Voice notes subheader", (await page.locator(".section-heading.subheading h3").count()) === 1);

consoleErrors.forEach((e) => console.log("CONSOLE ERROR:", e));
check("No console errors", consoleErrors.length === 0, consoleErrors.join(" | "));

await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
