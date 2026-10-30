// mobile-v2 主应用：单屏遥控台（3D + 摇杆 + 聊天 + 状态）
import { api } from "./api.js";
import { createPreview } from "./preview3d.js";
import { createRemoteController } from "./remote.js";
import { createChatController } from "./chat.js";

const statusBar = document.querySelector("#statusBar");
const statusText = document.querySelector("#statusText");
const deviceName = document.querySelector("#deviceName");
const modeChip = document.querySelector("#modeChip");
const modelStateTime = document.querySelector("#chatModelState");

const POLL_INTERVAL_MS = 4000;
let deviceOnline = false;
let lastDeviceStatus = null;

function setStatus(text, state) {
  statusBar.dataset.state = state;
  statusText.textContent = text;
}

function setMode(mode) {
  modeChip.dataset.mode = mode;
  modeChip.textContent = mode === "demo" ? "演示" : "真机";
}

async function pollDeviceStatus() {
  try {
    const status = await api.get("/device/status", { timeout: 3000 });
    lastDeviceStatus = status;
    deviceOnline = Boolean(status?.status?.connected);
    if (deviceOnline) {
      setStatus(status?.status?.device_id ? `在线 · ${status.status.device_id}` : "在线", "online");
    } else {
      setStatus("设备离线 · 演示模式可用", "offline");
    }
    setMode(deviceOnline ? "real" : "demo");
    window.dispatchEvent(new CustomEvent("stackchandevicestatus", { detail: status }));
  } catch {
    deviceOnline = false;
    setStatus("未连接后台 · 演示模式", "offline");
    setMode("demo");
  }
}

// 打字状态下不打断模型；思考时眯眼（用 LED 变暗表达）
function setThinking(thinking) {
  document.body.classList.toggle("is-thinking", thinking);
}

const preview = createPreview();
const remote = createRemoteController({
  api,
  preview,
  onDeviceStatus: (sync) => window.addEventListener("stackchandevicestatus", (event) => sync(event.detail)),
});
createChatController({ onThinkingChanged: setThinking });

// 首次轮询立即执行，之后定时
pollDeviceStatus();
window.setInterval(pollDeviceStatus, POLL_INTERVAL_MS);

// 模式点击：手动切换（真机 / 演示），轮询会在下一次自动校正
modeChip.addEventListener("click", async () => {
  if (document.body.dataset.mode !== "demo") return;
  await pollDeviceStatus();
});

// 状态条不可见时不打扰用户；仅在初始化完成时显示就绪
setStatus("正在连接…", "offline");