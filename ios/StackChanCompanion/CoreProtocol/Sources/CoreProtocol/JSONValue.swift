import Foundation

// ============================================================================
// JSONValue —— **自研 JSON 值树 + 解析器**（不依赖 `JSONSerialization`）。
//
// ⭐⭐ 为什么不用 Foundation 的 `JSONSerialization`：
//    我们必须区分「`10`」和「`10.0`」——
//    固件 ArduinoJson 的 `is<int>()` 判定是「**字面量带不带小数点**」
//    （`docs/research/53` §3.1、`docs/spec/06-表情参数模型.md` §1.3），
//    而 `JSONSerialization` 把两者都变成 `NSNumber`，
//    **能否区分取决于 Foundation 版本与平台**（Darwin 与 swift-corelibs 行为不同）。
//
//    ⭐ 旧实现（2026-10-30 之前）把这条写成了「**【运行时未验证】** 的假设」：
//       "JSONSerialization 对 `10` 返回整数型 NSNumber、对 `10.0` 返回浮点型 NSNumber"
//       并由单测 `testJSONSerializationPreservesIntegerTypes` 守门。
//       —— 2026-10-30 **第一次在 GitHub Actions（macOS / Xcode 16.2）真跑**时，
//          这条单测直接红了，而且暴露了更基础的问题：
//          `JSONSerialization.jsonObject(with:options:)` **连顶层片段都解析不了**
//          （`"10"` / `"10.0"` / `"10.5"` 全部抛 NSCocoaError 3840
//          "JSON text did not start with array or object…"）。
//
//    ⇒ 现在改成**自研解析器**：数字按**字面量**判定 int / double，
//      与平台、Foundation 版本**完全无关**，与固件 `is<int>()` 语义一一对应。
//      顺带解决「顶层片段解析」问题（我们本来就要把顶层数字/字符串**拒收**，
//      但必须是我们自己的 `SchemaError`，而不是 Foundation 的 NSCocoaError）。
//
// ⛔ 本文件**不含任何协议规则**：只有「怎么把 JSON 文本变成值树」。
//    契约校验在 `JSONSchema.swift`，帧语义在 `DanceSequence.swift`。
// ============================================================================

/// 一个 JSON 值。
///
/// ⭐ **数字分两类**：`.int`（字面量不带小数点 / 指数）与 `.double`（带小数点或指数）。
///    这条区分就是「固件 ArduinoJson `is<int>()`」的等价物。
public enum JSONValue: Equatable, Sendable {

    /// JSON 对象。
    case object([String: JSONValue])
    /// JSON 数组。
    case array([JSONValue])
    /// JSON 字符串。
    case string(String)
    /// JSON 整数（字面量不带小数点 / 指数，且能装进 `Int`）。
    case int(Int)
    /// JSON 非整数（字面量带小数点或指数，或超出 `Int` 表示范围）。
    case double(Double)
    /// JSON 布尔。
    case bool(Bool)
    /// JSON `null`。
    case null
}

/// JSON 解析失败的原因。
public enum JSONParseError: Error, Equatable, Sendable {
    /// 输入提前结束。
    case unexpectedEnd
    /// 出现不该在这里的字符。
    case unexpectedCharacter(offset: Int)
    /// 数字字面量非法。
    case invalidNumber(offset: Int)
    /// 字符串字面量非法（转义 / UTF-8 / 代理对）。
    case invalidString(offset: Int)
    /// 解析完一个值之后还有多余内容。
    case trailingData(offset: Int)
    /// 嵌套层数超限（防御畸形输入导致的栈溢出）。
    case depthExceeded
}

/// JSON 解析器（自研，**行为与平台无关**）。
///
/// ⚠️ 刻意**不支持** Foundation 的 `JSONSerialization`：
///    它对「顶层片段」和「整数 / 小数」的处理都不可控（见文件头）。
///    本解析器覆盖的是**协议需要的 JSON 子集**：对象 / 数组 / 字符串 / 数字 / 布尔 / null。
public enum JSONParser {

    /// 解析 UTF-8 字节。
    public static func parse(_ data: Data) throws -> JSONValue {
        try parse([UInt8](data))
    }

    /// 解析字符串。
    public static func parse(_ text: String) throws -> JSONValue {
        try parse(Array(text.utf8))
    }

    /// 解析字节数组。
    public static func parse(_ bytes: [UInt8]) throws -> JSONValue {
        var scanner = Scanner(bytes: bytes)
        scanner.skipWhitespace()
        let value = try scanner.parseValue(depth: 0)
        scanner.skipWhitespace()
        guard scanner.isAtEnd else {
            throw JSONParseError.trailingData(offset: scanner.offset)
        }
        return value
    }
}

// MARK: - 扫描器

/// 递归下降扫描器（内部实现）。
private struct Scanner {

    /// 最大嵌套层数（防御畸形输入）。
    private static let maxDepth = 64

    let bytes: [UInt8]
    var offset: Int = 0

    init(bytes: [UInt8]) {
        self.bytes = bytes
    }

    var isAtEnd: Bool { offset >= bytes.count }

