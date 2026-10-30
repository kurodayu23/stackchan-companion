import ActivityKit
import SwiftUI
import WidgetKit
import StackChanShared

/// Live Activity 的 Widget Extension。
///
/// ⭐ 契约出处：`docs/spec/01-功能取舍与主次折叠.md` §3 元素 10–11
///    10. Live Activity 紧凑态 | 锁屏/灵动岛 | 图形 | **只有情绪图形，没有文字**
///    11. Live Activity 展开态 | 锁屏/灵动岛 | 一行 + 一按钮 | 情绪 + 在场 + 一句话 + 一个动作
///
/// ⚠️ **紧凑态零文字**是硬线（元素 10 + `DESIGN.md` §9「禁写文字状态标签」
///    + `docs/research/19` §1.7 F32「静止即状态」）。
///    ⇒ 本文件在紧凑区（compactLeading / compactTrailing / minimal）**不出现任何 Text**。
///
/// ⛔ **展开态内容与全部视觉待用户拍板**；此外
///    「展开态是否带一句话」本身还有口径冲突（见 `StackChanAttributes.swift` 文件头的说明），
///    未裁决前只留空位。
struct StackChanLiveActivityWidget: Widget {

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: StackChanAttributes.self) { context in
            // TODO(pending design decision): 锁屏展开态的布局与内容待拍板
            //   契约：docs/spec/01 §3 元素 11
            EmptyView()
        } dynamicIsland: { context in
            DynamicIsland {
                // TODO(pending design decision): 灵动岛展开区内容待拍板
                DynamicIslandExpandedRegion(.leading) {
                    EmptyView()
                }
                DynamicIslandExpandedRegion(.trailing) {
                    EmptyView()
                }
                DynamicIslandExpandedRegion(.center) {
                    EmptyView()
                }
                DynamicIslandExpandedRegion(.bottom) {
                    EmptyView()
                }
            } compactLeading: {
                // ⛔ 紧凑态：只有图形，没有文字（docs/spec/01 §3 元素 10）
                EmptyView()
            } compactTrailing: {
                // ⛔ 紧凑态：只有图形，没有文字（docs/spec/01 §3 元素 10）
                EmptyView()
            } minimal: {
                // ⛔ 最小态：只有图形，没有文字
                EmptyView()
            }
        }
    }
}

/// Widget Extension 入口。
@main
struct StackChanLiveActivityBundle: WidgetBundle {
    var body: some Widget {
        StackChanLiveActivityWidget()
    }
}
