import Foundation

// ============================================================================
// FaceGeometry —— 设备端 320×240 表情渲染的**几何事实**在 Swift 里的移植。
//
// ⭐ 本文件是「App 是镜子」这条产品原则的**可执行载体**：
//    「设备是身体，App 是镜子」（`docs/research/58-iOS端架构决策.md` §4）
//
// ⚠️ **所有数值都有固件出处**（`docs/spec/06-表情参数模型.md` §6.2 渲染几何事实表）。
//    这里是**移植**，不是重新设计** —— 若发现固件行为与本文件不符，
//    以固件为准并**公开订正**本文件（不许悄悄改数值）。
//
// ⚠️ 本文件**不含任何视觉字面量**（颜色 / 圆角 / 时长 / 字号）：
//    几何是固件事实，视觉是设计决策，两者必须分开。
//    颜色等视觉参数走 `DesignSystem/`（门禁：`ios/tools/validate_project.py`）。
// ============================================================================

/// 设备端画布尺寸（像素）。固件面板就是 320×240，居中于屏幕。
///
/// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/default.cpp:13-15`
public struct FaceCanvas: Equatable, Sendable {
    /// 画布宽（像素）。
    public let width: Int
    /// 画布高（像素）。
    public let height: Int

    public init(width: Int = 320, height: Int = 240) {
        self.width = width
        self.height = height
    }

    /// 设备端标准画布（320×240）。
    public static let device = FaceCanvas(width: 320, height: 240)
}

/// 一个元素在画布上的**整数像素**几何。
///
/// ⭐ 全部来自 `docs/spec/06` §6.2：
///    - 眼位 / 嘴位：设备端固定基准 + 参数偏移
///    - 眼睛直径：`8 + (size + 100) * 24 / 200`（**整数截断**）
///    - 眼睑 y 偏移：`-(眼径 * weight / 100)`（向上为负）
///    - 嘴尺寸：宽 `90 + w*(60-90)/100`、高 `6 + w*(50-6)/100`、圆角 `0 + w*(16-0)/100`
public struct FaceElementGeometry: Equatable, Sendable {
    /// 元素中心 x（像素，画布坐标系）。
    public var centerX: Int
    /// 元素中心 y（像素，画布坐标系）。
    public var centerY: Int
    /// 宽（像素）。
    public var width: Int
    /// 高（像素）。
    public var height: Int
    /// 旋转角，单位 **0.1 度**（与固件同量纲）。
    public var rotationTenths: Int
    /// 眼睑/张嘴的下沉量（像素，向下为正）。眼睑的 `weight` 与嘴的 `weight` 语义不同，见 ``FaceGeometry``。
    public var lidOffsetY: Int
    /// 圆角半径（像素）。固件嘴是**填充圆角矩形**，不是描边路径。
    public var cornerRadius: Int

    public init(centerX: Int, centerY: Int, width: Int, height: Int,
                rotationTenths: Int = 0, lidOffsetY: Int = 0, cornerRadius: Int = 0) {
        self.centerX = centerX
        self.centerY = centerY
        self.width = width
        self.height = height
        self.rotationTenths = rotationTenths
        self.lidOffsetY = lidOffsetY
        self.cornerRadius = cornerRadius
    }
}

/// 一次渲染所需的**全部**几何。
public struct FaceGeometry: Equatable, Sendable {
    /// 左眼。
    public var leftEye: FaceElementGeometry
    /// 右眼。
    public var rightEye: FaceElementGeometry
    /// 嘴。
    public var mouth: FaceElementGeometry

    public init(leftEye: FaceElementGeometry, rightEye: FaceElementGeometry, mouth: FaceElementGeometry) {
        self.leftEye = leftEye
        self.rightEye = rightEye
        self.mouth = mouth
    }
}

// MARK: - 几何计算

/// 固件几何公式的 Swift 移植。
///
/// ⭐ 事实来源：`docs/spec/06-表情参数模型.md` §6.2（逐行带固件出处）。
///    本类型是**纯函数 + 纯值**，不依赖 SwiftUI ⇒ 可在 `swift test` 里直接单测。
public enum FaceGeometryEngine {

    // MARK: 基准常量（固件事实）

