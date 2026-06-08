const { expect, test } = require("@playwright/test");

const pages = [
  { name: "overview", path: "/api/v1/dashboard/overview" },
  { name: "activity", path: "/api/v1/dashboard/activity" },
  { name: "pipeline", path: "/api/v1/dashboard/pipeline" },
  { name: "watch", path: "/api/v1/dashboard/watch" },
  { name: "settings", path: "/api/v1/dashboard/settings" },
];

const summaryFixture = {
  contacts_total: 32,
  active_consents: 21,
  open_conversations: 8,
  open_tickets: 3,
  follow_ups_due: 5,
  inbound_messages_today: 14,
  outbound_messages_today: 19,
  groups_joined: 12,
  messages_analyzed: 420,
  leads_detected_total: 86,
  conversions: 11,
  leads_detected_today: 9,
  public_replies_sent: 17,
  dms_sent: 28,
  reply_rate: 39.3,
  conversion_rate: 12.8,
  high_prob_leads: 7,
  high_value_leads: 16,
  reseller_prospects: 6,
  average_ltv_score: 74.5,
  ltv_distribution: { "High Value": 16, "Reseller": 6, "Standard": 18 },
  problem_distribution: { Buffering: 14, Billing: 6, Setup: 9 },
  influence_distribution: { leader: 3, power_user: 8, regular: 31 },
  sentiment_trends: {
    "2026-06-01": { Buffering: 3, Billing: 1 },
    "2026-06-02": { Buffering: 5, Setup: 4 },
    "2026-06-03": { Billing: 3, Setup: 2 },
  },
  hourly_heatmap: [{ hour: 0, count: 2 }, { hour: 1, count: 5 }, { hour: 13, count: 4 }],
  persona_performance: [
    { name: "Aiden", leads: 35, conversions: 6, rate: 17.1 },
    { name: "Maya", leads: 24, conversions: 4, rate: 16.7 },
  ],
  account_health: [
    { phone: "+10000000000", status: "active", dms_used: 2, dms_left: 8, joins_used: 1, joins_left: 1, proxy_status: true },
  ],
  competitor_stats: [{ name: "Competitor A", score: 78, complaints: 12 }],
  activity_log: [{ user: "graceatv", type: "lead", text: "Asked for reseller pricing", time: "12:45:10" }],
  recent_events: [{ type: "consent_granted", time: "2026-06-07T10:00:00Z", contact: "graceatv", metadata: { scope: "support" } }],
  crm_trend: [
    { day: "2026-06-01", contacts_total: 10, open_tickets: 2, follow_ups_due: 1 },
    { day: "2026-06-02", contacts_total: 18, open_tickets: 3, follow_ups_due: 2 },
    { day: "2026-06-03", contacts_total: 32, open_tickets: 3, follow_ups_due: 5 },
  ],
  ticket_status_breakdown: { open: 3, pending: 2 },
  ticket_priority_breakdown: { high: 2, medium: 3 },
  consent_scope_breakdown: { support_updates: 21 },
  lifecycle_stage_breakdown: { new: 18, qualified: 9, customer: 5 },
  recent_leads: [
    { username: "graceatv", lead_score: 91, lead_strength: "hot", status: "NEW", group_name: "IPTV Support", last_contact: null },
  ],
  top_groups: [
    { group_name: "IPTV Support", leads_generated: 12, messages_scanned: 140 },
  ],
  daily_trend: [
    { date: "2026-06-01", count: 5 },
    { date: "2026-06-02", count: 9 },
    { date: "2026-06-03", count: 12 },
  ],
  conversion_funnel: [{ stage: "NEW", count: 42 }, { stage: "CONVERTED", count: 11 }],
};

async function authenticateDashboard(page) {
  const password = process.env.DASHBOARD_ADMIN_PASSWORD || "changeme";
  const response = await page.request.post("/api/v1/dashboard/auth/login", {
    data: { password },
  });
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  return data.token;
}

async function authenticateControl(page) {
  const password = process.env.DASHBOARD_CONTROL_PASSWORD || "control-changeme";
  const response = await page.request.post("/api/v1/dashboard/auth/login", {
    data: { password, scope: "control" },
  });
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  return data.token;
}

async function mockDashboardApi(page, token) {
  await page.addInitScript((value) => localStorage.setItem("slie_token", value), token);
  await page.route("**/api/v1/dashboard/summary", route => route.fulfill({ json: summaryFixture }));
  await page.route("**/api/v1/dashboard/groups", route => route.fulfill({
    json: [
      { name: "IPTV Support", members: 5400, score: 88, density: 0.21 },
      { name: "Premium Resellers", members: 2900, score: 74, density: 0.18 },
    ],
  }));
  await page.route("**/api/v1/dashboard/high-intent-buyers", route => route.fulfill({
    json: [{ username: "graceatv", score: 91, temperature: "HOT", timestamp: "2026-06-07" }],
  }));
  await page.route("**/api/v1/dashboard/settings-config", route => route.fulfill({
    json: {
      target_tags: ["iptv", "reseller"],
      search_tags: ["buffering", "trial"],
      brand_tags: ["SLIE"],
      watch_terms: ["competitor"],
      lead_score_threshold: 70,
      daily_dm_limit: 50,
      auto_join_groups: false,
      telegram_outreach_enabled: true,
      notes: "Visual test configuration",
    },
  }));
}

for (const dashboardPage of pages) {
  test(`${dashboardPage.name} renders without a blank screen`, async ({ page }) => {
    const token = dashboardPage.name === "settings"
      ? await authenticateControl(page)
      : await authenticateDashboard(page);
    await mockDashboardApi(page, token);
    await page.goto(dashboardPage.path);
    await page.addStyleTag({
      content: `
        *, *::before, *::after { animation: none !important; transition: none !important; }
        .liquid-bg::before, .liquid-bg::after { display: none !important; }
        .scroll-reveal { opacity: 1 !important; transform: none !important; }
      `,
    });
    await expect(page.locator("#main-content")).toBeVisible();
    await expect(page.locator("#loginModal")).toBeHidden();
    await expect(page.locator("body")).not.toHaveCSS("background-color", "rgb(255, 255, 255)");

    const mainBox = await page.locator("#main-content").boundingBox();
    expect(mainBox).not.toBeNull();
    expect(mainBox.width).toBeGreaterThan(300);
    expect(mainBox.height).toBeGreaterThan(300);

    if (dashboardPage.name === "overview") {
      await expect(page.locator("#personaSankey svg.sankey-svg")).toBeVisible();
    }

    const activeView = dashboardPage.name === "watch" ? "targeting" : dashboardPage.name;
    const screenshotTarget = dashboardPage.name === "overview"
      ? page.locator("#personaSankey")
      : page.locator(`#view-${activeView} .command-hero`);

    await expect(screenshotTarget).toHaveScreenshot(`${dashboardPage.name}.png`, {
      animations: "disabled",
    });
  });
}
