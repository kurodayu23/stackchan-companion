import Foundation
#if canImport(CoreFoundation)
import CoreFoundation
#endif

/// 本地 JSON schema 校验的错误类型。
///
/// ⭐ 为什么必须有这一层：
///    固件用 ArduinoJson **逐字段 `is<int>()`** 判断，**未知字段 / 错类型字段静默忽略、不报错**
///    （`docs/research/53` §3.1、§7 事实 2）⇒ 下发拼错的 key 不会报错，只会「什么都没发生」。
///    ⇒ 后端与 App 侧必须本地校验 + 单测（`docs/research/53` §7 事实 2）。
public enum SchemaError: Error, Equatable, Sendable {
    /// 顶层不是 JSON 对象。
    case notAnObject(found: String)
    /// 顶层不是 JSON 数组。
    case notAnArray(found: String)
    /// 缺 key。
    case missingKey(path: String)
    /// 值不是整数（JSON 里带小数点就算不是 int，与 ArduinoJson `is<int>()` 判定一致）。
    case notAnInt(path: String)
    /// 值不是字符串。
    case notAString(path: String)
    /// 数值超出允许范围。
    case outOfRange(path: String, value: Int, allowed: String)
    /// 出现契约之外的 key（固件会静默忽略，这里显式报错）。
    case unknownKey(path: String, key: String)
    /// payload 为空。
    case emptyPayload
}

/// JSON schema 校验工具。
///
/// ⚠️ **校验严格度与固件的差异（有意为之）**：
///    - 固件：未知 key 静默忽略、缺 key 用默认值、单字段非 int 只忽略该字段；
///    - 我们：**契约要求的 key 必须齐全、多余 key 直接报错、x/y 必须同时是 int**。
///    理由见 ``SchemaError`` 的文档注释。
public enum JSONSchema {

    // MARK: - 基础取值

    /// 顶层必须是 JSON 对象。
    public static func requireObject(_ value: Any) throws -> [String: Any] {
        guard let object = value as? [String: Any] else {
            throw SchemaError.notAnObject(found: typeName(of: value))
        }
        return object
    }

    /// 顶层必须是 JSON 数组。
    public static func requireArray(_ value: Any) throws -> [Any] {
        guard let array = value as? [Any] else {
            throw SchemaError.notAnArray(found: typeName(of: value))
        }
        return array
    }

    /// 取一个必填的整数字段。
    ///
    /// ⚠️ **「是不是 int」的判定**：JSON 数字带小数点即**不算 int**。
    ///    这与固件 ArduinoJson 的 `is<int>()` 判定一致（`docs/research/53` §3.1）。
    public static func requireInt(_ container: [String: Any], key: String, path: String) throws -> Int {
        guard let raw = container[key] else {
            throw SchemaError.missingKey(path: "\(path).\(key)")
        }
        guard isIntegerJSONNumber(raw) else {
            throw SchemaError.notAnInt(path: "\(path).\(key)")
        }
        guard let number = raw as? NSNumber else {
            throw SchemaError.notAnInt(path: "\(path).\(key)")
        }
        return number.intValue
    }

    /// 取一个必填的字符串字段。
    public static func requireString(_ container: [String: Any], key: String, path: String) throws -> String {
        guard let raw = container[key] else {
            throw SchemaError.missingKey(path: "\(path).\(key)")
        }
        guard let text = raw as? String else {
            throw SchemaError.notAString(path: "\(path).\(key)")
        }
        return text
    }

    /// 拒绝契约之外的 key（固件静默忽略 ⇒ 这里显式报错）。
    public static func rejectUnknownKeys(_ container: [String: Any], allowed: Set<String>, path: String) throws {
        for key in container.keys where !allowed.contains(key) {
            throw SchemaError.unknownKey(path: path, key: key)
        }
    }

    /// 判断一个 JSON 数值是不是**整数**。
    ///
    /// 规则：JSON 数字**带小数点即不是 int**（与固件 ArduinoJson `is<int>()` 一致）。
    ///
    /// ⚠️ **【运行时未验证】** —— 本机（Windows）没有 Swift 编译器，无法实跑这段。
    ///    实现依赖一个 Foundation 行为假设：`JSONSerialization` 对 `10` 返回**整数型** NSNumber，
    ///    对 `10.0` 返回**浮点型** NSNumber。
    ///    该假设由单测 `testJSONSerializationPreservesIntegerTypes` 在 macOS CI 上守门，
    ///    若 Foundation 行为变化，单测会红。
    public static func isIntegerJSONNumber(_ value: Any) -> Bool {
        guard let number = value as? NSNumber else { return false }
        #if canImport(CoreFoundation)
        // JSON 的 true/false 也是 NSNumber，必须排除
        if CFGetTypeID(number) == CFBooleanGetTypeID() { return false }
        if CFNumberIsFloatType(number) { return false }
        #endif
        return true
    }

    /// 类型的可读名（错误信息用）。
    public static func typeName(of value: Any) -> String {
        switch value {
        case is [Any]: return "array"
        case is [String: Any]: return "object"
        case is String: return "string"
        case is NSNumber: return "number"
        default: return "unknown"
        }
    }

    // MARK: - ControlAvatar(0x03)

    /// ControlAvatar 契约的 3 个元素 key。
    public static let avatarElementKeys: Set<String> = ["leftEye", "rightEye", "mouth"]
    /// 元素内部必须齐全的 5 个参数 key。
    public static let avatarFeatureKeys: Set<String> = ["x", "y", "rotation", "weight", "size"]