    /// 跳过 JSON 允许的空白（空格 / 制表 / 换行 / 回车）。
    mutating func skipWhitespace() {
        while offset < bytes.count {
            let b = bytes[offset]
            if b == 0x20 || b == 0x09 || b == 0x0A || b == 0x0D {
                offset += 1
            } else {
                return
            }
        }
    }

    mutating func parseValue(depth: Int) throws -> JSONValue {
        guard depth <= Scanner.maxDepth else { throw JSONParseError.depthExceeded }
        guard offset < bytes.count else { throw JSONParseError.unexpectedEnd }
        switch bytes[offset] {
        case 0x7B:                                   // {
            return try parseObject(depth: depth)
        case 0x5B:                                   // [
            return try parseArray(depth: depth)
        case 0x22:                                   // "
            return .string(try parseString())
        case 0x74:                                   // t
            try expect(literal: "true")
            return .bool(true)
        case 0x66:                                   // f
            try expect(literal: "false")
            return .bool(false)
        case 0x6E:                                   // n
            try expect(literal: "null")
            return .null
        default:
            return try parseNumber()
        }
    }

    mutating func parseObject(depth: Int) throws -> JSONValue {
        offset += 1                                  // 吃掉 '{'
        var out: [String: JSONValue] = [:]
        skipWhitespace()
        if offset < bytes.count && bytes[offset] == 0x7D {
            offset += 1
            return .object(out)
        }
        while true {
            skipWhitespace()
            guard offset < bytes.count, bytes[offset] == 0x22 else {
                throw JSONParseError.unexpectedCharacter(offset: offset)
            }
            let key = try parseString()
            skipWhitespace()
            guard offset < bytes.count, bytes[offset] == 0x3A else {
                throw JSONParseError.unexpectedCharacter(offset: offset)
            }
            offset += 1                              // 吃掉 ':'
            skipWhitespace()
            out[key] = try parseValue(depth: depth + 1)
            skipWhitespace()
            guard offset < bytes.count else { throw JSONParseError.unexpectedEnd }
            if bytes[offset] == 0x2C {                // ,
                offset += 1
                continue
            }
            if bytes[offset] == 0x7D {                // }
                offset += 1
                return .object(out)
            }
            throw JSONParseError.unexpectedCharacter(offset: offset)
        }
    }

    mutating func parseArray(depth: Int) throws -> JSONValue {
        offset += 1                                  // 吃掉 '['
        var out: [JSONValue] = []
        skipWhitespace()
        if offset < bytes.count && bytes[offset] == 0x5D {
            offset += 1
            return .array(out)
        }
        while true {
            skipWhitespace()
            out.append(try parseValue(depth: depth + 1))
            skipWhitespace()
            guard offset < bytes.count else { throw JSONParseError.unexpectedEnd }
            if bytes[offset] == 0x2C {                // ,
                offset += 1
                continue
            }
            if bytes[offset] == 0x5D {                // ]
                offset += 1
                return .array(out)
            }
            throw JSONParseError.unexpectedCharacter(offset: offset)
        }
    }

    mutating func parseString() throws -> String {
        offset += 1                                  // 吃掉开头的 '"'
        var buffer: [UInt8] = []
        while true {
            guard offset < bytes.count else { throw JSONParseError.unexpectedEnd }
            let b = bytes[offset]
            if b == 0x22 {                            // 收尾的 '"'
                offset += 1
                guard let text = String(bytes: buffer, encoding: .utf8) else {
                    throw JSONParseError.invalidString(offset: offset)
                }
                return text
            }
            if b == 0x5C {                            // '\'
                offset += 1
                guard offset < bytes.count else { throw JSONParseError.unexpectedEnd }
                let escaped = bytes[offset]
                offset += 1
                switch escaped {
                case 0x22: buffer.append(0x22)        // \"
                case 0x5C: buffer.append(0x5C)        // \\
                case 0x2F: buffer.append(0x2F)        // \/
                case 0x62: buffer.append(0x08)        // \b
                case 0x66: buffer.append(0x0C)        // \f
                case 0x6E: buffer.append(0x0A)        // \n
                case 0x72: buffer.append(0x0D)        // \r
                case 0x74: buffer.append(0x09)        // \t
                case 0x75:                            // \uXXXX
                    let first = try parseHex4()
                    var scalarValue = UInt32(first)
                    if first >= 0xD800 && first <= 0xDBFF {
                        // 高位代理 ⇒ 必须紧跟一个低位代理
                        guard offset + 1 < bytes.count,
                              bytes[offset] == 0x5C,
                              bytes[offset + 1] == 0x75 else {
                            throw JSONParseError.invalidString(offset: offset)
                        }
                        offset += 2
                        let second = try parseHex4()
                        guard second >= 0xDC00 && second <= 0xDFFF else {
                            throw JSONParseError.invalidString(offset: offset)
                        }
                        scalarValue = 0x10000
                            + (UInt32(first - 0xD800) << 10)
                            + UInt32(second - 0xDC00)
                    }
                    guard let scalar = Unicode.Scalar(scalarValue) else {
                        throw JSONParseError.invalidString(offset: offset)
                    }
                    buffer.append(contentsOf: Array(String(scalar).utf8))
                default:
                    throw JSONParseError.unexpectedCharacter(offset: offset - 1)
                }
                continue
            }
            if b < 0x20 {
                // 控制字符必须转义
                throw JSONParseError.unexpectedCharacter(offset: offset)
            }
            buffer.append(b)
            offset += 1
        }
    }

