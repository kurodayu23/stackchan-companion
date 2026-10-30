import XCTest
@testable import CoreProtocol

/// 表情模型 / 极性 / 单位换算单测。
///
/// ⭐ 规则来源：`docs/research/53` §2（情绪映射表）、§3.2（量纲）、`docs/spec/03` §2.4（舵机限位）
final class AvatarModelTests: XCTestCase {

    // MARK: - weight 极性

    func testEyeWeightPolarityIsNotInverted() {
        // ⭐ 眼睛 weight 越大 = 越睁开（固件 eyes.cpp:87-120 情绪表：
        //    Neutral=100 全睁，Sleepy=35 几乎闭）。参数名叫"眼睑下沉"，数值方向是反的。
        XCTAssertFalse(WeightPolarity.EyeWeight.inverted)
    }

    func testMouthWeightPolarityIsNotInverted() {
        // ⭐ 嘴 weight 越大 = 越张开（固件 mouth.cpp:55-59；SpeakingModifier 改写嘴 weight 实现开合）
        XCTAssertFalse(WeightPolarity.MouthWeight.inverted)
    }

    func testOpennessMapsWeightDirectly() {
        XCTAssertEqual(WeightPolarity.openness(element: .leftEye, weight: 100), 1.0, accuracy: 0.0001)
        XCTAssertEqual(WeightPolarity.openness(element: .leftEye, weight: 35), 0.35, accuracy: 0.0001)
        XCTAssertEqual(WeightPolarity.openness(element: .mouth, weight: 0), 0.0, accuracy: 0.0001)
        XCTAssertEqual(WeightPolarity.openness(element: .mouth, weight: 100), 1.0, accuracy: 0.0001)
    }

    func testOpennessClampsOutOfRangeWeight() {
        XCTAssertEqual(WeightPolarity.openness(element: .leftEye, weight: 300), 1.0, accuracy: 0.0001)
        XCTAssertEqual(WeightPolarity.openness(element: .leftEye, weight: -20), 0.0, accuracy: 0.0001)
    }

    // MARK: - 官方情绪表

    func testMoodTableMatchesFirmwareEmotionMapping() {
        // ⭐ docs/research/53 §2（eyes.cpp:87-120）
        XCTAssertEqual(Mood.neutral.eyeWeight, 100)
        XCTAssertEqual(Mood.happy.eyeWeight, 72)
        XCTAssertEqual(Mood.angry.eyeWeight, 70)
        XCTAssertEqual(Mood.sad.eyeWeight, 70)
        XCTAssertEqual(Mood.doubt.eyeWeight, 75)
        XCTAssertEqual(Mood.sleepy.eyeWeight, 35)

        XCTAssertEqual(Mood.happy.leftEyeRotation, 1550)
        XCTAssertEqual(Mood.happy.rightEyeRotation, -1550)
        XCTAssertEqual(Mood.sad.leftEyeRotation, -400)
        XCTAssertEqual(Mood.sleepy.leftEyeRotation, -50)
        XCTAssertEqual(Mood.neutral.leftEyeRotation, 0)
    }

    /// ⚠️ 固件视觉值是带符号的；**下发时必须换算成 0…3600 的等效正角**。
    ///
    /// ⭐ 规则：`docs/spec/06-表情参数模型.md` §4.3「不要下发负 rotation，用 3600-θ 表达反向」。
    /// ⚠️ `docs/spec/06` §5.1 表注写「用 3560 表达 −40°」是**算术笔误**
    ///    （3560 × 0.1° = 356° = −4°）；正确值是 3600 − 400 = **3200**。
    func testWireRotationMapsNegativeToEquivalentPositive() {
        XCTAssertEqual(AvatarGeometry.wireRotation(0), 0)
        XCTAssertEqual(AvatarGeometry.wireRotation(1550), 1550)
        XCTAssertEqual(AvatarGeometry.wireRotation(-400), 3200, "−40° 的等效正角是 3200（0.1° 单位）")
        XCTAssertEqual(AvatarGeometry.wireRotation(-50), 3550)
        XCTAssertEqual(AvatarGeometry.wireRotation(-1550), 2050)
        XCTAssertEqual(AvatarGeometry.wireRotation(-450), 3150)
    }

