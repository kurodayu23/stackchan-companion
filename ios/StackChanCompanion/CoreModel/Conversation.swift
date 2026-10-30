import Foundation

/// 一段对话（消息的有序集合）。
///
/// ⛔ 纯数据模型，不含视觉决策。
/// ⭐ 出处：`docs/spec/01-功能取舍与主次折叠.md` §3 元素 2（对话流）
public struct Conversation: Equatable, Sendable, Codable, Identifiable {

    /// 本地唯一标识。
    public let id: UUID

    /// 消息列表（时间升序）。
    public private(set) var messages: [Message]

    public init(id: UUID = UUID(), messages: [Message] = []) {
        self.id = id
        self.messages = messages
    }

    /// 追加一条消息。
    public mutating func append(_ message: Message) {
        messages.append(message)
    }

    /// 取某个来源的最后一条消息。
    public func lastMessage(from source: MessageSource) -> Message? {
        messages.last { $0.source == source }
    }

    /// 小栈说的话（主气泡流）。
    public var stackMessages: [Message] { messages.filter { $0.source == .stack } }
    /// 你说的话。
    public var userMessages: [Message] { messages.filter { $0.source == .user } }
    /// 系统事件（独立层级，不混进气泡流）。
    public var systemEvents: [Message] { messages.filter { $0.source == .systemEvent } }
}
