import SwiftUI

/// 根场景（Tab 容器）。
///
/// ⭐ 契约出处：`docs/spec/07-待拍板清单与防返工机制.md` §3.4b
///    （2026-10-25 第二次拍板：**主界面 = 控制台，聊天降级为小功能**）；
///    `docs/spec/00` §4.1；`docs/spec/01` §2；
///    `docs/spec/02` §1 Q-7「Tab ≤ 5 且永不溢出」；
///    `docs/research/19` §2 R17（导航深度 ≤ 2）。
///
/// ⛔ **本文件不含任何布局与视觉**：Tab 图标、顺序的最终形态、页面转场待用户拍板。
///    目前只保留两个 Tab 的**结构**。
struct RootScene: View {

    /// 当前选中的 Tab。
    @State private var selection: Tab = .control

    /// Tab 标识。
    enum Tab: String, Hashable, CaseIterable {
        /// 控制台页（主界面）：设备卡 / 状态 / 摇杆 / 表情 / 动作。
        case control
        /// 设置页：设备 / 网络 / 陪伴 / 通用。
        case settings
    }

    var body: some View {
        TabView(selection: $selection) {
            // TODO(pending design decision): Tab 图标与转场待拍板
            StackView()
                .tabItem { Text("控制") }
                .tag(Tab.control)

            SettingsScene()
                .tabItem { Text("设置") }
                .tag(Tab.settings)
        }
    }
}
