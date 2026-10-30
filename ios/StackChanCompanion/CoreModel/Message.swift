import Foundation

/// 对话消息的**来源**（三种，必须视觉分层 —— 但分层样式待拍板）。
///
/// ⭐ 出处：`docs/spec/01-功能取舍与主次折叠.md` §3 元素 2
///    「对话流 … 小栈的话 / 系统事件 / 你说的话，**三种来源视觉分层**」
///    `docs/spec/00-StackChan产品规格与技术规格.md` §2.1
///    「三种来源**必须**视觉分层：① 小栈说的话（主气泡）② 系统事件（独立视觉层级，
///    **不能混进气泡流**）③ 你说的话」
public enum MessageSource: String, CaseIterable, Sendable, Codable {
    /// 小栈说的话。
    case stack
    /// 系统事件（你离开了 / 它低落了 / 你回来了 / 它被换了人格）。
    case systemEvent
    /// 你说的话。
    case user
}

/// 一条对话消息。
///
/// ⛔ 纯数据模型，**不含任何视觉决策**（气泡样式、颜色、字号都在 DesignSystem / Feature 层，且待拍板）。
public struct Message: Identifiable, Equatable, Sendable, Codable {

    /// 本地唯一标识。
    public let id: UUID

    /// 消息来源（决定视觉分层）。
    public let source: MessageSource

    /// 正文。
    public let text: String

    /// 产生时间。
    public let timestamp: Date

    /// 发送状态（本地乐观值）。
    public var delivery: DeliveryState

    /// 发送状态。
    public enum DeliveryState: String, Equatable, Sendable, Codable {
        /// 本地待发。
        case pending
        /// 已送达服务端。
        case sent
        /// 发送失败（错误提示必须说明怎么修 —— `docs/spec/02` §1 Q-10）。
        case failed
    }

    public init(id: UUID = UUID(),
                source: MessageSource,
                text: String,
                timestamp: Date = Date(),
                delivery: DeliveryState = .pending) {
        self.id = id
        self.source = source
        self.text = text
        self.timestamp = timestamp
        self.delivery = delivery
    }
}