    /// 左眼基准中心（无偏移时）。
    public static let leftEyeBaseX = 90
    /// 眼睛基准中心 y。
    public static let eyeBaseY = 104
    /// 右眼基准中心 x。
    public static let rightEyeBaseX = 230
    /// 嘴基准中心 x。
    public static let mouthBaseX = 160
    /// 嘴基准中心 y。
    public static let mouthBaseY = 146
    /// 眼睛容器恒定尺寸。
    public static let eyeContainerSize = 32
    /// 位置偏移量程：±16 像素 ↔ ±100 参数单位。
    public static let positionRangePixels = 16
    /// 位置偏移量程：±100 参数单位。
    public static let positionRangeUnits = 100
    /// 旋转角量程：0 ~ 3600（0.1° 单位）。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/avatar/elements/element.h:43`
    ///    （`uitk::clamp(rotation, 0, 3600)`）
    public static let rotationRange = 0...3600

    // MARK: 换算

    /// 位置偏移（±100）→ 像素偏移（±16）。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/eyes.cpp:64-65`
    ///    （`mouth.cpp:42-43` 同）
    ///    `map_range(_position.x, -100, 100, -16, 16)`
    ///
    /// ⚠️ **必须逐字复刻 `map_range`，不能简化成 `units * 16 / 100`**：
    ///    固件的 `map_range(v, in_min, in_max, out_min, out_max)` 是
    ///    `out_min + ((v - in_min) * (out_max - out_min)) / (in_max - in_min)`
    ///    （`base.hpp:40-48`，**整数除法向零截断**）。
    ///    ⇒ `map_range(x, -100, 100, -16, 16)` = `-16 + (x + 100) * 32 / 200`，
    ///    这与 `x * 16 / 100` **在负数段差 1 像素**（例：`x = -1` ⇒ 固件 −1、简化式 0）。
    ///    ⇒ 差 1 像素就破了「逐像素一致」的镜子原则。
    ///    门禁：`tools/check_face_geometry.py` 逐点比对（−150..150）。
    ///
    /// ⚠️ **钳位发生在上游**：`Element::setPosition` 先把 `_position` 钳到 ±100
    ///    （`element.h:29`），`map_range` 本身**不钳位**（纯线性映射）。
    ///    ⇒ 本函数自己钳位，等价于固件的「先钳后映」。
    public static func positionOffsetPixels(_ units: Int) -> Int {
        let clamped = max(-positionRangeUnits, min(positionRangeUnits, units))
        // 逐字复刻 map_range(v, -100, 100, -16, 16)
        return -positionRangePixels
            + (clamped + positionRangeUnits) * (positionRangePixels * 2) / (positionRangeUnits * 2)
    }

    /// 旋转角钳位（0 ~ 3600）。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/avatar/elements/element.h:43`
    ///
    /// ⚠️ **负角会被钳成 0** —— 这就是 `docs/spec/06` §5.1 里
    ///    「Sad 的 `-400` 是视觉值，存储值被钳成 0」那条的成因。
    ///    ⇒ 我们下发时用 `3560` 表达 −40°（等价于 +3560°）。
    public static func clampRotation(_ rotation: Int) -> Int {
        max(rotationRange.lowerBound, min(rotationRange.upperBound, rotation))
    }

    /// 眼睛直径（像素）：`8 + (size + 100) * 24 / 200`。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/eyes.cpp:16,137`
    ///
    /// - `size = 0` → 直径 20 px
    /// - `size = -100` → 直径 8 px
    /// - `size = +100` → 直径 32 px
    public static func eyeDiameter(size: Int) -> Int {
        let clamped = max(-positionRangeUnits, min(positionRangeUnits, size))
        // 固件是 map_range(size, -100, 100, 8, 32) ⇒ 8 + (size+100)*24/200
        return 8 + (clamped + 100) * 24 / 200
    }

