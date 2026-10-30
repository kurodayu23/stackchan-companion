import ActivityKit
import Foundation

/// Live Activity 的属性定义。
///
/// ⚠️ **这个类型必须同时被 App target 与 Widget Extension target 引用，且必须是"同一个类型"**
///    ⇒ 所以它单独放在**共享动态框架** `StackChanShared` 里（两个 target 都链接同一个二进制），
///    不能各自编译一份（静态链接会让两份的 mangled name 不同，ActivityKit 匹配不上）。
///    参考做法：Apple 官方 Emoji Rangers 示例同样用一个 shared framework 承载 `ActivityAttributes`。
///
/// ⭐ 内容边界（`docs/research/58-iOS端架构决策.md` §5）：
///    - Live Activity **4 KB 数据上限 / 8 小时活动上限**、**无网络权限**。
///    - ⛔ **不放对话正文**（锁屏会暴露）。
///    - ⚠️ **口径冲突（未裁决）**：
///      58 号 §5 说「状态词 ✅ 放」，
///      但 `docs/spec/01` §3 元素 10 说「Live Activity 紧凑态 … **只有情绪图形，没有文字**」，
///      `DESIGN.md` §9 组件清单也说「禁写文字状态标签」、`docs/research/19` §1.7 F32 同向。
///      ⇒ **以"紧凑态零文字"为准**（多数文档一致），展开态是否带一句话**待裁决**，
///        故下面的 ContentState **不含任何正文字段**。
///
/// ⛔ 表情怎么画、状态怎么表达属于视觉层，**待用户拍板**；本文件只放语义状态。
///
/// TODO(pending design decision): Live Activity 的展示形态（紧凑态图形、展开态内容）待拍板
public struct StackChanAttributes: ActivityAttributes {

    /// 活动内容状态。
    public struct ContentState: Codable, Hashable {

        /// 当前情绪（官方 6 情绪的原始名，见 `CoreProtocol.Mood`）。
        public var mood: String

        /// 在场 / 等待（见 `CoreModel.Presence`）。
        public var presence: String

        /// 是否正在说话。
        public var isSpeaking: Bool

        public init(mood: String, presence: String, isSpeaking: Bool) {
            self.mood = mood
            self.presence = presence
            self.isSpeaking = isSpeaking
        }
    }

    /// 设备名。
    public var deviceName: String

    /// 活动开始时间。
    public var startedAt: Date

    public init(deviceName: String, startedAt: Date = Date()) {
        self.deviceName = deviceName
        self.startedAt = startedAt
    }
}
