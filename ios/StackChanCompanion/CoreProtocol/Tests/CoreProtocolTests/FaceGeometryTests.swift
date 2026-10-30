import XCTest
@testable import CoreProtocol

/// 脸渲染器（几何 + 双模式）单测。
///
/// ⭐ 规则来源：`docs/spec/06-表情参数模型.md` §6.2（几何事实）、§9.2b（8 条约束）
final class FaceGeometryTests: XCTestCase {

    // MARK: - 几何公式（固件事实）

    func testPositionOffsetIsClampedToPlusMinus16Pixels() {
        // ±100 参数 ↔ ±16 像素
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(0), 0)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(100), 16)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(-100), -16)
        // 超出量程要被钳位（固件 map_range 会钳）
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(200), 16)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(-200), -16)
    }

    func testEyeDiameterFollowsFirmwareFormula() {
        // 8 + (size + 100) * 24 / 200
        XCTAssertEqual(FaceGeometryEngine.eyeDiameter(size: 0), 20)
        XCTAssertEqual(FaceGeometryEngine.eyeDiameter(size: -100), 8)
        XCTAssertEqual(FaceGeometryEngine.eyeDiameter(size: 100), 32)
        // 整数截断：size = -50 ⇒ 8 + 50*24/200 = 8 + 6 = 14
        XCTAssertEqual(FaceGeometryEngine.eyeDiameter(size: -50), 14)
    }

    func testEyelidOffsetIsNegativeAndScalesWithWeight() {
        // -(眼径 * weight / 100)，向上为负
        let closed = FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 100)
        XCTAssertEqual(closed, -20)
        let open = FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 0)
        XCTAssertEqual(open, 0)
        // 眨眼时固件写的是 weight = 25（不是 0）⇒ 眼睑只压下 25%
        XCTAssertEqual(FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 25), -5)
    }

    func testEyelidOffsetPolarityIsNotInverted() {
        // ⭐ weight 越大 = 越睁开 ⇒ 眼睑越往上（offset 越负）
        //    固件 eyes.cpp:75 是 `-map_range(weight, 0, 100, 0, 眼径)`，
        //    而眼睑是背景色方块：offset=0 ⇒ 与眼白同心 ⇒ 完全盖住 = 闭眼；
        //    offset=−眼径 ⇒ 移到眼睛上方 ⇒ 完全露出 = 全睁。
        let heavy = FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 100)
        let light = FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 25)
        XCTAssertLessThan(heavy, light, "weight 越大眼睑越靠上，不能写反")
        // 全睁时眼睑完全移出眼睛范围
        XCTAssertEqual(heavy, -20)
        // 闭眼时眼睑与眼白同心
        XCTAssertEqual(FaceGeometryEngine.eyelidOffsetY(eyeDiameter: 20, weight: 0), 0)
    }

    func testPositionOffsetMatchesFirmwareMapRangeNotSimplifiedFormula() {
        // ⭐ 固件是 map_range(x, -100, 100, -16, 16) = -16 + (x+100)*32/200，
        //    **不是** x*16/100 —— 后者在负数段差 1 像素，会破「逐像素一致」。
        //    例：x = -1 ⇒ 固件 -1，简化式 0。
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(-1), -1)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(1), 0)
        // 端点必须精确
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(-100), -16)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(100), 16)
        XCTAssertEqual(FaceGeometryEngine.positionOffsetPixels(0), 0)
    }

    func testMouthSizeFollowsFirmwareFormula() {
        let closed = FaceGeometryEngine.mouthSize(weight: 0)
        XCTAssertEqual(closed.width, 90)
        XCTAssertEqual(closed.height, 6)
        XCTAssertEqual(closed.cornerRadius, 0)

        let wide = FaceGeometryEngine.mouthSize(weight: 100)
        XCTAssertEqual(wide.width, 60)
        XCTAssertEqual(wide.height, 50)
        XCTAssertEqual(wide.cornerRadius, 16)
    }

    func testBasePositionsMatchFirmware() {
        // ⭐ docs/spec/06 §6.2：左眼 (90,104)、右眼 (230,104)、嘴 (160,146)
        let model = AvatarModel()
        let geo = FaceGeometryEngine.geometry(for: model)
        XCTAssertEqual(geo.leftEye.centerX, 90)
        XCTAssertEqual(geo.leftEye.centerY, 104)
        XCTAssertEqual(geo.rightEye.centerX, 230)
        XCTAssertEqual(geo.rightEye.centerY, 104)
        XCTAssertEqual(geo.mouth.centerX, 160)
        XCTAssertEqual(geo.mouth.centerY, 146)
    }

    func testGeometryAppliesPositionOffsets() {
        var model = AvatarModel()
        model.leftEye.x = 100     // 满量程右移
        model.leftEye.y = -100    // 满量程上移
        let geo = FaceGeometryEngine.geometry(for: model)
        XCTAssertEqual(geo.leftEye.centerX, 90 + 16)
        XCTAssertEqual(geo.leftEye.centerY, 104 - 16)
    }

    func testMouthWeightDrivesMouthGeometry() {
        var model = AvatarModel()
        model.mouth.weight = 100
        let geo = FaceGeometryEngine.geometry(for: model)
        XCTAssertEqual(geo.mouth.width, 60)
        XCTAssertEqual(geo.mouth.height, 50)
        XCTAssertEqual(geo.mouth.cornerRadius, 16)
    }

    // MARK: - 旋转（固件事实：eyes.cpp:80-85, 93-98, 103-122）

    func testMoodTableMatchesFirmwareEmotionTable() {
        // ⭐ 固件 `apply_style(weight, rotation)` 的 6 组值
        //    （`firmware/main/stackchan/avatar/skins/default/eyes.cpp:103-122`）
        let expected: [(Mood, Int, Int)] = [
            (.neutral, 100, 0),
            (.happy, 72, 1550),
            (.angry, 70, 450),
            (.sad, 70, -400),
            (.doubt, 75, 0),
            (.sleepy, 35, -50),
        ]
        for (mood, weight, rotation) in expected {
            XCTAssertEqual(mood.eyeWeight, weight, "\(mood) weight 与固件不一致")
            XCTAssertEqual(mood.leftEyeRotation, rotation, "\(mood) 左眼 rotation 与固件不一致")
        }
    }

    func testRightEyeRotationIsMirroredFromLeft() {
        // ⭐ 固件 `apply_style` 里右眼是 `setRotation(-rotation)`
        //    （`eyes.cpp:93-98`）⇒ 左右眼镜像。
        for mood in Mood.allCases {
            XCTAssertEqual(mood.rightEyeRotation, -mood.leftEyeRotation,
                           "\(mood) 右眼旋转必须是左眼取反")
        }
        XCTAssertEqual(Mood.happy.rightEyeRotation, -1550)
        XCTAssertEqual(Mood.sad.rightEyeRotation, 400)
    }

    func testWireRotationConvertsNegativeAnglesToPositiveEquivalents() {
        // ⭐ 协议下发值必须落在 0…3600（固件 `Element::setRotation` 钳位区间）
        //    负角用 `3600 + θ` 表达（`AvatarGeometry.wireRotation`）。
        XCTAssertEqual(AvatarGeometry.wireRotation(0), 0)
        XCTAssertEqual(AvatarGeometry.wireRotation(1550), 1550)
        XCTAssertEqual(AvatarGeometry.wireRotation(-400), 3200)   // 320° ≡ −40°
        XCTAssertEqual(AvatarGeometry.wireRotation(-50), 3550)    // 355° ≡ −5°
        XCTAssertEqual(Mood.sad.leftEyeRotationForWire, 3200)
        XCTAssertEqual(Mood.sad.rightEyeRotationForWire, 400)
    }

    func testGeometryCarriesRotationThroughToElements() {
        // ⭐ 几何层必须把 rotation 带到 `rotationTenths`
        //    —— 渲染层据此绕眼睛中心旋转（固件容器 pivot = 容器中心）。
        var model = AvatarModel()
        model.leftEye.rotation = 1550
        model.rightEye.rotation = 2050   // 3600 − 1550，与左眼等效反向
        let geo = FaceGeometryEngine.geometry(for: model)
        XCTAssertEqual(geo.leftEye.rotationTenths, 1550)
        XCTAssertEqual(geo.rightEye.rotationTenths, 2050)
    }

    func testEmotionFeatureUsesWireRotationNotRawVisualValue() {
        // ⭐ `Mood.eyeFeature` 必须用**下发值**（0…3600），不是带符号的视觉值
        //    —— 否则 JSONSchema 校验会直接拒绝（rotation 越界）。
        let left = Mood.sad.eyeFeature(side: .leftEye)
        let right = Mood.sad.eyeFeature(side: .rightEye)
        XCTAssertEqual(left.rotation, 3200)
        XCTAssertEqual(right.rotation, 400)
        XCTAssertGreaterThanOrEqual(left.rotation, 0)
        XCTAssertLessThanOrEqual(left.rotation, 3600)
        XCTAssertGreaterThanOrEqual(right.rotation, 0)
        XCTAssertLessThanOrEqual(right.rotation, 3600)
    }
}
