import SwiftUI

/// App 入口。
///
/// ⭐ 场景结构（2026-10-25 第二次 IA 拍板，见 `docs/spec/07` §3.4b）：
///    「**Tab 2 个（控制 / 设置）**，不用厚重玻璃 Dock」
///    ⇒ 主场景是 TabView；**设置就是 Tab 2**（不再是独立 Scene）；
///    **对话降级为二级页**（从 Tab 1 的「和它说话」进入），不是 Tab。
///
/// ⚠️ **对话二级页的路由尚未实现**（sheet / 导航栈 push 择一未拍板）——
///    见 `docs/spec/09` §九 的实施欠账登记。
///
/// ⛔ **主题选择器是开发期开关**：视觉方向尚未拍板
///    （`docs/research/63-夜间自主工作纪要-20261024.md` §3.4），
///    拍板后应当收敛掉这行用户可见开关。
@main
struct StackChanCompanionApp: App {

    /// 当前主题选择（注入环境）。开发期可切换。
    @State private var themeChoice: ThemeChoice = .light

    var body: some Scene {
        WindowGroup {
            RootScene()
                .environment(\.themeChoice, themeChoice)
        }
    }
}
