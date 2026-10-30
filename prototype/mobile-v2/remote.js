// mobile-v2 摇杆遥控模块：模型(演示)与真机双轨，同一目标接口。
// 数值口径与旧移动端 / 17865 控制台一致：yaw ±128、pitch 3–87、死区 8%、四档速度。

const HEAD_SEND_INTERVAL_MS = 100;
const HEAD_SPEEDS = [100, 220, 520, 850];
const SPEED_LABELS = ["安静", "轻柔", "自然", "活泼"];
const JOYSTICK_DEAD_ZONE = 0.08;
const DEFAULT_SPEED_LEVEL = 2;
const YAW_MAX = 128;
const PITCH_CENTER = 45;
const PITCH_LIMIT = 42; // 45 ± 42 → 3..87

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

export function createRemoteController({ api, preview, onDeviceStatus }) {
  const joystick = document.querySelector("#joystick");
  const joystickKnob = document.querySelector("#joystickKnob");
  const poseYaw = document.querySelector("#poseYaw");
  const posePitch = document.querySelector("#posePitch");
  const stageChip = document.querySelector("#stageChip");
  const speedDots = [...document.querySelectorAll("[data-speed-level]")];
  const speedValue = document.querySelector("#speedValue");
  const centerHead = document.querySelector("#centerHead");
  const nodHead = document.querySelector("#nodHead");

  let currentYaw = 0;
  let currentPitch = 45;
  let speedLevel = DEFAULT_SPEED_LEVEL;
  let pendingHeadTarget = null;
  let lastSentAt = 0;
  let joystickPointer = null;
  let previewPointer = null;
  let previewStartX = 0;
  let previewStartY = 0;
  let previewStartYaw = 0;
  let previewStartPitch = 0;
  let deviceOnline = false;

  function joystickLimit() {
    const knobSize = joystickKnob.offsetWidth || 52;
    const bounds = joystick.getBoundingClientRect();
    return Math.max(1, Math.min(bounds.width, bounds.height) / 2 - knobSize / 2 - 4);
  }

  function moveKnob(yaw, pitch) {
    const limit = joystickLimit();
    const x = (yaw / YAW_MAX) * limit;
    const y = ((PITCH_CENTER - pitch) / PITCH_LIMIT) * limit;
    joystickKnob.style.transform = `translate(${x}px, ${y}px)`;
    joystickKnob.style.setProperty("--look-x", `${(yaw / YAW_MAX) * 5}px`);
    joystickKnob.style.setProperty("--look-y", `${((PITCH_CENTER - pitch) / PITCH_LIMIT) * 5}px`);
  }

  function applyRobotPose(yaw, pitch, updateKnob = true, send = true) {
    currentYaw = clamp(Math.round(yaw), -YAW_MAX, YAW_MAX);
    currentPitch = clamp(Math.round(pitch), 3, 87);
    if (updateKnob) moveKnob(currentYaw, currentPitch);
    if (preview && typeof preview.setPose === "function") preview.setPose(currentYaw, currentPitch);
    if (poseYaw) poseYaw.textContent = `${currentYaw}°`;
    if (posePitch) posePitch.textContent = `${currentPitch}°`;
    if (stageChip) stageChip.textContent = `● 当前：Yaw ${currentYaw} / Pitch ${currentPitch}`;
    if (send) queueHeadTarget();
  }

  function queueHeadTarget() {
    pendingHeadTarget = { yaw: currentYaw, pitch: currentPitch, speed: HEAD_SPEEDS[speedLevel] };
    const delay = Math.max(0, HEAD_SEND_INTERVAL_MS - (performance.now() - lastSentAt));
    clearTimeout(window.__headSendTimer);
    window.__headSendTimer = setTimeout(flushHeadTarget, delay);
  }

  async function flushHeadTarget() {
    const target = pendingHeadTarget;
    if (!target) return;
    // 数据竞态保护：新的拖动会覆盖 pending，只有当前 target 仍是最新才发送。
    if (pendingHeadTarget !== target) return;
    pendingHeadTarget = null;
    if (!deviceOnline) return; // 演示模式：仅 3D 模型，不请求真机
    try {
      await api.post("/device/head", target, { timeout: 3000 });
      lastSentAt = performance.now();
    } catch {
      // 真机抖动：静默丢帧，由下一次拖动补发
    }
  }

  function setJoystick(x, y) {
    const limit = joystickLimit();
    const distance = Math.hypot(x, y);
    const scale = distance > limit ? limit / distance : 1;
    const offsetX = x * scale;
    const offsetY = y * scale;
    if (distance / limit <= JOYSTICK_DEAD_ZONE) {
      moveKnob(currentYaw, currentPitch);
      return;
    }
    joystickKnob.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    joystickKnob.style.setProperty("--look-x", `${(offsetX / limit) * 5}px`);
    joystickKnob.style.setProperty("--look-y", `${(offsetY / limit) * 5}px`);
    applyRobotPose((offsetX / limit) * YAW_MAX, PITCH_CENTER - (offsetY / limit) * PITCH_LIMIT, false);
  }

  function setSpeedLevel(level, send = true) {
    speedLevel = clamp(level, 0, 3);
    speedDots.forEach((dot) => {
      const active = Number(dot.dataset.speedLevel) === speedLevel;
      dot.classList.toggle("is-active", active);
      dot.setAttribute("aria-pressed", String(active));
    });
    if (speedValue) speedValue.textContent = SPEED_LABELS[speedLevel];
    if (send) queueHeadTarget();
  }

  function syncDeviceStatus(status) {
    const head = status?.status?.head;
    deviceOnline = Boolean(status?.status?.connected);
    if (head && Number.isFinite(Number(head.yaw))) {
      applyRobotPose(Number(head.yaw), Number(head.pitch), true, false);
    }
  }

  joystick.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    joystickPointer = event.pointerId;
    joystick.setPointerCapture(event.pointerId);
    joystick.classList.add("is-controlling");
    const bounds = joystick.getBoundingClientRect();
    setJoystick(event.clientX - bounds.left - bounds.width / 2, event.clientY - bounds.top - bounds.height / 2);
  });
  joystick.addEventListener("pointermove", (event) => {
    if (joystickPointer !== event.pointerId) return;
    event.preventDefault();
    const bounds = joystick.getBoundingClientRect();
    setJoystick(event.clientX - bounds.left - bounds.width / 2, event.clientY - bounds.top - bounds.height / 2);
  });
  function releaseJoystick(event) {
    if (joystickPointer !== event.pointerId) return;
    joystickPointer = null;
    joystick.classList.remove("is-controlling");
    flushHeadTarget();
  }
  joystick.addEventListener("pointerup", releaseJoystick);
  joystick.addEventListener("pointercancel", releaseJoystick);

  // 3D 舞台本身也可以拖动（与 17865 控制台一致）
  const canvas = document.querySelector("#robotPreviewCanvas");
  if (canvas) {
    canvas.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      previewPointer = event.pointerId;
      previewStartX = event.clientX;
      previewStartY = event.clientY;
      previewStartYaw = currentYaw;
      previewStartPitch = currentPitch;
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add("is-controlling");
    });
    canvas.addEventListener("pointermove", (event) => {
      if (previewPointer !== event.pointerId) return;
      event.preventDefault();
      const bounds = canvas.getBoundingClientRect();
      applyRobotPose(
        previewStartYaw + ((event.clientX - previewStartX) / bounds.width) * 256,
        previewStartPitch - ((event.clientY - previewStartY) / bounds.height) * 84,
      );
    });
    const releasePreview = (event) => {
      if (previewPointer !== event.pointerId) return;
      previewPointer = null;
      canvas.classList.remove("is-controlling");
      flushHeadTarget();
    };
    canvas.addEventListener("pointerup", releasePreview);
    canvas.addEventListener("pointercancel", releasePreview);
  }

  // 键盘：方向键 / Home
  function applyKeyboardPose(event) {
    const poses = {
      ArrowLeft: [currentYaw - 8, currentPitch],
      ArrowRight: [currentYaw + 8, currentPitch],
      ArrowUp: [currentYaw, currentPitch + 3],
      ArrowDown: [currentYaw, currentPitch - 3],
      Home: [0, 45],
    };
    if (!poses[event.key]) return;
    event.preventDefault();
    applyRobotPose(...poses[event.key]);
  }
  joystick.addEventListener("keydown", applyKeyboardPose);
  if (canvas) canvas.addEventListener("keydown", applyKeyboardPose);

  speedDots.forEach((dot) => {
    dot.addEventListener("click", () => setSpeedLevel(Number(dot.dataset.speedLevel)));
  });

  centerHead?.addEventListener("click", () => applyRobotPose(0, 45));
  nodHead?.addEventListener("click", async () => {
    if (deviceOnline) {
      try { await api.post("/device/head", { yaw: currentYaw, pitch: 40, speed: HEAD_SPEEDS[speedLevel] }, { timeout: 3000 }); } catch { /* ignore */ }
      try { await new Promise((r) => setTimeout(r, 620)); await api.post("/device/head", { yaw: currentYaw, pitch: 12, speed: HEAD_SPEEDS[speedLevel] }, { timeout: 3000 }); } catch { /* ignore */ }
      try { await new Promise((r) => setTimeout(r, 160)); await api.post("/device/head", { yaw: currentYaw, pitch: 6, speed: 520 }, { timeout: 3000 }); } catch { /* ignore */ }
    } else {
      applyRobotPose(currentYaw, 40);
      setTimeout(() => applyRobotPose(currentYaw, 12), 300);
      setTimeout(() => applyRobotPose(currentYaw, 6), 500);
    }
  });

  if (onDeviceStatus) onDeviceStatus(syncDeviceStatus);
  setSpeedLevel(DEFAULT_SPEED_LEVEL, false);
  applyRobotPose(0, 45, true, false);

  return { flushHeadTarget };
}