import Foundation

/// 在场 / 等待状态。
///
/// ⭐ 出处：`docs/spec/00-StackChan产品规格与技术规格.md` §2.1 元素 1
///    「小栈状态条 … 情绪（**图形优先，最多配 1 个词**）+ 在场/等待 + 电量」
///    `docs/spec/02-交付感与质感规范.md` §6 状态矩阵（「设备离线」「等待态（你不在）」）
///
/// ⛔ 纯语义状态，**不含视觉决策**（怎么显示是视觉层的事，且待拍板）。
public enum Presence: String, CaseIterable, Sendable, Codable {
    /// 在场（设备在线、App 活跃）。
    case present
    /// 等待你回来。
    case waiting
    /// 不在场（App 不在前台）。
    case away
    /// 设备离线。
    case deviceOffline
}