    mutating func parseHex4() throws -> UInt16 {
        guard offset + 4 <= bytes.count else { throw JSONParseError.unexpectedEnd }
        var value: UInt16 = 0
        for _ in 0..<4 {
            let c = bytes[offset]
            let digit: UInt16
            switch c {
            case 0x30...0x39: digit = UInt16(c - 0x30)
            case 0x61...0x66: digit = UInt16(c - 0x61 + 10)
            case 0x41...0x46: digit = UInt16(c - 0x41 + 10)
            default: throw JSONParseError.invalidString(offset: offset)
            }
            value = value << 4 | digit
            offset += 1
        }
        return value
    }

    /// 解析数字字面量。
    ///
    /// ⭐ **int / double 的判定只看字面量**：出现 `.` / `e` / `E` ⇒ double；
    ///    否则按 `Int` 解析（装不下 ⇒ double）。
    ///    ⇒ 与固件 ArduinoJson `is<int>()` 的判定完全一致。
    mutating func parseNumber() throws -> JSONValue {
        let start = offset
        if offset < bytes.count && bytes[offset] == 0x2D {    // '-'
            offset += 1
        }
        var sawDigit = false
        var isIntegerLiteral = true
        while offset < bytes.count {
            let c = bytes[offset]
            if c >= 0x30 && c <= 0x39 {                        // '0'...'9'
                sawDigit = true
                offset += 1
                continue
            }
            if c == 0x2E || c == 0x65 || c == 0x45 {           // '.' 'e' 'E'
                isIntegerLiteral = false
                offset += 1
                continue
            }
            if c == 0x2B || c == 0x2D {                        // '+' '-'（只可能出现在指数里）
                guard !isIntegerLiteral else {
                    throw JSONParseError.invalidNumber(offset: offset)
                }
                offset += 1
                continue
            }
            break
        }
        guard sawDigit else { throw JSONParseError.invalidNumber(offset: start) }
        let text = String(decoding: bytes[start..<offset], as: UTF8.self)
        if isIntegerLiteral, let intValue = Int(text) {
            return .int(intValue)
        }
        guard let doubleValue = Double(text) else {
            throw JSONParseError.invalidNumber(offset: start)
        }
        return .double(doubleValue)
    }

    mutating func expect(literal: String) throws {
        let expected = Array(literal.utf8)
        guard offset + expected.count <= bytes.count else {
            throw JSONParseError.unexpectedEnd
        }
        for (i, c) in expected.enumerated() where bytes[offset + i] != c {
            throw JSONParseError.unexpectedCharacter(offset: offset + i)
        }
        offset += expected.count
    }
}

// MARK: - 序列化

extension JSONValue {

    /// 序列化回 JSON 文本。
    ///
    /// ⭐ **整数不会变成 `10.0`**（`.int` 直接写十进制；`.double` 至少保留一位小数）。
    public func serialized() -> String {
        var out = ""
        write(into: &out)
        return out
    }

    /// 序列化回 UTF-8 字节。
    public func serializedData() -> Data {
        Data(serialized().utf8)
    }

    private func write(into out: inout String) {
        switch self {
        case .object(let dictionary):
            out += "{"
            var first = true
            for key in dictionary.keys.sorted() {
                if !first { out += "," }
                first = false
                out += JSONValue.escape(key)
                out += ":"
                if let value = dictionary[key] {
                    value.write(into: &out)
                }
            }
            out += "}"
        case .array(let items):
            out += "["
            for (index, item) in items.enumerated() {
                if index > 0 { out += "," }
                item.write(into: &out)
            }
            out += "]"
        case .string(let text):
            out += JSONValue.escape(text)
        case .int(let value):
            out += String(value)
        case .double(let value):
            if value.isFinite {
                var text = String(value)
                if !text.contains(".") && !text.contains("e") && !text.contains("E") {
                    text += ".0"
                }
                out += text
            } else {
                out += "null"
            }
        case .bool(let flag):
            out += flag ? "true" : "false"
        case .null:
            out += "null"
        }
    }

    /// JSON 字符串转义（只转义必须转义的，其余原样按 UTF-8 输出）。
    static func escape(_ text: String) -> String {
        var out = "\""
        for scalar in text.unicodeScalars {
            switch scalar.value {
            case 0x22: out += "\\\""
            case 0x5C: out += "\\\\"
            case 0x0A: out += "\\n"
            case 0x0D: out += "\\r"
            case 0x09: out += "\\t"
            case 0x08: out += "\\b"
            case 0x0C: out += "\\f"
            default:
                if scalar.value < 0x20 {
                    out += String(format: "\\u%04X", scalar.value)
                } else {
                    out.unicodeScalars.append(scalar)
                }
            }
        }
        out += "\""
        return out
    }
}