    func testMoodWireRotationsAreWithinSchemaRange() {
        for mood in Mood.allCases {
            XCTAssertTrue((0...3600).contains(mood.leftEyeRotationForWire),
                          "\(mood.rawValue) 左眼下发值越界")
            XCTAssertTrue((0...3600).contains(mood.rightEyeRotationForWire),
                          "\(mood.rawValue) 右眼下发值越界")
        }
        XCTAssertEqual(Mood.sad.leftEyeRotationForWire, 3200)
        XCTAssertEqual(Mood.sad.rightEyeRotationForWire, 400)
    }

    // MARK: - 设备端几何公式（docs/spec/06 §2.2 / §6.2）

    func testEyeDiameterFormula() {
        XCTAssertEqual(AvatarGeometry.eyeDiameter(size: 0), 20, "size = 0 ⇒ 20 px")
        XCTAssertEqual(AvatarGeometry.eyeDiameter(size: 100), 32)
        XCTAssertEqual(AvatarGeometry.eyeDiameter(size: -100), 8)
    }

    func testEyelidOffsetIsNegativeAndProportionalToWeight() {
        XCTAssertEqual(AvatarGeometry.eyelidOffsetY(weight: 0, eyeDiameter: 20), 0)
        XCTAssertEqual(AvatarGeometry.eyelidOffsetY(weight: 100, eyeDiameter: 20), -20)
        XCTAssertEqual(AvatarGeometry.eyelidOffsetY(weight: 50, eyeDiameter: 20), -10)
    }

    func testMouthRectFormula() {
        let closed = AvatarGeometry.mouthRect(weight: 0)
        XCTAssertEqual(closed.width, 90)
        XCTAssertEqual(closed.height, 6)
        XCTAssertEqual(closed.cornerRadius, 0)

        let open = AvatarGeometry.mouthRect(weight: 100)
        XCTAssertEqual(open.width, 60)
        XCTAssertEqual(open.height, 50)
        XCTAssertEqual(open.cornerRadius, 16)
    }

    func testRestingDefaultMatchesFirmwareInitialState() {
        // docs/spec/06 §3：眼睛 weight = 100、嘴 weight = 0
        let resting = AvatarModel.restingDefault
        XCTAssertEqual(resting.leftEye.weight, 100)
        XCTAssertEqual(resting.rightEye.weight, 100)
        XCTAssertEqual(resting.mouth.weight, 0)
        XCTAssertEqual(resting.leftEye.size, 0)
        XCTAssertEqual(resting.mouth.size, 0)
    }

    func testMoodHasExactlySixCases() {
        // ⭐ 设备端只有 6 种情绪，不可远程设置（docs/research/53 §1、§2）
        XCTAssertEqual(Mood.allCases.count, 6)
    }

    func testEyeFeatureUsesMoodWeightAndRotation() {
        let happy = Mood.happy.eyeFeature(side: .leftEye)
        XCTAssertEqual(happy.weight, 72)
        XCTAssertEqual(happy.rotation, 1550)

        // ⚠️ 右眼是**等效正角 2050**（3600 − 1550），不是固件的视觉值 −1550。
        //    理由：固件 `Element::setRotation` 把存储值钳到 0…3600，
        //    负值读回是 0（`docs/spec/06-表情参数模型.md` §4.3），
        //    ⇒ 下发必须用等效正角；`eyeFeature` 的文档也写明「rotation 用**下发值**」。
        //    ⭐ 2026-10-30 第一次在 macOS CI 真跑时，这条断言写的是 −1550，
        //    与同一函数里左眼的 1550（本来就是下发值）自相矛盾 ⇒ 这里按**下发值**订正。
        let right = Mood.happy.eyeFeature(side: .rightEye)
        XCTAssertEqual(right.rotation, 2050)
        XCTAssertEqual(Mood.happy.rightEyeRotation, -1550, "固件视觉值本身仍带符号的 −1550")
    }

    // MARK: - x/y 单位换算（系数 6.25）

