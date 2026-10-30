import SwiftUI
import CoreProtocol

/// 3D 姿态预览的**占位实现**。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 6
///    「3D 姿态预览 | 小栈页 | ≈180 px 3D | **拖动即控头部**（护城河体验的入口）」
///
/// ⭐ **实现约束（机制性，可直接照做）**：
///    - 表情必须**参数化绘制**（SwiftUI `Canvas` 画 3 元素 × 5 参数），
///      **不是贴一张表情图**——设备端表情是连续参数，App 端要能画任意参数
///      （`docs/research/58-iOS端架构决策.md` §4.2 App 轨、§4.4「复用设备端同一套 5 参数语义」）。
///    - x/y 换算用协议层的 `AvatarCoordinate`（JSON ±100 ↔ 像素 ±16，系数 6.25，
///      `docs/research/53` §3.2）。
///    - 眼睛 weight **越大越睁开**、嘴 weight 越大越张开（`WeightPolarity`）。
///    - 显示的是**乐观值**（我们命令它转到哪），**不得**写成"实时姿态"
///      （`docs/spec/03` §2.4 裁决 ③；`docs/spec/05` §3 裁决）。
///    - 屏幕唯一会动的东西是**小栈的脸**（`DESIGN.md` §0），单屏持续动效 ≤ 1 处。
///
/// ⛔ 脸的具体画法（眼睛形状、线条粗细、构图比例）待用户拍板。
struct PosturePreview: View {

    /// 当前目标姿态。
    let motion: MotionModel

    /// 当前表情参数。
    let avatar: AvatarModel

    var body: some View {
        // TODO(pending design decision): 姿态预览的画法与构图待拍板
        //   实现约束：Canvas 参数化绘制 + AvatarCoordinate 单位换算（见文件头）
        EmptyView()
    }
}
