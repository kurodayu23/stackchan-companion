import SwiftUI
import CoreProtocol

/// 气泡旁的动作键（轻触浮现）。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 5
///    「气泡旁动作键 | 陪伴页 | 轻触浮现 | 插入一个动作（点头 / 看别处 / 前倾）」
///
/// ⚠️ **机制性硬线**：
///    - 一次交互**最多 1 次触感**（`docs/spec/02` §1 Q-9）。
///    - 动作是**目标角 + 时长**，**轨迹由服务端编译成 0x14 关键帧**，App 不本地算轨迹
///      （`docs/research/58-iOS端架构决策.md` §8 预设项 6）。
///    - 表情下发受 **< 2000 ms** 保活约束（`docs/research/53` §4.3）。
///
/// ⛔ 出现方式、形状、数量、样式待拍板。
struct ActionKeys: View {

    /// 动作列表。
    let actions: [StackAction]

    /// 选中动作。
    var onSelect: (StackAction) -> Void

    var body: some View {
        // TODO(pending design decision): 动作键的视觉与浮现动效待拍板
        //   契约：docs/spec/01 §3 元素 5；一次交互 ≤1 次触感（Q-9）
        EmptyView()
    }
}

/// App 侧可下发的一个动作。
///
/// ⭐ 语义表出处：`docs/spec/03` §5 预设项 6「8 个动作胶囊 → `MotionData(yaw, pitch)` + 时长」
///    —— 具体动作清单与命名待用户拍板，此处只保留数据结构。
struct StackAction: Identifiable, Equatable, Sendable {
    /// 稳定标识。
    public let id: String
    /// 展示名（占位，待拍板）。
    public let title: String
    /// 目标姿态（**乐观值**：我们命令它转到哪，不是它现在长什么样）。
    public let target: MotionModel
    /// 期望持续时长（毫秒）。
    public let durationMs: Int

    public init(id: String, title: String, target: MotionModel, durationMs: Int) {
        self.id = id
        self.title = title
        self.target = target
        self.durationMs = durationMs
    }
}
