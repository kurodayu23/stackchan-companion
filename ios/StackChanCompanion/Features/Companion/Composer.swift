import SwiftUI

/// 输入框。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 3（底，圆角，打字）
///
/// ⚠️ **机制性硬线（可直接照做，不是视觉决策）**：
///    - 输入字号 **≥ 16pt**，否则触发 iOS 输入框自动放大导致布局跳动
///      （`docs/research/19` §1.8 F35；`docs/spec/02` §2.1）。
///    - 键盘类型 / 提交行为 / 发送态属于交互契约，实现时对齐
///      `docs/spec/00` §2.1 元素 3 与 `docs/spec/02` §2.2（尾部截断、最多 3 行）。
///
/// ⛔ 圆角、底色、字号、占位文案待拍板。
struct Composer: View {

    /// 当前输入文本。
    @Binding var text: String

    /// 发送动作。
    var onSend: () -> Void

    var body: some View {
        // TODO(pending design decision): 输入框视觉待拍板
        //   契约：docs/spec/01 §3 元素 3；输入字号 ≥16pt（F35）
        EmptyView()
    }
}
