import XCTest
@testable import CoreProtocol

/// 脸渲染**双模式**（镜像 / 风格化）单测。
///
/// ⭐ 规则来源：`docs/spec/06-表情参数模型.md` §9.2b（8 条约束）
final class FaceProjectionTests: XCTestCase {

    /// 一个带情绪的模型（Happy：左眼 72 / 1550，嘴 weight 40）。
    private func happyModel() -> AvatarModel {
        var m = AvatarModel()
        m.leftEye.weight = 72
        m.leftEye.rotation = 1550
        m.rightEye.weight = 72
        m.rightEye.rotation = -1550
        m.mouth.weight = 40
        return m
    }

    // MARK: - 约束 1：枚举与默认值

    func testExactlyTwoModesAndDefaultIsMirror() {
        // ⭐ 约束 1：只有 .mirror / .stylized，默认 .mirror
        XCTAssertEqual(FaceRenderMode.allCases.count, 2)
        XCTAssertTrue(FaceRenderMode.allCases.contains(.mirror))
        XCTAssertTrue(FaceRenderMode.allCases.contains(.stylized))
        XCTAssertEqual(FaceRenderMode.default, .mirror)
    }

    func testModeHasDisplayNameAndSummary() {
        for mode in FaceRenderMode.allCases {
            XCTAssertFalse(mode.displayName.isEmpty)
            XCTAssertFalse(mode.summary.isEmpty)
        }
    }

    // MARK: - 约束 3 / 4 / 5：模式分叉

    func testOnlyMirrorPromisesPixelPerfect() {
        // ⭐ 约束 3
        XCTAssertTrue(FaceProjection(mode: .mirror, model: happyModel()).promisesPixelPerfectMirror)
        XCTAssertFalse(FaceProjection(mode: .stylized, model: happyModel()).promisesPixelPerfectMirror)
    }

    func testOnlyStylizedAllowsAntialiasing() {
        // ⭐ 约束 3 的推论
        XCTAssertFalse(FaceProjection(mode: .mirror, model: happyModel()).allowsAntialiasing)
        XCTAssertTrue(FaceProjection(mode: .stylized, model: happyModel()).allowsAntialiasing)
    }

    func testOnlyStylizedFollowsThemePalette() {
        // ⭐ 约束 4：镜像模式的背景/前景必须是设备原色
        XCTAssertFalse(FaceProjection(mode: .mirror, model: happyModel()).followsThemePalette)
        XCTAssertTrue(FaceProjection(mode: .stylized, model: happyModel()).followsThemePalette)
    }

    func testMirrorModeForcesMouthToDefaultClosed() {
        // ⭐ 约束 5 + §5.1：固件 setEmotion 不碰嘴 ⇒ 设备永远闭嘴
        let proj = FaceProjection(mode: .mirror, model: happyModel())
        XCTAssertEqual(proj.model.mouth.weight, 0)
        XCTAssertEqual(proj.geometry.mouth.width, 90)
        XCTAssertEqual(proj.geometry.mouth.height, 6)
    }

    func testMirrorModeKeepsEyeParametersUntouched() {
        // ⭐ 表 A 是固件事实，镜像模式不得改动眼睛
        let proj = FaceProjection(mode: .mirror, model: happyModel())
        XCTAssertEqual(proj.model.leftEye.weight, 72)
        XCTAssertEqual(proj.model.leftEye.rotation, 1550)
        XCTAssertEqual(proj.model.rightEye.rotation, -1550)
    }

    func testStylizedModeKeepsMouthWeight() {
        let proj = FaceProjection(mode: .stylized, model: happyModel())
        XCTAssertEqual(proj.model.mouth.weight, 40)
        // 嘴高 = 6 + 40*(50-6)/100 = 6 + 17 = 23（整数截断）
        XCTAssertEqual(proj.geometry.mouth.height, 23)
        // 嘴宽 = 90 + 40*(60-90)/100 = 90 - 12 = 78
        XCTAssertEqual(proj.geometry.mouth.width, 78)
    }

    func testOnlyStylizedAllowsEmotionDrivenMouth() {
        XCTAssertFalse(FaceProjection(mode: .mirror, model: happyModel()).allowsEmotionDrivenMouth)
        XCTAssertTrue(FaceProjection(mode: .stylized, model: happyModel()).allowsEmotionDrivenMouth)
    }

    // MARK: - 约束 2：两种模式共用同一套几何函数

    func testBothModesUseSameGeometryEngine() {
        // ⭐ 约束 2：同一份表情（嘴归一化后）→ 两种模式的几何必须完全一致
        var normalized = happyModel()
        normalized.mouth.weight = 0
        let expected = FaceGeometryEngine.geometry(for: normalized)

        XCTAssertEqual(FaceProjection(mode: .mirror, model: happyModel()).geometry, expected)
        XCTAssertEqual(FaceProjection(mode: .stylized, model: normalized).geometry, expected)
    }