    /// 眼睑 y 偏移（像素）：`-(眼径 * weight / 100)`（**向上为负**）。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/eyes.cpp:75,77`
    ///    （`-map_range(_weight, 0, 100, 0, 眼径)`，再 `setY`）
    ///
    /// ⚠️ **极性容易写反**：固件眼睛 `weight` 越大 = 越睁开
    ///    （`weight = 100` 全睁，`weight = 35` 几乎闭；见 `docs/research/53` §2 情绪表）。
    ///    眼睑是**背景色方块**，盖在白色圆眼上；
    ///    offset = 0 时眼睑与眼白同心 ⇒ **完全盖住 = 闭眼**；
    ///    offset = −眼径 时眼睑整个移到眼睛上方 ⇒ **完全露出 = 全睁**。
    ///    ⇒ **weight 越大 ⇒ offset 越负 ⇒ 越睁开**。
    public static func eyelidOffsetY(eyeDiameter: Int, weight: Int) -> Int {
        let clamped = max(0, min(100, weight))
        return -(eyeDiameter * clamped / 100)
    }

    /// 嘴的尺寸（宽 / 高 / 圆角）。
    ///
    /// ⭐ 出处：`firmware/main/stackchan/avatar/skins/default/mouth.cpp:15-18,52-54`
    ///    - 宽 `90 + w*(60-90)/100`
    ///    - 高 `6 + w*(50-6)/100`
    ///    - 圆角 `0 + w*(16-0)/100`
    ///
    /// - `weight = 0` → 90×6，r=0（闭嘴细线）
    /// - `weight = 100` → 60×50，r=16（大开口）
    public static func mouthSize(weight: Int) -> (width: Int, height: Int, cornerRadius: Int) {
        let clamped = max(0, min(100, weight))
        let width = 90 + clamped * (60 - 90) / 100
        let height = 6 + clamped * (50 - 6) / 100
        let cornerRadius = 0 + clamped * (16 - 0) / 100
        return (width, height, cornerRadius)
    }

    // MARK: 组合

    /// 算一个眼睛的几何。
    ///
    /// - Parameters:
    ///   - baseX: 基准中心 x（左眼 90 / 右眼 230）
    ///   - x: 位置偏移参数（±100）
    ///   - y: 位置偏移参数（±100）
    ///   - rotation: 旋转角（0.1°）
    ///   - weight: 开合权重（0..100，越大越睁）
    ///   - size: 尺寸参数（±100）
    public static func eyeGeometry(baseX: Int, x: Int, y: Int,
                                   rotation: Int, weight: Int, size: Int) -> FaceElementGeometry {
        let diameter = eyeDiameter(size: size)
        return FaceElementGeometry(
            centerX: baseX + positionOffsetPixels(x),
            centerY: eyeBaseY + positionOffsetPixels(y),
            width: diameter,
            height: diameter,
            rotationTenths: rotation,
            lidOffsetY: eyelidOffsetY(eyeDiameter: diameter, weight: weight),
            cornerRadius: 0
        )
    }

    /// 算嘴的几何。
    public static func mouthGeometry(x: Int, y: Int, rotation: Int, weight: Int) -> FaceElementGeometry {
        let size = mouthSize(weight: weight)
        return FaceElementGeometry(
            centerX: mouthBaseX + positionOffsetPixels(x),
            centerY: mouthBaseY + positionOffsetPixels(y),
            width: size.width,
            height: size.height,
            rotationTenths: rotation,
            lidOffsetY: 0,
            cornerRadius: size.cornerRadius
        )
    }

    /// 从一个表情模型算出完整几何。
    ///
    /// - Parameter model: 3 元素 × 5 参数（`CoreProtocol.AvatarModel`）
    public static func geometry(for model: AvatarModel) -> FaceGeometry {
        FaceGeometry(
            leftEye: eyeGeometry(baseX: leftEyeBaseX,
                                 x: model.leftEye.x, y: model.leftEye.y,
                                 rotation: model.leftEye.rotation,
                                 weight: model.leftEye.weight,
                                 size: model.leftEye.size),
            rightEye: eyeGeometry(baseX: rightEyeBaseX,
                                  x: model.rightEye.x, y: model.rightEye.y,
                                  rotation: model.rightEye.rotation,
                                  weight: model.rightEye.weight,
                                  size: model.rightEye.size),
            mouth: mouthGeometry(x: model.mouth.x, y: model.mouth.y,
                                 rotation: model.mouth.rotation,
                                 weight: model.mouth.weight)
        )
    }
}