    func testJsonToPixelUsesFactorSixPointTwoFive() {
        // ⭐ JSON ±100 ↔ 像素 ±16（docs/research/53 §3.2，固件 eyes.cpp:14-18 限幅 ±16）
        XCTAssertEqual(AvatarCoordinate.jsonToPixel(100), 16.0, accuracy: 0.0001)
        XCTAssertEqual(AvatarCoordinate.jsonToPixel(-100), -16.0, accuracy: 0.0001)
        XCTAssertEqual(AvatarCoordinate.jsonToPixel(0), 0.0, accuracy: 0.0001)
        XCTAssertEqual(AvatarCoordinate.jsonToPixel(50), 8.0, accuracy: 0.0001)
    }

    func testPixelToJsonUsesFactorSixPointTwoFive() {
        XCTAssertEqual(AvatarCoordinate.pixelToJson(16), 100)
        XCTAssertEqual(AvatarCoordinate.pixelToJson(-16), -100)
        XCTAssertEqual(AvatarCoordinate.pixelToJson(0), 0)
        XCTAssertEqual(AvatarCoordinate.pixelToJson(8), 50)
    }

    func testCoordinateRoundTripIsStable() {
        for json in [-100, -50, -13, 0, 13, 50, 100] {
            let pixel = AvatarCoordinate.jsonToPixel(json)
            XCTAssertEqual(AvatarCoordinate.pixelToJson(pixel), json)
        }
    }

    // MARK: - 舵机限位

    func testServoLimitsMatchFirmware() {
        // ⭐ docs/spec/03 §2.4：yaw ∈ [-1280, 1280]，pitch ∈ [30, 870]（0.1 度）
        XCTAssertTrue(ServoLimit.isValidYaw(-1280))
        XCTAssertTrue(ServoLimit.isValidYaw(1280))
        XCTAssertFalse(ServoLimit.isValidYaw(1281))
        XCTAssertFalse(ServoLimit.isValidYaw(-1281))

        XCTAssertTrue(ServoLimit.isValidPitch(30))
        XCTAssertTrue(ServoLimit.isValidPitch(870))
        XCTAssertFalse(ServoLimit.isValidPitch(29))
        XCTAssertFalse(ServoLimit.isValidPitch(871))
    }

    func testServoDegreesConversion() {
        XCTAssertEqual(ServoLimit.degrees(762), 76.2, accuracy: 0.0001)
        XCTAssertEqual(ServoLimit.degrees(-1280), -128.0, accuracy: 0.0001)
        XCTAssertEqual(ServoLimit.degrees(30), 3.0, accuracy: 0.0001)
        XCTAssertEqual(ServoLimit.degrees(870), 87.0, accuracy: 0.0001)
    }

    // MARK: - JSON 整数判定

    func testJSONParserDistinguishesIntegerFromFractionalLiteral() throws {
        // ⭐ 这条测试守的是**我们自己的解析器**，不是 Foundation 的行为。
        //    旧版本依赖「JSONSerialization 对 `10` 返回整数型 NSNumber、对 `10.0` 返回浮点型」
        //    —— 那条假设在 2026-10-30 第一次 macOS CI 真跑时被证伪
        //    （`JSONSerialization` 连顶层片段 `"10"` 都解析不了，抛 NSCocoaError 3840）。
        //    ⇒ 现在 int / double 由**字面量**判定，与平台、Foundation 版本无关。
        let integer = try JSONParser.parse("10")
        XCTAssertTrue(JSONSchema.isIntegerJSONNumber(integer))

        let fractional = try JSONParser.parse("10.0")
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(fractional))

