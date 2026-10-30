import SwiftUI
import CoreProtocol

/// 姿态数值读数（一行）。
///
/// ⭐ 契约出处：`docs/spec/01` §3 元素 7
///    「姿态数值 | 小栈页 | 一行等宽数字 | `左右 −12° · 俯仰 6°`」
///
/// ⚠️ **机制性硬线**：
///    - 数字必须**等宽**（`.monospacedDigit()`），避免数值跳动时布局抖
///      （`docs/spec/02` §2.2）。
///    - 角度显示单位是**度**（协议层是 0.1 度），换算用 `ServoLimit.degrees(_:)`。
///    - ⚠️ **不得编造指标**（Floor F2）：读数是"我命令它转到哪"，
///      **不是**设备实测姿态（固件未实现 0x15，`docs/spec/03` §2.4）。
///
/// ⛔ 展示格式（几项、单位写法、排版）待用户拍板。
struct PostureReadout: View {

    /// 当前目标姿态。
    let motion: MotionModel

    var body: some View {
        // TODO(pending design decision): 姿态读数的展示格式与排版待拍板
        //   契约：docs/spec/01 §3 元素 7；等宽数字；不得编造指标（F2）
        EmptyView()
    }
}
