import ActivityKit
import Foundation
import StackChanShared

/// Live Activity 的启停与刷新。
///
/// ⚠️ **刷新链路铁线**（`docs/research/58-iOS端架构决策.md` §5）：
///    「状态变化 → `Task { }` 甩出去，**绝不在 `onChange` 闭包里同步调 ActivityKit**（会掉帧）」
///    ⇒ 调用方必须把本类型的方法放进 `Task { }` 里调。
///
/// ⚠️ **触感约束**：同一次状态变化 = 一次交互 = **最多 1 次触感**
///    （`docs/spec/02` §1 Q-9；`docs/research/58` §5）。
///
/// ⛔ 展开态内容、锁屏样式待用户拍板；本类只管生命周期。
///
/// TODO(pending design decision): Live Activity 的展示形态待拍板
public final class LiveActivityController {

    /// 当前活动（未启动时为 `nil`）。
    private var activity: Activity<StackChanAttributes>?

    public init() {}

    /// 启动一个 Live Activity。
    ///
    /// - Throws: ActivityKit 的 `Activity.request` 抛出的错误（重复启动等）。
    @discardableResult
    public func start(attributes: StackChanAttributes,
                      state: StackChanAttributes.ContentState) async throws -> Activity<StackChanAttributes> {
        let content = ActivityContent(state: state, staleDate: nil)
        let started = try Activity.request(attributes: attributes, content: content, pushType: nil)
        activity = started
        return started
    }

    /// 更新内容。
    public func update(_ state: StackChanAttributes.ContentState) async {
        await activity?.update(ActivityContent(state: state, staleDate: nil))
    }

    /// 结束活动。
    public func end(_ state: StackChanAttributes.ContentState) async {
        await activity?.end(ActivityContent(state: state, staleDate: nil), dismissalPolicy: .immediate)
    }

    /// 当前是否有活动在跑。
    public var isRunning: Bool { activity != nil }
}
