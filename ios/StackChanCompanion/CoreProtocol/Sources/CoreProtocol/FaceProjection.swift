import Foundation

// ============================================================================
// FaceProjection —— 脸渲染的**双模式**（镜像 / 风格化）。
//
// ⭐ 2026-10-25 用户拍板：「两种都要：默认镜像 + 可切风格化」。
//    规格与 8 条约束见 `docs/spec/06-表情参数模型.md` §9.2b。
//
// 本文件只管**投影语义**（模式 → 该模式下的参数与约束），
// 纯值类型、不依赖 SwiftUI ⇒ 可在 `swift test` 里直接单测。
// 实际绘制在 `Features/Companion/Face/`（SwiftUI 层）。
//
// ⚠️ **模式的区别是「怎么画」，不是「画什么」**：
//    - 切换模式**不得**改变当前情绪参数（约束 7）。
//    - 两种模式**必须复用同一套几何函数**（约束 2，§7.3 红线）。
// ============================================================================

/// 脸的渲染模式。
///
/// ⭐ 用户拍板（2026-10-25）：默认 `.mirror`，可切 `.stylized`。
public enum FaceRenderMode: String, CaseIterable, Sendable, Hashable {
    /// **镜像模式**（默认）：App 端严格复刻设备屏幕。
    ///
    /// - 逐像素一致是硬要求 ⇒ 整数像素、无矢量抗锯齿；
    /// - 背景/前景必须是设备原色（纯黑 / 纯白）；
    /// - 嘴**恒为规范默认值**（固件 `setEmotion` 不碰嘴）。
    case mirror

    /// **风格化模式**：保持动作语义，只改画法（更圆润 / 渐变 / 描边）。
    case stylized

    /// 默认模式（用户拍板：默认镜像）。
    public static let `default`: FaceRenderMode = .mirror

    /// 给用户看的名字。
    public var displayName: String {
        switch self {
        case .mirror:   return "镜像"
        case .stylized: return "风格化"
        }
    }

    /// 给用户看的说明（一句话）。
    public var summary: String {
        switch self {
        case .mirror:   return "和设备屏幕一模一样"
        case .stylized: return "同样的表情，更柔和的画法"
        }
    }
}

/// 风格化模式的**语义不变量**检查结果。
///
/// ⭐ 约束 6：风格化模式必须保持**动作语义** ——
///    左右眼开合差值、嘴张开度与眼开合的**相对关系**必须保持。
public enum FaceSemanticsViolation: Equatable, Sendable {
    /// 左右眼开合差值被改变了。
    case eyeAsymmetryChanged(before: Int, after: Int)
    /// 嘴张开度与眼开合的相对关系被改变了。
    case mouthToEyeRatioChanged(before: Double, after: Double)
}

/// 风格化模式的语义检查器。
///
/// ⭐ 为什么需要它：风格化模式「只改画法」这句话**必须可验证**，
///    否则「风格化」很容易变成「顺手把表情也改了」。
public enum FaceSemanticGuard {

    /// 语义指纹：把一个表情模型压缩成「可比较的语义」。
    ///
    /// ⚠️ 只取**语义相关**的量（开合 / 嘴张），**不含**位置 / 旋转 / 尺寸
    ///    —— 风格化允许改画法，但不允许改「开合差」与「嘴眼相对关系」。
    public struct Fingerprint: Equatable, Sendable {
        /// 左眼开合权重。
        public let leftEyeWeight: Int
        /// 右眼开合权重。
        public let rightEyeWeight: Int
        /// 嘴张开权重。
        public let mouthWeight: Int

        public init(leftEyeWeight: Int, rightEyeWeight: Int, mouthWeight: Int) {
            self.leftEyeWeight = leftEyeWeight
            self.rightEyeWeight = rightEyeWeight
            self.mouthWeight = mouthWeight
        }

        /// 左右眼开合差值（右 − 左）。
        public var eyeAsymmetry: Int { rightEyeWeight - leftEyeWeight }

        /// 嘴张开度 ÷ 平均眼开合度（分母为 0 时取 0）。
        public var mouthToEyeRatio: Double {
            let avg = (Double(leftEyeWeight) + Double(rightEyeWeight)) / 2.0
            guard avg != 0 else { return 0 }
            return Double(mouthWeight) / avg
        }
    }

    /// 取一个表情模型的语义指纹。
    public static func fingerprint(of model: AvatarModel) -> Fingerprint {
        Fingerprint(leftEyeWeight: model.leftEye.weight,
                    rightEyeWeight: model.rightEye.weight,
                    mouthWeight: model.mouth.weight)
    }

