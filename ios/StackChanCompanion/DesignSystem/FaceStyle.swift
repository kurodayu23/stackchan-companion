import SwiftUI
import CoreProtocol

// ============================================================================
// FaceStyle —— 脸的**风格化**样式参数（只有风格化模式用）。
//
// ⭐ 用户拍板（2026-10-25）：「两种都要：默认镜像 + 可切风格化」。
//    规格与 8 条约束见 `docs/spec/06-表情参数模型.md` §9.2b。
//
// ⛔ **为什么这个文件在 DesignSystem/ 而不是 Features/Companion/Face/**：
//    门禁 `ios/tools/validate_project.py` 规定「视觉字面量只允许出现在
//    `DesignSystem/`」。风格化模式的圆角比例、画布尺寸就是视觉参数
//    ⇒ 必须集中在这里，Features 里只引用 token。
//
// ⭐ **镜像模式不使用本文件的任何值** —— 镜像必须用设备原色 + 整数像素，
//    那不是设计决策，是固件事实（`docs/spec/06` §7.1）。
// ============================================================================

/// 脸的**设备端**配色（**固件事实**，不是设计决策）。
///
/// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/default.h:21-22`
///    - `primaryColor` = `lv_color_white()`（前景：眼白 / 嘴）
///    - `secondaryColor` = `lv_color_black()`（背景：面板 / 眼睑）
///
/// ⚠️ 这两个值**不在** `ThemePalette` 里 —— 镜像模式不随方案变。
public enum DeviceFaceColors {
    /// 设备端前景色（纯白）。
    public static let foreground: Color = .white
    /// 设备端背景色（纯黑）。
    public static let background: Color = .black
}

/// 脸的样式参数（**只给风格化模式**用）。
public enum FaceStyle {

    // MARK: - 画布

    /// 脸在页面里的默认显示尺寸（点）。
    ///
    /// ⭐ 依据：`docs/spec/07` §3.2「陪伴页里小栈脸占 **≥ 40% 视觉面积**」
    ///    —— 320×240 的设备比例（4:3），240 pt 宽在 iPhone 上约占 40% 屏宽。
    ///    ⚠️ 这是**估算起点**，最终值要用户过目原型后定。
    public static let defaultDisplayWidth: CGFloat = 240
    /// 默认显示高度（点）—— 与宽度保持设备 4:3 比例。
    public static let defaultDisplayHeight: CGFloat = 180

    /// 脸画布的默认显示尺寸。
    public static var defaultFaceSize: CGSize {
        CGSize(width: defaultDisplayWidth, height: defaultDisplayHeight)
    }

    /// 设备画布 → 目标尺寸的缩放系数（取短边，保持比例）。
    ///
    /// ⭐ 两种模式**必须用同一个缩放系数** —— 否则它们就不是同一张脸了
    ///    （`docs/spec/06` §7.3 红线：App 端不许另算一套比例）。
    public static func scaleFactor(from canvas: FaceCanvas, to size: CGSize) -> CGFloat {
        guard canvas.width > 0, canvas.height > 0 else { return 1 }
        return min(size.width / CGFloat(canvas.width), size.height / CGFloat(canvas.height))
    }

    // MARK: - 风格化几何修饰

    /// 风格化眼睑的圆角比例（相对眼径）。
    ///
    /// ⭐ 取 0.5 = 圆角矩形变成**胶囊**（宽 = 高的两倍？不 —— 宽高相等时
    ///    圆角 = 半径的一半 ⇒ 变成**圆**）。
    ///    ⇒ 风格化的眼睑是圆的，镜像是方的 —— 这正是两种模式的视觉差别。
    public static let eyelidCornerRatio: CGFloat = 0.5

    /// 风格化眼睛的描边宽度（点）。0 = 不描边。
    ///
    /// ⚠️ 默认不描边：描边会在小尺寸下糊成一团，且与固件的「纯色块」气质冲突。
    public static let eyeStrokeWidth: CGFloat = 0
}
