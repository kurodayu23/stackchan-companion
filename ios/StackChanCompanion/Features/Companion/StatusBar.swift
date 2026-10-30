import SwiftUI

/// 顶部状态条。
///
/// ⭐ 契约出处：`docs/spec/01-功能取舍与主次折叠.md` §3 元素 1
///    「小栈状态条 | 陪伴页顶 | 窄条（Live Activity 风格）|
///      情绪 + 在场/等待 + 电量，**可滑动隐藏**」
///    `docs/spec/00` §2.1 元素 1：「一个元素承载 3 个信息：
///      情绪（**图形优先，最多配 1 个词**）+ 在场/等待 + 电量」
///
/// ⚠️ **入口位置已定**：状态条**顶部右侧进设置**
///    （`DESIGN.md` §14 待确认项 #4：Tab 2 个 + **独立 Settings Scene**）。
///    形状 / 配色 / 隐藏动效待拍板。
///
/// ⛔ **不写文字状态标签**：「正在听 / 正在想」这类 AI 内部状态由**小栈的脸**表达
///    （`DESIGN.md` §1 P7、§9 组件清单；`docs/research/19` §2 R5 禁止豁免）。
struct StatusBar: View {

    var body: some View {
        // TODO(pending design decision): 状态条视觉与隐藏动效待拍板
        //   契约：docs/spec/01 §3 元素 1
        EmptyView()
    }
}
