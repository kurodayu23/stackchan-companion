import SwiftUI

/// 对话流里的一条消息。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 2 / `docs/spec/00` §2.1
///    —— **三种来源必须视觉分层**：
///       ① 小栈说的话（主气泡）② 系统事件（**独立视觉层级，不能混进气泡流**）
///       ③ 你说的话
///    参考手法：`docs/research/45-网页与设计系统快速取数方法论.md` §5.3
///    「非对称气泡 tuck：AI 气泡左上角 4pt 尖角、用户气泡右上角 4pt，其余角 18pt
///      —— **不用颜色区分说话人**」
///
/// ⛔ **三种来源各自长什么样待拍板**（是否用底色、尖角还是别的手段区分）。
///    本文件只负责按 ``MessageSource`` 分派，不定义任何样式。
struct MessageRow: View {

    /// 要显示的消息。
    let message: Message

    var body: some View {
        // TODO(pending design decision): 三种来源的视觉分层方式待拍板
        //   契约：docs/spec/00 §2.1「三种来源必须视觉分层」
        EmptyView()
    }
}
