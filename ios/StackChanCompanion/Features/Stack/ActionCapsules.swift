import SwiftUI

/// 动作胶囊组（**横向滑动，不是网格**）。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 9
///    「动作胶囊组 | 小栈页 | 横向滑动胶囊 | 8 个动作，**滑动而非网格**」
///    `docs/spec/02` §4.3（HIG 原文："place buttons so their centers are at least 60 points apart"）
///
/// ⚠️ **机制性硬线**：
///    - 用**横向 `ScrollView`**，⛔ 不用 Grid / LazyVGrid
///      （Floor F36「禁彩色圆形图标网格」+ `docs/spec/01` §3 元素 9 明写"滑动而非网格"）。
///    - 胶囊之间中心距 ≥ 60pt（HIG 原文，`docs/spec/02` §4.3）。
///    - 一次交互最多 1 次触感（`docs/spec/02` §1 Q-9）。
///
/// ⛔ 胶囊的数量、文案、样式待用户拍板。
struct ActionCapsules: View {

    /// 动作列表。
    let actions: [StackAction]

    /// 选中动作。
    var onSelect: (StackAction) -> Void

    var body: some View {
        // TODO(pending design decision): 动作胶囊的样式待拍板
        //   契约：docs/spec/01 §3 元素 9（横向滑动，不是网格）
        EmptyView()
    }
}