    /// 比较两个指纹，返回违反的不变量（空数组 = 语义保持）。
    ///
    /// - Parameters:
    ///   - before: 风格化**前**的指纹
    ///   - after: 风格化**后**的指纹
    ///   - eyeAsymmetryTolerance: 左右眼开合差值的允许偏差（默认 0 = 完全一致）
    ///   - mouthRatioTolerance: 嘴眼相对关系的允许偏差（默认 0.0 = 完全一致）
    public static func violations(before: Fingerprint, after: Fingerprint,
                                  eyeAsymmetryTolerance: Int = 0,
                                  mouthRatioTolerance: Double = 0.0) -> [FaceSemanticsViolation] {
        var out: [FaceSemanticsViolation] = []

        if abs(after.eyeAsymmetry - before.eyeAsymmetry) > eyeAsymmetryTolerance {
            out.append(.eyeAsymmetryChanged(before: before.eyeAsymmetry,
                                             after: after.eyeAsymmetry))
        }
        if abs(after.mouthToEyeRatio - before.mouthToEyeRatio) > mouthRatioTolerance {
            out.append(.mouthToEyeRatioChanged(before: before.mouthToEyeRatio,
                                               after: after.mouthToEyeRatio))
        }
        return out
    }
}

/// 渲染投影：把「表情模型 + 模式」变成「该模式下要画的东西」。
///
/// ⭐ 这是模式分叉的**唯一决策点** —— SwiftUI 层只按这里的输出画，
///    不自己判断模式。
public struct FaceProjection: Equatable, Sendable {

    /// 渲染模式。
    public let mode: FaceRenderMode

    /// 实际用于渲染的表情模型。
    ///
    /// ⚠️ **镜像模式下这个值可能与输入不同**：固件的 `setEmotion` 不碰嘴
    ///    （`docs/spec/06` §5.1）⇒ 设备永远不会显示情绪化的嘴
    ///    ⇒ 镜像模式必须照抄这个事实，嘴恒为 `weight = 0`（约束 5）。
    public let model: AvatarModel

    /// 该模式下的几何（**两种模式共用同一套几何函数**，约束 2）。
    public let geometry: FaceGeometry

    /// 语义指纹（用于风格化模式的守卫检查）。
    public let fingerprint: FaceSemanticGuard.Fingerprint

    /// 该模式是否承诺「逐像素一致」。
    ///
    /// ⭐ 约束 3：只有镜像模式承诺。风格化模式不承诺。
    public var promisesPixelPerfectMirror: Bool { mode == .mirror }

    /// 该模式是否允许矢量抗锯齿 / 渐变等软渲染。
    public var allowsAntialiasing: Bool { mode == .stylized }

    /// 该模式是否允许随方案配色。
    ///
    /// ⭐ 约束 4：镜像模式的背景/前景必须是设备原色 ⇒ 不读 `ThemePalette` 的脸区色。
    public var followsThemePalette: Bool { mode == .stylized }

    /// 该模式是否允许随情绪改变嘴的张开度。
    ///
    /// ⭐ 约束 5：镜像模式下嘴恒为默认值。
    public var allowsEmotionDrivenMouth: Bool { mode == .stylized }

    // MARK: - 构造

    /// 造一个投影。
    ///
    /// - Parameters:
    ///   - mode: 渲染模式
    ///   - model: 原始表情模型
    public init(mode: FaceRenderMode, model: AvatarModel) {
        self.mode = mode
        // 镜像模式：嘴必须回到规范默认值（weight = 0，闭嘴）
        self.model = mode == .mirror ? FaceProjection.normalizedForMirror(model) : model
        self.geometry = FaceGeometryEngine.geometry(for: self.model)
        self.fingerprint = FaceSemanticGuard.fingerprint(of: self.model)
    }

    /// 镜像模式下的模型规范化：**嘴回到规范默认值**，其余原样保留。
    ///
    /// ⭐ 依据：`docs/spec/06` §5.1 —— 固件 `DefaultMouth` **未覆写** `setEmotion`
    ///    （基类是空实现）⇒ **固件情绪对嘴零影响**。
    ///
    /// ⚠️ 眼睛**不动** —— 表 A 的 6 组 weight/rotation 是固件事实，必须原样下发。
    public static func normalizedForMirror(_ model: AvatarModel) -> AvatarModel {
        var out = model
        out.mouth.weight = 0
        return out
    }

    // MARK: - 模式切换

    /// 切换模式。
    ///
    /// ⚠️ **约束 7：切换模式不得改变当前情绪参数。**
    ///    本方法只在**投影层**做模式特有的规范化（镜像模式的嘴归零），
    ///    **不改调用方持有的表情模型** —— 调用方的模型始终是「用户意图」。
    ///
    /// - Parameter mode: 目标模式
    /// - Returns: 新模式的投影
    public func switching(to mode: FaceRenderMode) -> FaceProjection {
        FaceProjection(mode: mode, model: model)
    }
}
