const COMPONENT_LABELS = {
  computer: "配套电脑",
  mobile: "手机界面",
  firmware: "小栈软件",
  assets: "屏幕资源",
};

const STATE_LABELS = {
  unavailable: "尚未配置更新源",
  idle: "可以检查更新",
  checking: "正在检查更新",
  available: "发现可用更新",
  downloading: "正在安全下载",
  staged: "更新已经准备好",
  installing: "正在安装更新",
  completed: "更新已经完成",
  failed: "更新失败，可以重试",
  rolling_back: "正在恢复上一版本",
  rolled_back: "已恢复上一版本",
};

const ACTIVE_STATES = new Set(["checking", "downloading", "installing", "rolling_back"]);

// 统一更新页面入口：查询发布状态并触发检查、准备和安装等阶段。
// 页面进度以服务端状态为依据，下载或请求成功不等于设备已经重启到新版本。
export function createUpdateController({ api }) {
  const connection = document.querySelector("#updateConnection");
  const version = document.querySelector("#updateVersion");
  const stateText = document.querySelector("#updateState");
  const message = document.querySelector("#updateMessage");
  const componentList = document.querySelector("#updateComponentList");
  const progressBox = document.querySelector("#updateProgress");
  const progress = document.querySelector("#updateProgressValue");
  const progressLabel = progressBox?.querySelector("span");
  const feedback = document.querySelector("#updateFeedback");
  const checkButton = document.querySelector("#updateCheckButton");
  const primaryButton = document.querySelector("#updatePrimaryButton");
  // 保存最近一次服务端状态；armedAction、计时器和页面可见性用于管理交互过程。
  let current = null;
  let armedAction = null;
  let armTimer = null;
  let pollTimer = null;
  let updateVisible = document.querySelector('[data-screen="update"]')?.hidden === false;

  function setFeedback(text, tone = "") {
    if (!feedback) return;
    feedback.textContent = text;
    feedback.dataset.tone = tone;
  }

  // 分别展示电脑、手机、固件和资源的状态，避免只看一个总进度误判完整发布。
  function renderComponents(components = {}) {
    componentList?.replaceChildren();
    Object.entries(COMPONENT_LABELS).forEach(([name, label]) => {
      const item = components[name] || {};
      const row = document.createElement("div");
      row.className = "update-component-row";
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      const detail = document.createElement("small");
      const badge = document.createElement("span");
      title.textContent = label;
      detail.textContent = item.target_version
        ? `${item.current_version || "未上报"} → ${item.target_version}`
        : item.current_version || "等待检查";
      badge.className = "component-state";
      badge.textContent = STATE_LABELS[item.state] || "等待检查";
      copy.append(title, detail);
      row.append(copy, badge);
      componentList?.append(row);
    });
  }

  // 根据状态机选择准备或安装按钮，不能跳过暂存阶段直接假定可安装。
  function configureButtons(status) {
    const active = ACTIVE_STATES.has(status.state);
    checkButton.disabled = active;
    checkButton.textContent = status.state === "checking" ? "正在检查…" : "检查更新";
    const action = status.state === "available" ? "prepare" : status.state === "staged" ? "install" : null;
    primaryButton.hidden = !action;
    primaryButton.disabled = !action || !status.release_id;
    if (action) primaryButton.textContent = action === "install" ? "安装全部更新" : "准备全部更新";
  }

  // 把服务端各组件进度汇总到页面；这里的平均百分比是展示指标，不是设备实测耗时比例。
  function render(status) {
    current = status || {};
    const componentProgress = Object.values(current.components || {})
      .map((item) => Number(item?.progress))
      .filter(Number.isFinite);
    const averageProgress = componentProgress.length
      ? componentProgress.reduce((total, value) => total + value, 0) / componentProgress.length
      : 0;
    const numericProgress = Math.max(0, Math.min(100, averageProgress));
    stateText.textContent = STATE_LABELS[current.state] || "等待检查";
    message.textContent = current.message || "可用更新会在这里集中显示。";
    version.textContent = current.release_version ? `可用版本 StackChan ${current.release_version}` : "当前没有已确认的新版本";
    renderComponents(current.components);
    progressBox.hidden = !ACTIVE_STATES.has(current.state) && current.state !== "completed";
    progress.value = numericProgress;
    progressLabel.textContent = `${Math.round(numericProgress)}%`;
    configureButtons(current);
    schedulePoll(current.state);
  }

  // 只有更新页可见且仍在进行时才安排下一轮查询，减少后台无效请求。
  function schedulePoll(state) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
    if (updateVisible && ACTIVE_STATES.has(state)) {
      pollTimer = window.setTimeout(refresh, 3000);
    }
  }

  // 先检查页面可见性和配对状态，再读取更新状态；连接失败显示错误而不伪造进度。
  async function refresh() {
    if (!updateVisible || document.visibilityState !== "visible") return;
    try {
      if (!(await api.isPaired())) {
        connection.textContent = "手机尚未配对";
        setFeedback("先在小栈上完成手机配对，再检查更新。", "error");
        return;
      }
      connection.textContent = window.stackChanDeviceState?.live === true ? "小栈已连接" : "小栈暂未在线";
      render(await api.get("/update/status"));
    } catch (error) {
      connection.textContent = "更新服务暂时不可用";
      setFeedback(error?.message || "无法读取更新状态", "error");
    }
  }

  checkButton?.addEventListener("click", async () => {
    checkButton.disabled = true;
    setFeedback("正在检查签名更新…");
    try {
      await api.post("/update/check", {});
      setFeedback("检查完成。", "success");
      await refresh();
    } catch (error) {
      setFeedback(`检查失败：${error.message}`, "error");
      checkButton.disabled = false;
    }
  });

  primaryButton?.addEventListener("click", async () => {
    const action = current?.state === "available" ? "prepare" : current?.state === "staged" ? "install" : null;
    if (!action || !current?.release_id) return;
    if (armedAction !== action) {
      armedAction = action;
      primaryButton.textContent = "再次点击确认";
      setFeedback(action === "install" ? "再次点击后开始安装；期间请勿断电。" : "再次点击后下载并校验全部组件。", "warning");
      window.clearTimeout(armTimer);
      armTimer = window.setTimeout(() => {
        armedAction = null;
        configureButtons(current);
        setFeedback("");
      }, 8000);
      return;
    }
    armedAction = null;
    window.clearTimeout(armTimer);
    primaryButton.disabled = true;
    primaryButton.textContent = action === "install" ? "正在启动安装…" : "正在准备…";
    try {
      await api.post(`/update/${action}`, { release_id: current.release_id }, {
        headers: { "X-StackChan-Confirm": action === "install" ? "install-release" : "prepare-release" },
        timeout: action === "install" ? 20000 : 120000,
      });
      setFeedback(action === "install" ? "更新已经开始，请保持供电和网络稳定。" : "更新包已完成安全准备。", "success");
      await refresh();
    } catch (error) {
      setFeedback(`${action === "install" ? "安装" : "准备"}失败：${error.message}`, "error");
      configureButtons(current);
    }
  });

  window.addEventListener("stackchanscreenchange", (event) => {
    updateVisible = event.detail?.target === "update";
    if (updateVisible) refresh();
    else schedulePoll("idle");
  });
  window.addEventListener("stackchandevicestatus", (event) => {
    if (connection) connection.textContent = event.detail?.live === true ? "小栈已连接" : "小栈暂未在线";
  });
  if (updateVisible) refresh();

  return { refresh };
}
