import { api } from "./api.js";
import { createCameraPanelController } from "./camera_panel.js";
import { createDeviceTestController } from "./actions_music.js";
import { createRemoteController } from "./remote_control.js";
import { createSettingsController } from "./settings.js";
import { createUpdateController } from "./update.js";
import { createChatController } from "./chat.js";
import { createScreenProgramsController } from "./screen_programs.js";

const screens = [...document.querySelectorAll("[data-screen]")];
const tabButtons = [...document.querySelectorAll(".tab-button")];
// 短提示只负责反馈操作结果，设备真实状态仍由查询接口决定。
function showToast(message) {
  const activeScreen = screens.find((screen) => !screen.hidden);
  const feedback = activeScreen?.querySelector("[data-page-feedback]");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.hidden = false;
}

const deviceState = { status: null, error: null, live: false };
let statusRefreshInFlight = false;

// 检查状态是否仍有效，避免页面长期显示过期的在线信息。
function isStatusLive(status) {
  if (!status?.connected) return false;
  const lastSeen = Number(status.last_seen_seconds);
  const networkAge = Number(status.network?.age_seconds);
  if (Number.isFinite(lastSeen) && lastSeen > 12) return false;
  if (status.network?.connected && Number.isFinite(networkAge) && networkAge > 30) return false;
  return true;
}

// 把设备状态映射为页面文字和交互状态，不直接发送控制命令。
function renderDeviceStatus(status, error = null) {
  deviceState.status = status;
  deviceState.error = error;
  const connected = isStatusLive(status);
  deviceState.live = connected;
  const needsPairing = error?.status === 401;
  const connectionText = needsPairing ? "手机未配对" : error ? "连接暂不可用" : connected ? "小栈已连接" : "小栈未连接";
  const connectionState = error ? "error" : connected ? "online" : "offline";
  const network = status?.network || {};
  const networkText = needsPairing ? "等待配对" : !connected ? "等待连接" : network.connected === false ? "未连接" : network.ssid || "未上报";
  document.querySelectorAll("[data-device-connection]").forEach((node) => {
    node.textContent = connectionText;
    const host = node.closest(".online-pill, .compact-header p, .device-card");
    if (host) host.dataset.connectionState = connectionState;
  });
  document.querySelectorAll("[data-device-ssid]").forEach((node) => {
    node.textContent = networkText;
  });
  document.querySelectorAll("[data-requires-device]").forEach((control) => {
    control.disabled = !connected || control.dataset.uiBusy === "true";
  });
  let activityText = "等待小栈上线";
  if (connected) {
    if (status?.music?.state === "playing") activityText = status.music.title ? `正在播放《${status.music.title}》` : "正在播放音乐";
    else if (status?.stage?.state && status.stage.state !== "idle") activityText = "正在执行动作";
    else if (status?.camera?.streaming) activityText = "摄像头预览已开启";
    else activityText = "在线待命";
  }
  document.querySelectorAll("[data-home-activity]").forEach((node) => {
    node.textContent = needsPairing ? "需要完成手机配对" : error ? "正在重新连接" : activityText;
  });
  document.querySelectorAll("[data-model-state]").forEach((node) => {
    node.textContent = connected ? "实时 3D" : "3D 模型";
  });
  document.querySelectorAll("[data-console-camera]").forEach((node) => {
    node.textContent = connected ? (status?.camera?.streaming ? "正在拍摄" : "已关闭") : "设备未连接";
  });
  window.stackChanDeviceState = deviceState;
  window.dispatchEvent(new CustomEvent("stackchandevicestatus", { detail: deviceState }));
}

// 拉取一轮状态并同步页面；失败也需要更新显示，不能继续沿用成功提示。
async function refreshDeviceStatus() {
  if (statusRefreshInFlight) return;
  statusRefreshInFlight = true;
  try {
    renderDeviceStatus(await api.get("/device/status"));
  } catch (error) {
    renderDeviceStatus(null, error);
  } finally {
    statusRefreshInFlight = false;
  }
}

// 建立状态刷新机制，使遥控、设置等模块共享最近的连接信息。
async function startDeviceStatusPolling() {
  const refreshWhenReady = async (refreshPairing = false) => {
    try {
      if (!(await api.isPaired(refreshPairing))) {
        renderDeviceStatus(null, { status: 401 });
        return;
      }
      await refreshDeviceStatus();
    } catch (error) {
      renderDeviceStatus(null, error);
    }
  };
  await refreshWhenReady();
  window.setInterval(() => {
    if (document.visibilityState === "visible") refreshWhenReady(true);
  }, 5000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshWhenReady(true);
  });
  window.addEventListener("focus", () => refreshWhenReady(true));
  window.addEventListener("online", () => refreshWhenReady(true));
}

// 切换当前页面并按参数同步 URL；这是网页导航，不是切换机器人屏幕应用。
function activateScreen(target, updateUrl = true) {
  const next = screens.find((screen) => screen.dataset.screen === target);
  if (!next) return;
  const remoteWasVisible = screens.some((screen) => screen.dataset.screen === "remote" && !screen.hidden);
  if (remoteWasVisible && target !== "remote") window.dispatchEvent(new Event("stackchanremotehide"));
  screens.forEach((screen) => {
    const active = screen === next;
    screen.hidden = !active;
    screen.classList.toggle("is-active", active);
  });
  tabButtons.forEach((button) => {
    const active = button.dataset.target === target;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (updateUrl && window.location.hash !== `#${target}`) history.replaceState(null, "", `#${target}`);
  if (target === "remote") window.requestAnimationFrame(() => window.dispatchEvent(new Event("stackchanremoteshow")));
  window.dispatchEvent(new CustomEvent("stackchanscreenchange", { detail: { target } }));
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}

document.querySelectorAll("[data-target]").forEach((control) => {
  control.addEventListener("click", () => activateScreen(control.dataset.target));
});

// 没有指定页面时先落在对话：这是这个 App 主要要做的事。
const requested = window.location.hash.slice(1);
const initialScreen = screens.some((screen) => screen.dataset.screen === requested) ? requested : "chat";
activateScreen(initialScreen, false);
window.addEventListener("hashchange", () => activateScreen(window.location.hash.slice(1), false));

createSettingsController({ activateSettings: () => activateScreen("settings", false) });

document.querySelectorAll("[data-toast]").forEach((control) => {
  control.addEventListener("click", () => showToast(control.dataset.toast));
});

// 同步滑块的视觉进度，让数值状态和 CSS 展示保持一致。
function syncRange(input) {
  const minimum = Number(input.min || 0);
  const maximum = Number(input.max || 100);
  const progress = ((Number(input.value) - minimum) / (maximum - minimum)) * 100;
  input.style.setProperty("--range", `${progress}%`);
}

document.querySelectorAll('input[type="range"]').forEach((input) => {
  syncRange(input);
  input.addEventListener("input", () => syncRange(input));
});

createRemoteController({ api });
createCameraPanelController({ api });
createDeviceTestController({ api, showToast, syncRange });
createUpdateController({ api });
createChatController({ api });
createScreenProgramsController({ api });

startDeviceStatusPolling();

if ("serviceWorker" in navigator) {
  let reloadingForServiceWorker = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloadingForServiceWorker || !navigator.serviceWorker.controller) return;
    reloadingForServiceWorker = true;
    window.location.reload();
  });
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js?v=29"));
}
