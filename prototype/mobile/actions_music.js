// 音乐与动作控制入口：复用 API 执行设备操作，并向页面反馈结果。
export function createDeviceTestController({ api, showToast, syncRange }) {
  const actionTiles = [...document.querySelectorAll(".action-tile[data-preset]")];
  const currentActionTitle = document.querySelector("#currentActionTitle");
  const currentActionDescription = document.querySelector("#currentActionDescription");
  const actionRunState = document.querySelector("#actionRunState");
  const actionState = document.querySelector(".standby");
  const executeAction = document.querySelector("#executeAction");
  const brightness = document.querySelector("#testBrightness");
  const brightnessValue = document.querySelector("#testBrightnessValue");
  const brightnessButton = document.querySelector("#testBrightnessButton");
  const volume = document.querySelector("#testVolume");
  const volumeValue = document.querySelector("#testVolumeValue");
  const soundSelect = document.querySelector("#testSoundSelect");
  const soundButton = document.querySelector("#testSoundButton");
  const soundState = document.querySelector("#testSoundState");
  let selectedAction = actionTiles.find((tile) => tile.classList.contains("is-selected")) || actionTiles[0];
  let actionTimer = null;
  // 保留已确认的亮度和音量，区分滑块预览值与接口操作确认值。
  let confirmedBrightness = Number(brightness?.value || 78);
  let confirmedVolume = Number(volume?.value || 58);
  let audioLoaded = false;

  // 操作前读取统一的实时连接判断，不以页面曾经加载成功代替设备在线。
  const connected = () => window.stackChanDeviceState?.live === true;

  // 同步动作执行时的控件和状态显示，避免用户重复触发同一操作。
  function setActionRunning(running, deviceConnected = connected()) {
    if (actionRunState) actionRunState.textContent = running ? "动作进行中" : "待命中";
    if (actionState) actionState.dataset.state = running ? "running" : "idle";
    if (executeAction) {
      executeAction.dataset.uiBusy = String(running);
      executeAction.disabled = running || !deviceConnected;
      executeAction.querySelector("span").textContent = running ? "进行中…" : "执行动作";
    }
  }

  // 切换选中的动作预设；选择动作与真正执行动作属于两个阶段。
  function selectAction(tile) {
    selectedAction = tile;
    actionTiles.forEach((item) => {
      item.classList.toggle("is-selected", item === tile);
      item.setAttribute("aria-pressed", String(item === tile));
      item.querySelector(".check")?.remove();
    });
    const check = document.createElement("b");
    check.className = "check";
    check.textContent = "✓";
    tile.append(check);
    if (currentActionTitle) currentActionTitle.textContent = tile.dataset.action;
    if (currentActionDescription) currentActionDescription.textContent = tile.dataset.description;
  }

  actionTiles.forEach((tile) => tile.addEventListener("click", () => selectAction(tile)));
  if (selectedAction) selectAction(selectedAction);

  executeAction?.addEventListener("click", async () => {
    if (!selectedAction || !connected()) {
      showToast("小栈未连接，动作没有发送");
      return;
    }
    executeAction.disabled = true;
    executeAction.querySelector("span").textContent = "执行中…";
    try {
      const result = await api.post("/device/macro", { preset: selectedAction.dataset.preset });
      if (result.ok !== true) throw new Error("小栈未接受动作");
      showToast(`${result.label || selectedAction.dataset.action}已开始`);
      const duration = Number(result.duration_ms);
      if (result.state === "running" && Number.isFinite(duration) && duration > 0) {
        window.clearTimeout(actionTimer);
        setActionRunning(true);
        actionTimer = window.setTimeout(() => {
          actionTimer = null;
          setActionRunning(false);
        }, Math.min(60000, Math.max(400, Math.round(duration))));
      }
    } catch (error) {
      showToast(`动作未执行：${error.message}`);
    } finally {
      if (!actionTimer) setActionRunning(false);
    }
  });

  // 从设备接口加载可播放的内置声音选项，页面据此建立选择列表。
  async function loadFactoryAudio() {
    if (audioLoaded || !soundSelect) return;
    try {
      const result = await api.get("/device/factory-audio");
      const sounds = Array.isArray(result.sounds) ? result.sounds : [];
      soundSelect.replaceChildren();
      sounds.forEach((sound) => {
        const option = document.createElement("option");
        option.value = sound.id;
        option.textContent = sound.label;
        soundSelect.append(option);
      });
      audioLoaded = sounds.length > 0;
      if (!audioLoaded) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "没有可用的内置声音";
        soundSelect.append(option);
      }
    } catch (error) {
      if (soundState) soundState.textContent = error?.status === 401 ? "手机未配对" : "声音列表读取失败";
    }
  }

  brightness?.addEventListener("input", () => {
    brightnessValue.textContent = `待发送 ${brightness.value}%`;
  });
  brightnessButton?.addEventListener("click", async () => {
    const requested = Number(brightness.value);
    brightnessButton.disabled = true;
    try {
      const result = await api.post("/device/brightness", { brightness: requested });
      if (!Number.isFinite(result.brightness)) throw new Error("没有收到有效亮度");
      confirmedBrightness = result.brightness;
      brightness.value = String(confirmedBrightness);
      brightnessValue.textContent = `已确认 ${confirmedBrightness}%`;
    } catch (error) {
      brightness.value = String(confirmedBrightness);
      brightnessValue.textContent = `未确认 · ${confirmedBrightness}%`;
      showToast(`亮度未改变：${error.message}`);
    } finally {
      brightnessButton.disabled = !connected();
      syncRange(brightness);
    }
  });

  volume?.addEventListener("input", () => {
    volumeValue.textContent = `待发送 ${volume.value}%`;
  });
  volume?.addEventListener("change", async () => {
    const requested = Number(volume.value);
    volume.disabled = true;
    try {
      const result = await api.post("/device/volume", { volume: requested, permanent: false });
      if (!Number.isFinite(result.volume)) throw new Error("没有收到有效音量");
      confirmedVolume = result.volume;
      volume.value = String(confirmedVolume);
      volumeValue.textContent = `已确认 ${confirmedVolume}%`;
    } catch (error) {
      volume.value = String(confirmedVolume);
      volumeValue.textContent = `未确认 · ${confirmedVolume}%`;
      showToast(`音量未改变：${error.message}`);
    } finally {
      volume.disabled = !connected();
      syncRange(volume);
    }
  });

  soundButton?.addEventListener("click", async () => {
    if (!soundSelect?.value || !connected()) return;
    soundButton.disabled = true;
    soundState.textContent = "正在播放…";
    try {
      const result = await api.post("/device/factory-audio", { sound: soundSelect.value });
      if (result.ok !== true) throw new Error("小栈未确认播放");
      soundState.textContent = `已播放 · ${result.label || "测试音"}`;
    } catch (error) {
      soundState.textContent = "播放失败";
      showToast(`测试音未播放：${error.message}`);
    } finally {
      soundButton.disabled = !connected();
    }
  });

  window.addEventListener("stackchandevicestatus", (event) => {
    const status = event.detail?.status || {};
    const deviceConnected = event.detail?.live === true;
    const running = status?.stage?.state === "running";
    if (!running && actionTimer) {
      window.clearTimeout(actionTimer);
      actionTimer = null;
    }
    setActionRunning(running, deviceConnected);
    [brightness, volume, soundSelect, soundButton, brightnessButton].forEach((control) => {
      if (control) control.disabled = !deviceConnected;
    });
    const reportedVolume = status?.music?.volume;
    if (Number.isFinite(reportedVolume)) {
      confirmedVolume = reportedVolume;
      volume.value = String(reportedVolume);
      volumeValue.textContent = `已确认 ${reportedVolume}%`;
      syncRange(volume);
    }
  });

  window.addEventListener("stackchanscreenchange", (event) => {
    if (event.detail?.target === "test") loadFactoryAudio();
  });
  if (document.querySelector('[data-screen="test"]')?.hidden === false) loadFactoryAudio();

  return { loadFactoryAudio };
}
