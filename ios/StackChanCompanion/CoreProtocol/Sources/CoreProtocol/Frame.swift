import Foundation

/// 远程 WS 帧格式：`[Type(1)][Length(4 BE)][Payload]`，**Payload 从 offset 5 开始**。
///
/// ⭐ 事实来源：`docs/spec/03-通信链路预设与数据契约.md` §2.3
///    —— 「远程 WS（经服务器）帧头 = 5 字节 `[type:1][length:4 BE][payload]`」
///    —— 原始出处：官方 Flutter App `app_state.dart:275-279`
///
/// ⚠️ 与 LAN 直连的 **20 字节帧头不能混用**
///    （`[0x53 0x43][ver:1][type:1][…][session:8][seq:4][len:2][payload]`，
///    magic = `0x53 0x43`("SC")，出处 `docs/spec/03` §2.3）。
///    本文件**只实现 5 字节远程帧**；LAN 帧属于独立传输层，不在本文件范围内。
public struct Frame: Equatable, Sendable {

    /// 帧头长度：1 字节 type + 4 字节 length。
    public static let headerSize = 5

    /// 单帧 payload 的自设上限（防畸形 length 触发巨额分配）。
    ///
    /// ⚠️ **【自研设定】** —— 官方协议与仓库文档**没有**给远程帧的 payload 上限
    ///    （`docs/spec/03` §2.3 只定义了帧头）。此处取 16 MiB 作为防御性上限，
    ///    远大于官方实际用法（jpeg 帧已被官方压到 320×240，见 `docs/spec/03` §4 第 7 条）。
    public static let maxPayloadSize = 16 * 1024 * 1024

    /// 帧类型。
    public let type: MsgType

    /// 帧载荷。
    public let payload: Data

    public init(type: MsgType, payload: Data = Data()) {
        self.type = type
        self.payload = payload
    }

    // MARK: - 编码

    /// 编码成线上的字节序列。
    public func encoded() -> Data {
        var out = Data(capacity: Frame.headerSize + payload.count)
        out.append(type.rawValue)
        // length：4 字节大端（Big Endian）
        let length = UInt32(payload.count)
        out.append(UInt8((length >> 24) & 0xFF))
        out.append(UInt8((length >> 16) & 0xFF))
        out.append(UInt8((length >> 8) & 0xFF))
        out.append(UInt8(length & 0xFF))
        out.append(payload)
        return out
    }

    // MARK: - 解码

    /// 帧解码失败的原因。
    public enum DecodeError: Error, Equatable, Sendable {
        /// 不足 5 字节帧头。
        case headerTooShort(byteCount: Int)
        /// 声明长度超过实际可用字节数（截断帧）。
        case payloadTruncated(declared: Int, available: Int)
        /// 声明长度超过自设上限。
        case payloadTooLarge(declared: Int, limit: Int)
        /// 帧头的 type 字节不是官方 24 项之一。
        case unknownType(raw: UInt8)
    }

    /// 解码一帧。**必须整帧齐全**，不足即抛错（不做"尽力而为"的截断解析）。
    ///
    /// - Throws: ``DecodeError``
    public init(decoding data: Data) throws {
        guard data.count >= Frame.headerSize else {
            throw DecodeError.headerTooShort(byteCount: data.count)
        }
        let bytes = [UInt8](data)
        let declared = (UInt32(bytes[1]) << 24)
            | (UInt32(bytes[2]) << 16)
            | (UInt32(bytes[3]) << 8)
            | UInt32(bytes[4])
        guard declared <= UInt32(Frame.maxPayloadSize) else {
            throw DecodeError.payloadTooLarge(declared: Int(declared), limit: Frame.maxPayloadSize)
        }
        let available = data.count - Frame.headerSize
        guard available >= Int(declared) else {
            throw DecodeError.payloadTruncated(declared: Int(declared), available: available)
        }
        guard let type = MsgType(rawValue: bytes[0]) else {
            throw DecodeError.unknownType(raw: bytes[0])
        }
        self.type = type
        // ⚠️ `Data.subdata(in:)` 用的是**接收者的绝对索引**。
        //    `Data` 的切片会**保留原索引空间**（`someData[10..<100]` 的 `startIndex` 是 10），
        //    这里如果直接写 `Frame.headerSize..<…` 就会越界崩溃 ⇒ 必须相对 `startIndex` 取。
        let lower = data.startIndex + Frame.headerSize
        let upper = data.startIndex + Frame.headerSize + Int(declared)
        self.payload = data.subdata(in: lower..<upper)
    }

    /// 静态解码入口。
    public static func decode(_ data: Data) throws -> Frame {
        try Frame(decoding: data)
    }
}

/// 字节流解帧器：把可能粘包/拆包的字节流切成一个个完整帧。
///
/// ⭐ WebSocket 二进制帧可能一次收到多帧、或半帧，这里做**最小可用**的粘包处理：
///    缓冲区不足一帧就等下一次追加；够了就切一帧，剩余留在缓冲区。
///
/// ⚠️ 【自研设定】—— 仓库文档没有规定粘包策略（`docs/spec/03` §2.3 只定义帧头）。
public struct FrameBuffer {

    private var buffer: Data = Data()

    public init() {}

    /// 当前缓冲区里还没切出完整帧的字节数。
    public var pendingByteCount: Int { buffer.count }

    /// 追加收到的字节。
    public mutating func append(_ data: Data) {
        buffer.append(data)
    }

    /// 尝试切出下一个完整帧。
    /// - Returns: 切出成功返回帧；数据不足返回 `nil`；数据非法抛错。
    public mutating func next() throws -> Frame? {
        guard buffer.count >= Frame.headerSize else { return nil }
        let bytes = [UInt8](buffer)
        let declared = (UInt32(bytes[1]) << 24)
            | (UInt32(bytes[2]) << 16)
            | (UInt32(bytes[3]) << 8)
            | UInt32(bytes[4])
        guard declared <= UInt32(Frame.maxPayloadSize) else {
            throw Frame.DecodeError.payloadTooLarge(declared: Int(declared), limit: Frame.maxPayloadSize)
        }
        let total = Frame.headerSize + Int(declared)
        guard buffer.count >= total else { return nil }
        let frameData = buffer.prefix(total)
        buffer.removeFirst(total)
        return try Frame(decoding: frameData)
    }

    /// 切出所有当前可切的帧。
    public mutating func drain() throws -> [Frame] {
        var out: [Frame] = []
        while let frame = try next() {
            out.append(frame)
        }
        return out
    }
}
