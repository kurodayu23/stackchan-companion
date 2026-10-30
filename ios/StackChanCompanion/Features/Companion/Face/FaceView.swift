import SwiftUI

// ============================================================================
// FaceView —— 小栈的脸（**双模式**：镜像 / 风格化）。
//
// ⭐ 用户拍板（2026-10-25）：「两种都要：默认镜像 + 可切风格化」。
//    规格与 8 条约束见 `docs/spec/06-表情参数模型.md` §9.2b。
//
// ⛔ **本文件不含任何视觉字面量**（颜色 / 圆角 / 时长 / 字号）：
//    - 几何 → `CoreProtocol.FaceGeometry`（固件事实）
//    - 模式语义 → `CoreProtocol.FaceProjection`
//    - 颜色 / 圆角 / 尺寸 → `DesignSystem/`（门禁：`ios/tools/validate_project.py`）
//
// ⭐ 两种模式的**唯一差别是画法**，不是画什么：
//    - 镜像：逐像素复刻设备屏幕（整数像素、无抗锯齿、设备原色）
//    - 风格化：同样的几何，用更柔和的画法（圆角睑 / 方案配色）
// ============================================================================

/// 小栈的脸。
///
/// ⭐ 用法：
/// ```swift
/// FaceView(
///     model: currentAvatarModel,
///     mode: .mirror,                 // 或 .stylized
///     theme: resolvedTheme
/// )
/// ```
struct FaceView: View {

    /// 表情模型（3 元素 × 5 参数）。
    let model: AvatarModel

    /// 渲染模式（默认镜像）。
    var mode: FaceRenderMode = .default

    /// 当前主题（**只在风格化模式生效**；镜像模式必须用设备原色）。
    var theme: ResolvedTheme

    /// 画布在视图中的尺寸（点）。几何按设备 320×240 算好后整体缩放到这里。
    var displaySize: CGSize = FaceStyle.defaultFaceSize

    /// 是否降低动效（系统辅助设置）。
    var reduceMotion: Bool = false

    private var projection: FaceProjection {
        FaceProjection(mode: mode, model: model)
    }

    var body: some View {
        switch mode {
        case .mirror:
            MirrorFaceCanvas(projection: projection, displaySize: displaySize)
        case .stylized:
            StylizedFaceCanvas(projection: projection,
                               displaySize: displaySize,
                               theme: theme,
                               reduceMotion: reduceMotion)
        }
    }
}

// MARK: - 镜像模式

/// **镜像**渲染器：逐像素复刻设备屏幕。
///
/// ⭐ 约束 3 / 4 / 5（`docs/spec/06` §9.2b）：
/// - **逐像素一致** ⇒ 必须整数像素、**无矢量抗锯齿**；
/// - 背景/前景必须是**设备原色**（纯黑 / 纯白），不随方案变；
/// - 嘴**恒为规范默认值**（固件 `setEmotion` 不碰嘴）——已由 `FaceProjection` 保证。
private struct MirrorFaceCanvas: View {

    let projection: FaceProjection
    let displaySize: CGSize

    var body: some View {
        Canvas { context, size in
            let scale = FaceStyle.scaleFactor(from: FaceCanvas.device, to: size)
            let geo = projection.geometry

            // 背景：设备原色（不是方案色）
            context.fill(Path(CGRect(origin: .zero, size: size)),
                         with: .color(DeviceFaceColors.background))

            // 左眼 / 右眼：白色圆 + 黑色方块眼睑（眼睑压在上面）
            drawEye(context: &context, geo: geo.leftEye, scale: scale)
            drawEye(context: &context, geo: geo.rightEye, scale: scale)

            // 嘴：填充圆角矩形
            drawMouth(context: &context, geo: geo.mouth, scale: scale)
        }
        .drawingGroup(opaque: true, colorMode: .linear)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("小栈的脸"))
    }

    /// 画一只眼：白色圆（眼白）+ 黑色方块（眼睑）。
    ///
    /// ⭐ 层级出处：`docs/spec/06` §6.1 —— 眼白先建、眼睑后建 ⇒ **眼睑压在上面**。
    ///
    /// ⭐ 旋转出处：`firmware/main/stackchan/avatar/skins/default/eyes.cpp:80-85`
    ///    —— 固件把 rotation 施加在 **eye 的容器**上（`_container->setRotation`），
    ///    容器里同时装着眼白与眼睑 ⇒ **两者一起转**。
    ///    容器 pivot = 容器中心（`eyes.cpp:29` `setTransformPivot(16,16)`）= 眼睛中心。
    ///    所以这里：先在**容器坐标系**里摆眼白与眼睑，再整体绕眼睛中心旋转。
    ///
    /// ⚠️ **固件旋转值可能为负**（Sad = −400 = −40°），但协议下发的值是
    ///    `3600 + θ`（0…3600，见 `AvatarGeometry.wireRotation`）。
    ///    两者渲染结果等价（+320° ≡ −40°），所以这里直接用下发值除以 10 取度。
    private func drawEye(context: inout GraphicsContext,
                         geo: FaceElementGeometry,
                         scale: CGFloat) {
        let center = CGPoint(x: CGFloat(geo.centerX) * scale,
                             y: CGFloat(geo.centerY) * scale)
        let diameter = CGFloat(geo.width) * scale
        let angle = Double(geo.rotationTenths) / 10.0

        // 绕眼睛中心旋转（固件容器 pivot = 容器中心）
        context.translateBy(x: center.x, y: center.y)
        context.rotate(by: .degrees(angle))
        context.translateBy(x: -center.x, y: -center.y)

        // 眼白：圆（LV_RADIUS_CIRCLE）
        let eyeRect = CGRect(x: center.x - diameter / 2,
                             y: center.y - diameter / 2,
                             width: diameter, height: diameter)
        context.fill(Path(ellipseIn: eyeRect),
                     with: .color(DeviceFaceColors.foreground))

        // 眼睑：正方形（radius 0），盖在圆上
        let lidCenterY = center.y + CGFloat(geo.lidOffsetY) * scale
        let lidRect = CGRect(x: center.x - diameter / 2,
                             y: lidCenterY - diameter / 2,
                             width: diameter, height: diameter)
        context.fill(Path(lidRect), with: .color(DeviceFaceColors.background))
    }

    /// 画嘴：填充圆角矩形。
    ///
    /// ⭐ 出处：`docs/spec/06` §6.2（`mouth.cpp:23-26,56-57`）
    private func drawMouth(context: inout GraphicsContext,
                           geo: FaceElementGeometry,
                           scale: CGFloat) {
        let center = CGPoint(x: CGFloat(geo.centerX) * scale,
                             y: CGFloat(geo.centerY) * scale)
        let width = CGFloat(geo.width) * scale
        let height = CGFloat(geo.height) * scale
        let rect = CGRect(x: center.x - width / 2,
                          y: center.y - height / 2,
                          width: width, height: height)
        let path = Path(roundedRect: rect,
                        cornerRadius: CGFloat(geo.cornerRadius) * scale,
                        style: .continuous)
        context.fill(path, with: .color(DeviceFaceColors.foreground))
    }
}

