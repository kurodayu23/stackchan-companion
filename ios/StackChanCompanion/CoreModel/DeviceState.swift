import Foundation
import CoreProtocol

/// 连接状态机。
///
/// ⭐ 出处：`docs/spec/03-通信链路预设与数据契约.md` §4.1「建议的连接状态机
///    （**UI 必须能表达这 6 个状态**）」
///
///    UI 铁律（同节）：**连接状态变化不弹窗、不打断对话**，只在状态条上体现。
///
/// ⚠️ **口径差异（公开订正）**：`docs/research/58-iOS端架构决策.md` §3 给的是另一组六态
///    （`disconnected / connecting / connectedDeviceOffline / connectedDeviceOnline /
///    permissionPending / error`），并注明「03 号 §4.1 六态」——
///    但 03 号 §4.1 实际列的是下面这一组。
///    ⇒ 本实现**以 03 号 §4.1 为准**（它是被引用的原始出处，且 03 号 §4.1 自带 UI 铁律），
///    58 号 那组记在此处备查，两者的映射关系待 03 号 / 58 号 的所有者统一。
public enum ConnectionState: String, CaseIterable, Sendable, Codable {
    /// 未连接。
    case disconnected
    /// 连服务器中转。
    case connectingRemote
    /// 已连服务器（可收发）。
    case connectedRemote
    /// 探测 LAN 可达性（`ping`/`pong`）—— 静默，无提示。
    case lanProbing
    /// 已切到 LAN（低延迟）—— 静默，不打扰。
    case connectedLan
    /// 设备在线但功能不可用（降级）。
    case degraded

    /// 是否处于"可收发"状态。
    public var canSend: Bool {
        self == .connectedRemote || self == .connectedLan
    }

    /// 是否为**静默**状态（UI 不提示）。
    ///
    /// ⭐ `docs/spec/03` §4.1：`lanProbing` / `connectedLan` 均标注「无提示（静默，**不打扰**）」。
    public var isSilent: Bool {
        self == .lanProbing || self == .connectedLan
    }
}

/// 设备端状态快照。
///
/// ⛔ 纯数据模型，不含视觉决策。
///
/// ⚠️ **姿态是"乐观值"，不是设备真值**：
///    `docs/spec/03` §2.4 —— 固件**没有实现** `getAvatarPosture`(0x15)，
///    官方 App 的 3D 预览是「发出即乐观显示」。
///    `docs/spec/03` §2.4 裁决 ③：**接受乐观值**并明确文档化，
///    把"姿态真值"降级为"我命令它转到哪"。
///    ⇒ 文案不得把它写成"实时姿态"（`docs/spec/05` §3 裁决）。
public struct DeviceState: Equatable, Sendable {

    /// 连接状态。
    public var connection: ConnectionState

    /// 当前情绪（协议层的官方 6 情绪）。
    public var mood: Mood

    /// 在场 / 等待。
    public var presence: Presence

    /// 电量百分比（0...100）；未知时为 `nil`。
    public var batteryPercent: Int?

    /// 当前下发的目标姿态（**乐观值**）。
    public var targetMotion: MotionModel

    public init(connection: ConnectionState = .disconnected,
                mood: Mood = .neutral,
                presence: Presence = .deviceOffline,
                batteryPercent: Int? = nil,
                targetMotion: MotionModel = MotionModel()) {
        self.connection = connection
        self.mood = mood
        self.presence = presence
        self.batteryPercent = batteryPercent
        self.targetMotion = targetMotion
    }
}
