import Foundation

/// DanceSequence(0x14) 的**一个关键帧**。
///
/// ⭐ 事实来源：`docs/spec/03` §2.5.3 + `docs/research/53` §5.2
///    （原始出处：固件 `json_helper.cpp:178-233` `parse_sequence_from_json`）
///
///    顶层必须是 **JSON 数组**，每个元素一个关键帧，**恰好 8 个 key**：
///    `leftEye` / `rightEye` / `mouth` / `yawServo` / `pitchServo` /
///    `leftRgbColor` / `rightRgbColor` / `durationMs`
///
///    ```json
///    [ { "leftEye":     { "x": -10, "y": 0, "rotation": 0, "weight": 50, "size": 0 },
///        "rightEye":    { "x": -10, "y": 0, "rotation": 0, "weight": 50, "size": 0 },
///        "mouth":       { "x": 0,   "y": 0, "rotation": 0, "weight": 50, "size": 0 },
///        "yawServo":    { "angle": 300,  "speed": 200 },
///        "pitchServo":  { "angle": -100, "speed": 200 },
///        "leftRgbColor":  "#FF6D60",
///        "rightRgbColor": "#8FD3F4",
///        "durationMs": 800 } ]
///    ```
///
/// ⚠️ 文档示例里 `pitchServo.angle = -100` **落在固件俯仰限位 [30, 870] 之外**
///    （固件会自行限幅，`docs/spec/03` §2.4）。我们的解码器**严格拒绝**越限角度，
///    理由见 ``DanceSequence`` 的文档注释。
public struct DanceKeyframe: Equatable, Sendable {

    /// 关键帧必须齐全的 8 个 key。
    public static let requiredKeys: Set<String> = [
        "leftEye", "rightEye", "mouth",
        "yawServo", "pitchServo",
        "leftRgbColor", "rightRgbColor", "durationMs"
    ]

    public var leftEye: AvatarFeature
    public var rightEye: AvatarFeature
    public var mouth: AvatarFeature
    public var yawServo: ServoTarget
    public var pitchServo: ServoTarget
    /// 左侧 RGB 灯颜色，形如 `#RRGGBB`。
    public var leftRgbColor: String
    /// 右侧 RGB 灯颜色，形如 `#RRGGBB`。
    public var rightRgbColor: String
    /// 本关键帧的持续时间（毫秒）。
    public var durationMs: Int

    public init(leftEye: AvatarFeature = AvatarFeature(),
                rightEye: AvatarFeature = AvatarFeature(),
                mouth: AvatarFeature = AvatarFeature(),
                yawServo: ServoTarget = ServoTarget(),
                pitchServo: ServoTarget = ServoTarget(),
                leftRgbColor: String = "#000000",
                rightRgbColor: String = "#000000",
                durationMs: Int = 0) {
        self.leftEye = leftEye
        self.rightEye = rightEye
        self.mouth = mouth
        self.yawServo = yawServo
        self.pitchServo = pitchServo
        self.leftRgbColor = leftRgbColor
        self.rightRgbColor = rightRgbColor
        self.durationMs = durationMs
    }
}

/// DanceSequence(0x14) 的解码与校验。
///
/// ⚠️ **为什么解码比固件严格**：
///    固件逐字段判断、未知 key 静默忽略（`docs/research/53` §3.1、§7 事实 2），
///    所以**拼错的 key 不会让设备报错，只会「什么都没发生」**。
///    ⇒ 解码端必须本地校验（`docs/research/53` §7 事实 2）。
///    此外 0x14 关键帧**绕过 modify lock**（`docs/research/53` §5、§4.4），
///    一旦下发就是"立刻生效"，容错率更低 ⇒ 宁可拒收，不要静默跑偏。
public enum DanceSequence {

    /// 解析并校验一个 0x14 payload。
    ///
    /// - Parameter data: payload 字节（UTF-8 JSON）
    /// - Returns: 关键帧数组
    /// - Throws: ``SchemaError`` 或 JSON 解析错误
    public static func decode(_ data: Data) throws -> [DanceKeyframe] {
        let value: JSONValue
        do {
            value = try JSONParser.parse(data)
        } catch {
            throw SchemaError.notAnArray(found: "invalid-json")
        }
        return try decode(value)
    }

    /// 解析并校验一个 0x14 payload（已经是 `JSONValue` 的情况）。
    public static func decode(_ value: JSONValue) throws -> [DanceKeyframe] {
        // ⭐ 顶层必须是**数组**（固件 `parse_sequence_from_json` 读的是数组）
        let array = try JSONSchema.requireArray(value)
        guard !array.isEmpty else {
            throw SchemaError.emptyPayload
        }
        var frames: [DanceKeyframe] = []
        for (index, element) in array.enumerated() {
            frames.append(try validateKeyframe(element, index: index))
        }
        return frames
    }

