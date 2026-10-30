// ============================================================================
// 手机端 UI 端到端回归（Playwright）
//
// ⚠️ 运行前提：
//   1. 手机端服务已起（例：py -3.12 serve.py --port 17877，WorkingDirectory=prototype/mobile）
//   2. 装好 playwright：npm i -D playwright  （本机已装在旧项目 D:\jss18\AI\StackChan\node_modules）
//   3. 本机装了 Chrome（脚本用 channel: "chrome"，不用下载 chromium）
//
// 用法：
//   $env:MOBILE_URL='http://127.0.0.1:17877'
//   node tools/verify_v26_ui.js
//
//   截图落点：仓库内 prototype/output/playwright/mobile-v26（已被 .gitignore 挡住）
//   要挪出仓库：$env:MOBILE_SHOT_DIR='D:\path\to\shots'
// ============================================================================
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const MOBILE_URL = process.env.MOBILE_URL || "http://127.0.0.1:17877";

const programs = [
  ["chat", "AI Chat", "和小栈自然对话", "chat"],
  ["quote", "小栈悄悄话", "生日彩蛋与温柔留言", "letter"],
  ["album", "相册", "翻看依婵的照片", "album"],
  ["mood", "心情日记", "记录今天的心情", "mood"],
  ["pomodoro", "番茄钟", "开始一段专注时间", "focus"],
  ["fortune", "今日运势", "抽一张今天的小运势", "fortune"],
  ["game", "游戏专区", "贪吃蛇、疯狂玛丽与依婵坦克大战", "game"],
  ["settings", "系统设置", "网络、亮度与设备信息", "settings"],
].map(([id, name, description, icon]) => ({ id, name, description, icon }));

function deviceStatus(connected) {
  return {
    connected,
    connected_seconds: connected ? 92 : null,
    last_seen_seconds: connected ? 0.2 : null,
    network: { connected, ssid: connected ? "iPhone" : null, age_seconds: connected ? 0.2 : null },
    music: { state: "idle" },
    stage: { state: "idle" },
    camera: { available: false, streaming: false },
    head: { yaw: 0, pitch: 24, speed: 190 },
  };
}

async function installApiStubs(page) {
  await page.route("**/mobile-health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ ok: true, service: "stackchan-mobile", paired: true }),
  }));
  await page.route("**/mobile-api/**", async route => {
    const pathname = new URL(route.request().url()).pathname;
    let payload;
    if (pathname === "/mobile-api/device/status") payload = deviceStatus(false);
    else if (pathname === "/mobile-api/screen-programs") payload = { ok: true, programs, device: deviceStatus(false) };
    else if (pathname === "/mobile-api/screen-programs/control") {
      const body = route.request().postDataJSON();
      const program = programs.find(item => item.id === body.program_id);
      payload = { ok: true, action: "open", program, device: deviceStatus(true) };
    } else if (pathname === "/mobile-api/chat") {
      const body = route.request().postDataJSON();
      payload = {
        say: `当然可以。先做最小的一步：${body.message}，完成后就算今天赢了一局。`,
        emotion: "happy",
        face: "happy_sparkle",
        motion: "nod",
        route: "standard",
        model: "claude-sonnet-5",
        latency_ms: 48,
      };
    } else if (pathname === "/mobile-api/update/status") {
      payload = { state: "idle", message: "当前没有待安装更新", components: [] };
    } else payload = {};
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

async function assertViewport(page, label) {
  const size = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
    visibleScreen: document.querySelector(".screen:not([hidden])")?.dataset.screen,
  }));
  if (size.bodyWidth > size.viewportWidth) throw new Error(`${label} has horizontal overflow: ${JSON.stringify(size)}`);
  const tabSizes = await page.locator(".tab-button").evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect().height));
  if (tabSizes.some(height => height < 44)) throw new Error(`${label} has a tab target below 44px: ${tabSizes.join(",")}`);
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  // 落点默认在仓库内 `prototype/output/`（已被 .gitignore 挡住）；
  // 需要把产物挪出仓库时用 MOBILE_SHOT_DIR 覆盖。
  const outputDir = process.env.MOBILE_SHOT_DIR
    ? path.resolve(process.env.MOBILE_SHOT_DIR)
    : path.resolve(__dirname, "..", "..", "output", "playwright", "mobile-v26");
  fs.mkdirSync(outputDir, { recursive: true });
  const browserErrors = [];

  try {
    for (const viewport of [{ width: 430, height: 932 }, { width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, serviceWorkers: "block" });
      const page = await context.newPage();
      page.on("pageerror", error => browserErrors.push(error.message));
      page.on("console", message => {
        if (message.type() !== "error") return;
        const text = message.text();
        // ⚠️ 官方 3D 模型（stack_chan_model.glb）**故意不入库**：
        //    它在官方仓 app/assets/ 下，而 app/ 没有 LICENSE（见 docs/research/33 / 97 号）
        //    ⇒ 克隆本仓后必然 404，页面走「兼容 3D 模型」兜底。这不是本次回归的失败。
        if (text.includes("3D model not found")) return;
        browserErrors.push(text);
      });
      page.on("requestfailed", request => {
        const failure = request.failure()?.errorText || "request failed";
        if (request.url().includes("stack_chan_model.glb") && failure.includes("ERR_ABORTED")) return;
        browserErrors.push(`${request.url()}: ${failure}`);
      });
      await installApiStubs(page);
      // ⚠️ 不能等 networkidle：页面每 5 s 轮询一次设备状态 ⇒ 网络永不空闲
      await page.goto(`${MOBILE_URL}/#home`, { waitUntil: "domcontentloaded" });
      await page.waitForFunction(() => {
        const text = document.querySelector("#robotPreviewFallback")?.textContent || "";
        return text.includes("3D 模型已加载") || text.includes("兼容 3D 模型");
      });
      await page.waitForTimeout(1300);
      await assertViewport(page, `${viewport.width} home`);
      await page.screenshot({ path: path.join(outputDir, `home-${viewport.width}x${viewport.height}.png`), fullPage: true });

      // 「屏幕功能」现在是首页里的快捷入口（IA 已收敛为 3 个 Tab），不是 Tab 按钮
      await page.locator('[data-target="screen"]').first().click();
      await page.locator("#screenProgramGrid").waitFor();
      if (await page.locator("[data-screen-program]").count() !== 8) throw new Error("screen program count is not eight");
      if (await page.locator('[data-screen-program="game"]').isEnabled()) throw new Error("offline screen action is enabled");
      await assertViewport(page, `${viewport.width} screen`);
      await page.screenshot({ path: path.join(outputDir, `screen-${viewport.width}x${viewport.height}.png`), fullPage: true });

      await page.locator('.tab-button[data-target="chat"]').click();
      await page.locator("#chatMessageInput").fill("帮我做一个十分钟雅思计划");
      await page.locator("#chatMessageInput").press("Enter");
      await page.locator(".chat-bubble.assistant").filter({ hasText: "完成后就算今天赢了一局" }).waitFor();
      if (await page.locator(".chat-bubble.user").count() !== 1) throw new Error("mobile chat did not render the user message");
      await assertViewport(page, `${viewport.width} chat`);
      await page.screenshot({ path: path.join(outputDir, `chat-${viewport.width}x${viewport.height}.png`), fullPage: true });
      await context.close();
    }
    if (browserErrors.length) throw new Error(`browser errors: ${browserErrors.join(" | ")}`);
    console.log(JSON.stringify({ status: "pass", url: MOBILE_URL, viewports: ["430x932", "390x844"], programs: 8 }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
