import SwiftUI

/// 麦克风键（按住说话）。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 4（底，圆形，**按住说话**）
///    `DESIGN.md` §9 组件清单「按住说话条」：
///    「两端 | 按住说话 / 松手结束；iOS 按住时浮出「发送/取消」
///      | 禁隐藏手势（必须另有可见入口）」
///
/// ⚠️ **机制性硬线**：
///    - 触摸目标 ≥ 44×44pt（`docs/research/19` §1.2 F5）。
///    - 按住时必须浮出「发送 / 取消」，**手势不得是唯一入口**（Floor P8 / F5 同源）。
///
/// ⛔ 形状、配色、按压反馈待拍板。
struct MicButton: View {

    /// 按下 / 松开。
    var onPressChanged: (Bool) -> Void

    var body: some View {
        // TODO(pending design decision): 麦克风键视觉待拍板
        //   契约：docs/spec/01 §3 元素 4；触摸目标 ≥44pt（F5）
        EmptyView()
    }
}
