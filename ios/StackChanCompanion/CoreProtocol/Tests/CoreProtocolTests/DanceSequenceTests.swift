import XCTest
@testable import CoreProtocol

/// 0x14 DanceSequence 解码校验单测。
///
/// ⭐ 规则来源：`docs/spec/03` §2.5.3 + `docs/research/53` §5.2
final class DanceSequenceTests: XCTestCase {

    /// 一条合法的关键帧（字段值取自真实关键帧语料的范围：
    /// `D:\AP\AP7000\ai-workspace\stackchan-research\r59\keyframes.json` 的 292 帧之一）。
    private let validFrameJSON = """
    {
      "leftEye":     { "x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0 },
      "rightEye":    { "x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0 },
      "mouth":       { "x": 0,  "y": 0,  "rotation": 0, "weight": 30,  "size": 0 },
      "yawServo":    { "angle": 14,  "speed": 800 },
      "pitchServo":  { "angle": 762, "speed": 800 },
      "leftRgbColor": "#BABABA",
      "rightRgbColor": "#CCCCCC",
      "durationMs": 40
    }
    """

    private func decodeObject(_ json: String) throws -> JSONValue {
        try JSONParser.parse(json)
    }

    // MARK: - 顶层必须是数组

    func testTopLevelArrayIsAccepted() throws {
        let frames = try DanceSequence.decode(try decodeObject("[\(validFrameJSON)]"))
        XCTAssertEqual(frames.count, 1)
        XCTAssertEqual(frames[0].durationMs, 40)
        XCTAssertEqual(frames[0].leftEye.weight, 100)
        XCTAssertEqual(frames[0].yawServo.angle, 14)
        XCTAssertEqual(frames[0].leftRgbColor, "#BABABA")
    }

    func testTopLevelObjectIsRejected() throws {
        // ⭐ 顶层是对象而不是数组 ⇒ 必须拒收
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject(validFrameJSON))) { error in
            guard case .notAnArray = (error as? SchemaError) else {
                return XCTFail("应当抛 notAnArray，实际 \(error)")
            }
        }
    }

    func testTopLevelNumberIsRejected() throws {
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("42"))) { error in
            guard case .notAnArray = (error as? SchemaError) else {
                return XCTFail("应当抛 notAnArray，实际 \(error)")
            }
        }
    }

    func testEmptyArrayIsRejected() throws {
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[]"))) { error in
            XCTAssertEqual(error as? SchemaError, .emptyPayload)
        }
    }

    // MARK: - 每帧 8 个 key 必须齐全

    func testMissingKeyIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 0, "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC"
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            XCTAssertEqual(error as? SchemaError, .missingKey(path: "sequence[0].durationMs"))
        }
    }

    func testUnknownKeyIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 0, "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40,
          "extraKey": 1
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            XCTAssertEqual(error as? SchemaError, .unknownKey(path: "sequence[0]", key: "extraKey"))
        }
    }

    // MARK: - x / y 必须同时是 int

    func testFractionalCoordinateIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 10.5, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0,  "y": 0,  "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 14,  "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            XCTAssertEqual(error as? SchemaError, .notAnInt(path: "sequence[0].leftEye.x"))
        }
    }

    func testCoordinatePairMustBothBeInt() throws {
        // x 是 int、y 是小数 ⇒ 整对坐标不成立 ⇒ 拒收
        let broken = """
        {
          "leftEye":     { "x": 13, "y": -1.5, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 13, "y": -1, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0,  "y": 0,  "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 14,  "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            XCTAssertEqual(error as? SchemaError, .notAnInt(path: "sequence[0].leftEye.y"))
        }
    }

    // MARK: - 舵机限位

    func testYawOutOfRangeIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 1281, "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "sequence[0].yawServo.angle")
        }
    }

    func testPitchOutOfRangeIsRejected() throws {
        // pitch 限位 [30, 870]（0.1 度），29 越界
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 14, "speed": 800 },
          "pitchServo":  { "angle": 29, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "sequence[0].pitchServo.angle")
        }
    }

    func testServoBoundaryValuesAreAccepted() throws {
        let boundary = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": -1280, "speed": 800 },
          "pitchServo":  { "angle": 870, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        let frames = try DanceSequence.decode(try decodeObject("[\(boundary)]"))
        XCTAssertEqual(frames[0].yawServo.angle, -1280)
        XCTAssertEqual(frames[0].pitchServo.angle, 870)
    }

    // MARK: - 颜色与时长

    func testInvalidRgbColorIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 14, "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 40
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "sequence[0].leftRgbColor")
        }
    }

    func testNonPositiveDurationIsRejected() throws {
        let broken = """
        {
          "leftEye":     { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "rightEye":    { "x": 0, "y": 0, "rotation": 0, "weight": 100, "size": 0 },
          "mouth":       { "x": 0, "y": 0, "rotation": 0, "weight": 30,  "size": 0 },
          "yawServo":    { "angle": 14, "speed": 800 },
          "pitchServo":  { "angle": 762, "speed": 800 },
          "leftRgbColor": "#BABABA",
          "rightRgbColor": "#CCCCCC",
          "durationMs": 0
        }
        """
        XCTAssertThrowsError(try DanceSequence.decode(try decodeObject("[\(broken)]"))) { error in
            guard case .outOfRange(let path, _, _) = (error as? SchemaError) else {
                return XCTFail("应当抛 outOfRange，实际 \(error)")
            }
            XCTAssertEqual(path, "sequence[0].durationMs")
        }
    }

    // MARK: - 往返

    func testEncodeDecodeRoundTrip() throws {
        let frames = try DanceSequence.decode(try decodeObject("[\(validFrameJSON)]"))
        let encoded = try DanceSequence.encode(frames)
        let decodedAgain = try DanceSequence.decode(encoded)
        XCTAssertEqual(decodedAgain, frames)
    }

    func testMultiFrameSequenceIsAccepted() throws {
        let json = "[\(validFrameJSON), \(validFrameJSON)]"
        let frames = try DanceSequence.decode(try decodeObject(json))
        XCTAssertEqual(frames.count, 2)
    }
}