    // MARK: - 约束 7：切换模式不改情绪参数

    func testSwitchingModeDoesNotMutateSourceModel() {
        let source = happyModel()
        let proj = FaceProjection(mode: .mirror, model: source)
        _ = proj.switching(to: .stylized)
        // 源模型必须原封不动（用户的意图不变）
        XCTAssertEqual(source.mouth.weight, 40)
        XCTAssertEqual(source.leftEye.weight, 72)
    }

    func testSwitchingModePreservesEyeParametersAcrossBothDirections() {
        let proj = FaceProjection(mode: .mirror, model: happyModel())
        let toStylized = proj.switching(to: .stylized)
        XCTAssertEqual(toStylized.model.leftEye.weight, 72)
        XCTAssertEqual(toStylized.model.leftEye.rotation, 1550)

        let back = toStylized.switching(to: .mirror)
        XCTAssertEqual(back.model.leftEye.weight, 72)
        XCTAssertEqual(back.model.leftEye.rotation, 1550)
    }

    // MARK: - 约束 6：风格化必须保持动作语义

    func testSemanticFingerprintCapturesEyeAsymmetryAndMouthRatio() {
        var m = AvatarModel()
        m.leftEye.weight = 100
        m.rightEye.weight = 60
        m.mouth.weight = 50
        let fp = FaceSemanticGuard.fingerprint(of: m)
        XCTAssertEqual(fp.eyeAsymmetry, -40)
        XCTAssertEqual(fp.mouthToEyeRatio, 50.0 / 80.0, accuracy: 0.0001)
    }

    func testIdenticalFingerprintsProduceNoViolations() {
        let fp = FaceSemanticGuard.fingerprint(of: happyModel())
        XCTAssertTrue(FaceSemanticGuard.violations(before: fp, after: fp).isEmpty)
    }

    func testChangedEyeAsymmetryIsDetected() {
        var before = AvatarModel()
        before.leftEye.weight = 100
        before.rightEye.weight = 100
        var after = before
        after.rightEye.weight = 40   // 人为破坏左右差
        let v = FaceSemanticGuard.violations(
            before: FaceSemanticGuard.fingerprint(of: before),
            after: FaceSemanticGuard.fingerprint(of: after))
        XCTAssertEqual(v.count, 1)
        if case .eyeAsymmetryChanged = v[0] {} else { XCTFail("应报 eyeAsymmetryChanged，实际 \(v)") }
    }

    func testChangedMouthToEyeRatioIsDetected() {
        var before = AvatarModel()
        before.leftEye.weight = 100
        before.rightEye.weight = 100
        before.mouth.weight = 20
        var after = before
        after.mouth.weight = 90
        let v = FaceSemanticGuard.violations(
            before: FaceSemanticGuard.fingerprint(of: before),
            after: FaceSemanticGuard.fingerprint(of: after))
        XCTAssertEqual(v.count, 1)
        if case .mouthToEyeRatioChanged = v[0] {} else { XCTFail("应报 mouthToEyeRatioChanged，实际 \(v)") }
    }

    func testToleranceAllowsSmallDeviation() {
        var before = AvatarModel()
        before.leftEye.weight = 100
        before.rightEye.weight = 100
        before.mouth.weight = 20
        var after = before
        after.rightEye.weight = 98
        // 默认容差 0 ⇒ 违规
        XCTAssertFalse(FaceSemanticGuard.violations(
            before: FaceSemanticGuard.fingerprint(of: before),
            after: FaceSemanticGuard.fingerprint(of: after)).isEmpty)
        // 给 2 的容差 ⇒ 通过
        // ⚠️ **两个容差是独立的**：眼睛开合差变了 2，嘴眼相对关系也会**跟着**变
        //    （20/100 = 0.2 → 20/99 ≈ 0.20202，偏差 0.00202）。
        //    ⇒ 只给眼睛容差时，「嘴眼相对关系」这条不变量仍会报 —— 这是**预期行为**：
        //    风格化只改画法，嘴眼相对关系必须**单独**给容差才能放行。
        XCTAssertTrue(FaceSemanticGuard.violations(
            before: FaceSemanticGuard.fingerprint(of: before),
            after: FaceSemanticGuard.fingerprint(of: after),
            eyeAsymmetryTolerance: 2,
            mouthRatioTolerance: 0.01).isEmpty)
        // 只给眼睛容差 ⇒ 嘴眼相对关系这条**仍报**（证明上面的通过不是因为实现放水）
        XCTAssertEqual(FaceSemanticGuard.violations(
            before: FaceSemanticGuard.fingerprint(of: before),
            after: FaceSemanticGuard.fingerprint(of: after),
            eyeAsymmetryTolerance: 2).count, 1)
    }
}