// MARK: - 风格化模式

/// **风格化**渲染器：同样的几何，更柔和的画法。
///
/// ⭐ 约束 6：必须保持**动作语义**（左右眼开合差值、嘴眼相对关系）——
///    几何来自同一个 `FaceGeometry`，所以语义天然保持；
///    `FaceSemanticGuard` 提供可验证的指纹检查。
///
/// ⭐ 视觉参数一律来自 `DesignSystem/`（门禁强制）。
private struct StylizedFaceCanvas: View {

    let projection: FaceProjection
    let displaySize: CGSize
    let theme: ResolvedTheme
    let reduceMotion: Bool

    var body: some View {
        Canvas { context, size in
            let scale = FaceStyle.scaleFactor(from: FaceCanvas.device, to: size)
            let geo = projection.geometry

            // 背景：方案色（风格化模式才跟随主题）
            context.fill(Path(CGRect(origin: .zero, size: size)),
                         with: .color(theme.color(for: .canvas)))

            let ink = theme.color(for: .textPrimary)

            drawEye(context: &context, geo: geo.leftEye, scale: scale, ink: ink)
            drawEye(context: &context, geo: geo.rightEye, scale: scale, ink: ink)
            drawMouth(context: &context, geo: geo.mouth, scale: scale, ink: ink)
        }
        .drawingGroup(opaque: true, colorMode: .linear)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("小栈的脸"))
    }

    /// 风格化的眼：柔化的圆 + 圆角睑（**不用硬方块**）。
    ///
    /// ⚠️ 语义保持：开合度仍由 `lidOffsetY` 决定，只改**画法**。
    ///
    /// ⭐ 旋转与镜像模式**同口径**：固件把 rotation 施加在装着眼白与眼睑的**容器**上
    ///    （`eyes.cpp:80-85`），容器 pivot = 容器中心 = 眼睛中心
    ///    ⇒ 两者一起转。这里同样先摆好再整体绕眼睛中心旋转。
    private func drawEye(context: inout GraphicsContext,
                         geo: FaceElementGeometry,
                         scale: CGFloat,
                         ink: Color) {
        let center = CGPoint(x: CGFloat(geo.centerX) * scale,
                             y: CGFloat(geo.centerY) * scale)
        let diameter = CGFloat(geo.width) * scale
        let angle = Double(geo.rotationTenths) / 10.0

        context.translateBy(x: center.x, y: center.y)
        context.rotate(by: .degrees(angle))
        context.translateBy(x: -center.x, y: -center.y)

        // 眼白：柔和的椭圆
        let eyeRect = CGRect(x: center.x - diameter / 2,
                             y: center.y - diameter / 2,
                             width: diameter, height: diameter)
        context.fill(Path(ellipseIn: eyeRect), with: .color(ink))

        // 眼睑：风格化用**圆角矩形**而不是硬方块（圆角来自 token）
        let lidCenterY = center.y + CGFloat(geo.lidOffsetY) * scale
        let lidRect = CGRect(x: center.x - diameter / 2,
                             y: lidCenterY - diameter / 2,
                             width: diameter, height: diameter)
        let lidPath = Path(roundedRect: lidRect,
                           cornerRadius: diameter * FaceStyle.eyelidCornerRatio,
                           style: .continuous)
        context.fill(lidPath, with: .color(theme.color(for: .canvas)))
    }

    /// 风格化的嘴：圆角矩形（圆角来自几何，可更柔）。
    private func drawMouth(context: inout GraphicsContext,
                           geo: FaceElementGeometry,
                           scale: CGFloat,
                           ink: Color) {
        let center = CGPoint(x: CGFloat(geo.centerX) * scale,
                             y: CGFloat(geo.centerY) * scale)
        let width = CGFloat(geo.width) * scale
        let height = CGFloat(geo.height) * scale
        let rect = CGRect(x: center.x - width / 2,
                          y: center.y - height / 2,
                          width: width, height: height)
        let path = Path(roundedRect: rect,
                        cornerRadius: CGFloat(geo.cornerRadius) * scale,
                        style: .continuous)
        context.fill(path, with: .color(ink))
    }
}