    /// 校验单个关键帧。
    public static func validateKeyframe(_ value: JSONValue, index: Int) throws -> DanceKeyframe {
        let path = "sequence[\(index)]"
        let root = try JSONSchema.requireObject(value)
        try JSONSchema.rejectUnknownKeys(root, allowed: DanceKeyframe.requiredKeys, path: path)

        let leftEye = try JSONSchema.validateFeature(root, key: "leftEye", pathPrefix: path)
        let rightEye = try JSONSchema.validateFeature(root, key: "rightEye", pathPrefix: path)
        let mouth = try JSONSchema.validateFeature(root, key: "mouth", pathPrefix: path)

        let yaw = try JSONSchema.validateServo(root, key: "yawServo",
                                               isValid: ServoLimit.isValidYaw, pathPrefix: path)
        let pitch = try JSONSchema.validateServo(root, key: "pitchServo",
                                                 isValid: ServoLimit.isValidPitch, pathPrefix: path)

        let leftColor = try JSONSchema.requireString(root, key: "leftRgbColor", path: path)
        let rightColor = try JSONSchema.requireString(root, key: "rightRgbColor", path: path)
        try validateRgbColor(leftColor, path: "\(path).leftRgbColor")
        try validateRgbColor(rightColor, path: "\(path).rightRgbColor")

        let duration = try JSONSchema.requireInt(root, key: "durationMs", path: path)
        guard duration > 0 else {
            throw SchemaError.outOfRange(path: "\(path).durationMs", value: duration, allowed: "> 0")
        }

        return DanceKeyframe(leftEye: leftEye,
                             rightEye: rightEye,
                             mouth: mouth,
                             yawServo: yaw,
                             pitchServo: pitch,
                             leftRgbColor: leftColor,
                             rightRgbColor: rightColor,
                             durationMs: duration)
    }

    /// 校验 RGB 颜色字符串（**必须**是 `#RRGGBB`）。
    ///
    /// ⭐ 出处：`docs/spec/03` §2.5.3 的 keyframe 示例（`"#FF6D60"` / `"#8FD3F4"`）
    ///    —— `#` 是格式的一部分，缺 `#` 的裸十六进制串不接受（与 Python 侧复核脚本同规则）。
    public static func validateRgbColor(_ value: String, path: String) throws {
        guard value.hasPrefix("#") else {
            throw SchemaError.outOfRange(path: path, value: 0, allowed: "#RRGGBB")
        }
        let hex = String(value.dropFirst())
        guard hex.count == 6, hex.allSatisfy({ $0.isHexDigit }) else {
            throw SchemaError.outOfRange(path: path, value: 0, allowed: "#RRGGBB")
        }
    }

    /// 把关键帧数组编码成 payload（顶层 JSON 数组）。
    ///
    /// ⭐ 用**自研序列化器**（`JSONValue.serialized()`）而不是 `JSONSerialization`：
    ///    后者会把整数重新写成 `10.0` 之类（取决于平台与 Foundation 版本），
    ///    而固件 ArduinoJson 的 `is<int>()` 对**带小数点的字面量判 false**
    ///    ⇒ 编码端必须保证整数就是整数，否则**我们自己编的帧会被固件静默忽略**。
    public static func encode(_ frames: [DanceKeyframe]) throws -> Data {
        let array: [JSONValue] = frames.map { frame in
            .object([
                "leftEye": featureToValue(frame.leftEye),
                "rightEye": featureToValue(frame.rightEye),
                "mouth": featureToValue(frame.mouth),
                "yawServo": servoToValue(frame.yawServo),
                "pitchServo": servoToValue(frame.pitchServo),
                "leftRgbColor": .string(frame.leftRgbColor),
                "rightRgbColor": .string(frame.rightRgbColor),
                "durationMs": .int(frame.durationMs)
            ])
        }
        return JSONValue.array(array).serializedData()
    }

    private static func featureToValue(_ feature: AvatarFeature) -> JSONValue {
        .object([
            "x": .int(feature.x),
            "y": .int(feature.y),
            "rotation": .int(feature.rotation),
            "weight": .int(feature.weight),
            "size": .int(feature.size)
        ])
    }

    private static func servoToValue(_ servo: ServoTarget) -> JSONValue {
        .object([
            "angle": .int(servo.angle),
            "speed": .int(servo.speed)
        ])
    }
}