        let exponential = try JSONParser.parse("1e2")
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(exponential),
                       "指数写法也算非整数（固件 is<int>() 同样判 false）")
    }

    func testIntegerJSONNumberRejectsNonNumbers() throws {
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(try JSONParser.parse("\"10\"")))
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(try JSONParser.parse("[1, 2]")))
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(try JSONParser.parse("{\"a\": 1}")))
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(try JSONParser.parse("true")))
    }

    func testIntegerJSONNumberRejectsFractionalValue() throws {
        let value = try JSONParser.parse("10.5")
        XCTAssertFalse(JSONSchema.isIntegerJSONNumber(value))
    }

    func testJSONParserRejectsTopLevelFragmentFromFoundation() throws {
        // ⭐ 旧实现用 `JSONSerialization` 时，顶层片段（`10` / `"x"` / `true`）
        //    会抛 Foundation 的 NSCocoaError 3840 ⇒ 我们的 `SchemaError` 根本轮不到。
        //    ⇒ 现在顶层片段能正常解析成值，再由 schema 层**用我们自己的错误类型**拒收。
        let number = try JSONParser.parse("42")
        XCTAssertThrowsError(try DanceSequence.decode(number)) { error in
            guard case .notAnArray = (error as? SchemaError) else {
                return XCTFail("应当抛 notAnArray，实际 \(error)")
            }
        }
    }

    // MARK: - ControlAvatar 校验

    func testValidControlAvatarIsAccepted() throws {
        let json = """
        { "leftEye":  { "x": 0,  "y": 0, "rotation": 0,    "weight": 100, "size": 0 },
          "rightEye": { "x": 13, "y": -1, "rotation": 1550, "weight": 72,  "size": 0 },
          "mouth":    { "x": 0,  "y": 0, "rotation": 0,    "weight": 30,  "size": 0 } }
        """
        let value = try JSONParser.parse(json)
        let model = try JSONSchema.validateControlAvatar(value)

        XCTAssertEqual(model.leftEye.weight, 100)
        XCTAssertEqual(model.rightEye.rotation, 1550)
        XCTAssertEqual(model.rightEye.x, 13)
        XCTAssertEqual(model.rightEye.y, -1)
        XCTAssertEqual(model.mouth.weight, 30)
    }

    func testControlAvatarRejectsFloatCoordinate() throws {
        let json = """
        { "leftEye":  { "x": 10.5, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye": { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":    { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 } }
        """
        let value = try JSONParser.parse(json)
        XCTAssertThrowsError(try JSONSchema.validateControlAvatar(value)) { error in
            XCTAssertEqual(error as? SchemaError, .notAnInt(path: "avatar.leftEye.x"))
        }
    }

    func testControlAvatarRejectsMissingElement() throws {
        let json = """
        { "leftEye":  { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":    { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 } }
        """
        let value = try JSONParser.parse(json)
        XCTAssertThrowsError(try JSONSchema.validateControlAvatar(value)) { error in
            XCTAssertEqual(error as? SchemaError, .missingKey(path: "avatar.rightEye"))
        }
    }

    func testControlAvatarRejectsOutOfRangeWeight() throws {        let json = """
        { "leftEye":  { "x": 0, "y": 0, "rotation": 0, "weight": 101, "size": 0 },
          "rightEye": { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":    { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 } }
        """
        let value = try JSONParser.parse(json)
        XCTAssertThrowsError(try JSONSchema.validateControlAvatar(value)) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "avatar.leftEye.weight")
        }
    }

    // MARK: - ControlMotion 校验

    func testControlAvatarRejectsNegativeRotation() throws {
        // ⭐ docs/spec/06 §4.3：不要下发负 rotation（固件存储值钳到 0…3600，负值读回是 0）
        let json = """
        { "leftEye":  { "x": 0, "y": 0, "rotation": -400, "weight": 100, "size": 0 },
          "rightEye": { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":    { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 } }
        """
        let value = try JSONParser.parse(json)
        XCTAssertThrowsError(try JSONSchema.validateControlAvatar(value)) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "avatar.leftEye.rotation")
        }
    }

    func testValidControlMotionIsAccepted() throws {
        let json = """
        { "yawServo":   { "angle": -60, "speed": 500 },
          "pitchServo": { "angle": 220, "speed": 500 } }
        """
        let value = try JSONParser.parse(json)
        let model = try JSONSchema.validateControlMotion(value)
        XCTAssertEqual(model.yawServo.angle, -60)
        XCTAssertEqual(model.pitchServo.angle, 220)
        XCTAssertEqual(model.yawServo.speed, 500)
    }

    func testControlMotionRejectsOutOfRangePitch() throws {
        let json = """
        { "yawServo":   { "angle": 0, "speed": 500 },
          "pitchServo": { "angle": 900, "speed": 500 } }
        """
        let value = try JSONParser.parse(json)
        XCTAssertThrowsError(try JSONSchema.validateControlMotion(value)) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "motion.pitchServo.angle")
        }
    }
}