    /// 校验 ControlAvatar(0x03) 的 payload，并返回解析后的模型。
    ///
    /// ⭐ 出处：`docs/spec/03` §2.5.1
    public static func validateControlAvatar(_ value: Any) throws -> AvatarModel {
        let root = try requireObject(value)
        try rejectUnknownKeys(root, allowed: avatarElementKeys, path: "avatar")
        return AvatarModel(
            leftEye: try validateFeature(root, key: "leftEye"),
            rightEye: try validateFeature(root, key: "rightEye"),
            mouth: try validateFeature(root, key: "mouth")
        )
    }

    /// 校验单个表情元素（5 个参数）。
    ///
    /// ⭐ x/y 必须**同时是 int** 才生效（硬线，见 `docs/spec/06-表情参数模型.md` §1.3、§4.1）：
    ///    0x03 的固件 `update_feature` 里 x 与 y **必须同时是 int** 才调 `setPosition`
    ///    —— 只给 x 不给 y ⇒ **位置整体不生效**。
    ///    ⇒ 我们把它做成**成对**判定（不是逐字段），否则会出现"半个坐标生效"的错位。
    ///
    /// ⚠️ **通道差异（0x14 与 0x03 不同）**：`docs/spec/06` §1.3
    ///    「**0x14**：`x` 与 `y` **各自独立**判 `is<int>()`（可以只给一个，与 0x03 不同）」
    ///    ⇒ 固件在 0x14 下会"丢掉那个非 int 的、保留另一个"。
    ///    本方法对**两条通道都判成对**，属于**故意比固件严**（见文件头的说明）：
    ///    与固件不一致的帧我们宁可拒收，也不要让它"一半生效"。
    public static func validateFeature(_ root: [String: Any], key: String) throws -> AvatarFeature {
        let path = "avatar.\(key)"
        guard let raw = root[key] else {
            throw SchemaError.missingKey(path: path)
        }
        let element = try requireObject(raw)
        try rejectUnknownKeys(element, allowed: avatarFeatureKeys, path: path)

        // x / y 必须同时是 int
        let x = try requireInt(element, key: "x", path: path)
        let y = try requireInt(element, key: "y", path: path)

        let rotation = try requireInt(element, key: "rotation", path: path)
        let weight = try requireInt(element, key: "weight", path: path)
        let size = try requireInt(element, key: "size", path: path)

        // 量纲（docs/research/53 §3.2）
        guard (-100...100).contains(x) else {
            throw SchemaError.outOfRange(path: "\(path).x", value: x, allowed: "-100...100")
        }
        guard (-100...100).contains(y) else {
            throw SchemaError.outOfRange(path: "\(path).y", value: y, allowed: "-100...100")
        }
        // rotation：0.1 度。固件存储钳位 0..3600（`Element::setRotation`）。
        // ⚠️ **不要下发负 rotation**（负值在视觉上仍生效，但 `getRotation()` 读回是 0），
        //    反向角度用 `3600 - θ` 表达 —— 出处：docs/spec/06-表情参数模型.md §4.3。
        guard (0...3600).contains(rotation) else {
            throw SchemaError.outOfRange(path: "\(path).rotation", value: rotation, allowed: "0...3600")
        }
        guard (0...100).contains(weight) else {
            throw SchemaError.outOfRange(path: "\(path).weight", value: weight, allowed: "0...100")
        }
        guard (-100...100).contains(size) else {
            throw SchemaError.outOfRange(path: "\(path).size", value: size, allowed: "-100...100")
        }
        return AvatarFeature(x: x, y: y, rotation: rotation, weight: weight, size: size)
    }

    // MARK: - ControlMotion(0x04)

    /// ControlMotion 契约的 2 个舵机 key。
    public static let motionServoKeys: Set<String> = ["yawServo", "pitchServo"]
    /// 舵机对象内必须齐全的 2 个字段 key。
    public static let servoKeys: Set<String> = ["angle", "speed"]

    /// 校验 ControlMotion(0x04) 的 payload。
    ///
    /// ⭐ 出处：`docs/spec/03` §2.4；限位出处同 §2.4（`hal_servo.cpp` `servo_init()`）。
    public static func validateControlMotion(_ value: Any) throws -> MotionModel {
        let root = try requireObject(value)
        try rejectUnknownKeys(root, allowed: motionServoKeys, path: "motion")
        let yaw = try validateServo(root, key: "yawServo", isValid: ServoLimit.isValidYaw)
        let pitch = try validateServo(root, key: "pitchServo", isValid: ServoLimit.isValidPitch)
        return MotionModel(yawServo: yaw, pitchServo: pitch)
    }

    /// 校验单个舵机目标。
    public static func validateServo(_ root: [String: Any],
                                     key: String,
                                     isValid: (Int) -> Bool) throws -> ServoTarget {
        let path = "motion.\(key)"
        guard let raw = root[key] else {
            throw SchemaError.missingKey(path: path)
        }
        let servo = try requireObject(raw)
        try rejectUnknownKeys(servo, allowed: servoKeys, path: path)
        let angle = try requireInt(servo, key: "angle", path: path)
        let speed = try requireInt(servo, key: "speed", path: path)
        guard isValid(angle) else {
            let allowed = (key == "yawServo")
                ? "\(ServoLimit.yawRange)"
                : "\(ServoLimit.pitchRange)"
            throw SchemaError.outOfRange(path: "\(path).angle", value: angle, allowed: allowed)
        }
        return ServoTarget(angle: angle, speed: speed)
    }
}
