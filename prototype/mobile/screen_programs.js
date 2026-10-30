// 控制机器人上的屏幕应用；网页按钮通过接口请求设备切换或操作应用。
export function createScreenProgramsController({ api }) {
  const feedback = document.querySelector("#screenProgramFeedback");
  const buttons = [...document.querySelectorAll("[data-screen-program]")];
  const connection = document.querySelector("[data-screen-connection]");
  if (!feedback || !buttons.length || !connection) return;

  // 分别记录连接状态和目录是否加载，按钮是否可用需要同时考虑这两项。
  let deviceOnline = false;
  let loaded = false;

  // 根据在线状态与程序信息更新按钮，避免离线时仍显示可执行操作。
  function renderAvailability() {
    buttons.forEach(button => {
      button.disabled = !deviceOnline || button.dataset.uiBusy === "true";
      const action = button.querySelector("i");
      if (action) action.textContent = deviceOnline ? "打开" : "离线";
    });
    connection.textContent = deviceOnline ? "小栈在线" : "小栈未连接";
    connection.dataset.connectionState = deviceOnline ? "online" : "offline";
    if (loaded) {
      feedback.textContent = deviceOnline
        ? "选择一个功能，小栈会直接切换到对应页面。"
        : "屏幕功能已经对齐；等小栈重新上线后即可从手机打开。";
    }
  }

  // 向后端查询屏幕应用目录，再据此刷新可用状态；网页不硬编码所有设备能力。
  async function loadPrograms() {
    try {
      const payload = await api.get("/screen-programs");
      const available = new Map((payload.programs || []).map(program => [program.id, program]));
      buttons.forEach(button => {
        const program = available.get(button.dataset.screenProgram);
        if (!program) {
          button.hidden = true;
          return;
        }
        button.hidden = false;
        button.querySelector("strong").textContent = program.name;
        button.querySelector("small").textContent = program.description;
      });
      deviceOnline = payload.device?.connected === true;
      loaded = true;
      renderAvailability();
    } catch (error) {
      loaded = true;
      feedback.textContent = error?.message || "暂时无法读取屏幕功能。";
      renderAvailability();
    }
  }

  buttons.forEach(button => {
    button.addEventListener("click", async () => {
      if (!deviceOnline || button.dataset.uiBusy === "true") return;
      const programId = button.dataset.screenProgram;
      button.dataset.uiBusy = "true";
      button.disabled = true;
      const action = button.querySelector("i");
      if (action) action.textContent = "打开中";
      feedback.textContent = `正在让小栈打开${button.querySelector("strong").textContent}…`;
      try {
        const payload = await api.post("/screen-programs/control", {
          program_id: programId,
          action: "open",
        });
        feedback.textContent = `已让小栈打开${payload.program?.name || "这个功能"}。`;
      } catch (error) {
        feedback.textContent = error?.message || "没有打开成功，请确认小栈仍然在线。";
      } finally {
        button.dataset.uiBusy = "false";
        renderAvailability();
      }
    });
  });

  window.addEventListener("stackchandevicestatus", event => {
    deviceOnline = event.detail?.live === true;
    renderAvailability();
  });
  loadPrograms();
}
