import XCTest
@testable import CoreProtocol

/// 帧编解码单测。
///
/// ⭐ 规则来源：`docs/spec/03` §2.3 —— 远程 WS 帧头 `[type:1][length:4 BE][payload]`
final class FrameTests: XCTestCase {

    // MARK: - 编码

    func testEncodedLayoutIsTypeThenLengthBigEndianThenPayload() {
        let frame = Frame(type: .textMessage, payload: Data([0x41, 0x42, 0x43]))
        let bytes = [UInt8](frame.encoded())

        XCTAssertEqual(bytes.count, 5 + 3)
        XCTAssertEqual(bytes[0], 0x07, "第 1 字节必须是 type")
        XCTAssertEqual(bytes[1], 0x00, "length 是 4 字节大端")
        XCTAssertEqual(bytes[2], 0x00)
        XCTAssertEqual(bytes[3], 0x00)
        XCTAssertEqual(bytes[4], 0x03, "length = 3")
        XCTAssertEqual(Array(bytes[5...]), [0x41, 0x42, 0x43], "payload 从 offset 5 开始")
    }

    func testEncodedLengthIsBigEndianForMultiBytePayload() {
        let payload = Data(repeating: 0x5A, count: 0x0102)  // 258 字节
        let bytes = [UInt8](Frame(type: .dance, payload: payload).encoded())

        XCTAssertEqual(bytes[0], 0x14)
        XCTAssertEqual(bytes[1], 0x00)
        XCTAssertEqual(bytes[2], 0x00)
        XCTAssertEqual(bytes[3], 0x01)
        XCTAssertEqual(bytes[4], 0x02, "0x0102 = 258，必须按大端写出")
        XCTAssertEqual(bytes.count, 5 + 258)
    }

    func testEmptyPayloadIsAllowed() {
        let frame = Frame(type: .ping)
        XCTAssertEqual([UInt8](frame.encoded()), [0x10, 0x00, 0x00, 0x00, 0x00])
    }

    // MARK: - 解码

    func testRoundTripPreservesTypeAndPayload() throws {
        let original = Frame(type: .controlMotion, payload: Data("{\"a\":1}".utf8))
        let decoded = try Frame.decode(original.encoded())

        XCTAssertEqual(decoded.type, .controlMotion)
        XCTAssertEqual(decoded.payload, original.payload)
    }

    func testRoundTripForEveryMsgType() throws {
        for type in MsgType.allCases {
            let original = Frame(type: type, payload: Data([0x00, 0xFF]))
            let decoded = try Frame.decode(original.encoded())
            XCTAssertEqual(decoded.type, type)
            XCTAssertEqual(decoded.payload, original.payload)
        }
    }

    func testDecodingShorterThanHeaderThrows() {
        XCTAssertThrowsError(try Frame.decode(Data([0x07, 0x00]))) { error in
            XCTAssertEqual(error as? Frame.DecodeError, .headerTooShort(byteCount: 2))
        }
    }

    func testDecodingEmptyDataThrows() {
        XCTAssertThrowsError(try Frame.decode(Data())) { error in
            XCTAssertEqual(error as? Frame.DecodeError, .headerTooShort(byteCount: 0))
        }
    }

    func testDecodingTruncatedPayloadThrows() {
        // 声明 3 字节，只给了 1 字节
        let bytes = Data([0x07, 0x00, 0x00, 0x00, 0x03, 0x41])
        XCTAssertThrowsError(try Frame.decode(bytes)) { error in
            XCTAssertEqual(error as? Frame.DecodeError, .payloadTruncated(declared: 3, available: 1))
        }
    }

    func testDecodingUnknownTypeThrows() {
        // 0x08 不在官方 24 项之内
        let bytes = Data([0x08, 0x00, 0x00, 0x00, 0x00])
        XCTAssertThrowsError(try Frame.decode(bytes)) { error in
            XCTAssertEqual(error as? Frame.DecodeError, .unknownType(raw: 0x08))
        }
    }

    func testDecodingOversizedDeclaredLengthThrows() {
        var bytes = Data([0x07])
        let huge = UInt32(Frame.maxPayloadSize + 1)
        bytes.append(UInt8((huge >> 24) & 0xFF))
        bytes.append(UInt8((huge >> 16) & 0xFF))
        bytes.append(UInt8((huge >> 8) & 0xFF))
        bytes.append(UInt8(huge & 0xFF))
        XCTAssertThrowsError(try Frame.decode(bytes)) { error in
            guard case .payloadTooLarge = (error as? Frame.DecodeError) else {
                return XCTFail("应当抛 payloadTooLarge，实际 \(error)")
            }
        }
    }

    // MARK: - 流式解帧（粘包 / 半包）

    func testFrameBufferYieldsNothingWhenIncomplete() throws {
        var buffer = FrameBuffer()
        buffer.append(Data([0x07, 0x00, 0x00, 0x00]))
        XCTAssertNil(try buffer.next(), "帧头不全时不应产出帧")
    }

    func testFrameBufferSplitsConcatenatedFrames() throws {
        let a = Frame(type: .ping, payload: Data())
        let b = Frame(type: .pong, payload: Data([0x01]))
        var buffer = FrameBuffer()
        buffer.append(a.encoded())
        buffer.append(b.encoded())

        let frames = try buffer.drain()
        XCTAssertEqual(frames.count, 2)
        XCTAssertEqual(frames[0].type, .ping)
        XCTAssertEqual(frames[1].type, .pong)
        XCTAssertEqual(frames[1].payload, Data([0x01]))
        XCTAssertEqual(buffer.pendingByteCount, 0)
    }

    func testFrameBufferHandlesPartialFrameAcrossAppends() throws {
        let original = Frame(type: .textMessage, payload: Data("hello".utf8))
        let encoded = original.encoded()
        var buffer = FrameBuffer()
        buffer.append(encoded.prefix(3))
        XCTAssertNil(try buffer.next())
        buffer.append(encoded.dropFirst(3))

        let frames = try buffer.drain()
        XCTAssertEqual(frames.count, 1)
        XCTAssertEqual(frames[0].payload, Data("hello".utf8))
    }

    /// ⭐ 回归用例：`Data` 的切片**保留原索引空间**（`startIndex != 0`），
    ///    解码必须相对 `startIndex` 取 payload，否则会越界崩溃。
    func testDecodingSliceWithNonZeroStartIndex() throws {
        let payload = Data("sliced-payload".utf8)
        let encoded = Frame(type: .textMessage, payload: payload).encoded()

        // 造一个带 10 字节前缀的缓冲区，再切出帧那一段
        var big = Data([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22, 0x33, 0x44])
        big.append(encoded)
        let slice = big[10..<(10 + encoded.count)]

        // ⚠️ 守门断言：Data 切片应当保留原索引空间。
        //    若哪天 Foundation 改成把切片重基到 0，本用例就覆盖不到那个坑了 —— 那时要改写用例。
        XCTAssertNotEqual(slice.startIndex, 0,
                          "Data 切片应当保留原索引空间；若 Foundation 行为变了，本用例需要改写")

        let decoded = try Frame.decode(slice)
        XCTAssertEqual(decoded.type, .textMessage)
        XCTAssertEqual(decoded.payload, payload)
        XCTAssertEqual(decoded.payload, encoded.subdata(in: 5..<encoded.count))
    }

    /// ⭐ 回归用例：连续多帧 + 半帧，`drain()` 切出来的帧必须与逐个编码的字节完全一致。
    func testFrameBufferDrainMatchesIndividuallyEncodedFrames() throws {
        let frames = [
            Frame(type: .ping, payload: Data()),
            Frame(type: .pong, payload: Data([0x01, 0x02])),
            Frame(type: .textMessage, payload: Data("stackchan".utf8))
        ]
        let encoded = frames.map { $0.encoded() }

        var buffer = FrameBuffer()
        buffer.append(encoded[0])
        buffer.append(encoded[1])
        buffer.append(encoded[2].prefix(4))   // 半帧

        let first = try buffer.drain()
        XCTAssertEqual(first.count, 2, "半帧不完整时不应产出第三帧")
        XCTAssertEqual(first[0].type, .ping)
        XCTAssertEqual(first[1].type, .pong)
        XCTAssertEqual(first.map { $0.encoded() }, [encoded[0], encoded[1]],
                       "切出来的帧必须与逐个编码的字节完全一致")

        buffer.append(encoded[2].dropFirst(4))  // 补齐半帧
        let second = try buffer.drain()
        XCTAssertEqual(second.count, 1)
        XCTAssertEqual(second[0].type, .textMessage)
        XCTAssertEqual(second[0].encoded(), encoded[2],
                       "切出来的帧必须与逐个编码的字节完全一致")
        XCTAssertEqual(buffer.pendingByteCount, 0)
    }

    // MARK: - 消息类型表

    func testMsgTypeRawValuesMatchOfficialTable() {
        // 出处：docs/spec/03 §2.2
        XCTAssertEqual(MsgType.opus.rawValue, 0x01)
        XCTAssertEqual(MsgType.jpeg.rawValue, 0x02)
        XCTAssertEqual(MsgType.controlAvatar.rawValue, 0x03)
        XCTAssertEqual(MsgType.controlMotion.rawValue, 0x04)
        XCTAssertEqual(MsgType.onCamera.rawValue, 0x05)
        XCTAssertEqual(MsgType.offCamera.rawValue, 0x06)
        XCTAssertEqual(MsgType.textMessage.rawValue, 0x07)
        XCTAssertEqual(MsgType.requestCall.rawValue, 0x09)
        XCTAssertEqual(MsgType.refuseCall.rawValue, 0x0A)
        XCTAssertEqual(MsgType.agreeCall.rawValue, 0x0B)
        XCTAssertEqual(MsgType.hangupCall.rawValue, 0x0C)
        XCTAssertEqual(MsgType.updateDeviceName.rawValue, 0x0D)
        XCTAssertEqual(MsgType.getDeviceName.rawValue, 0x0E)
        XCTAssertEqual(MsgType.ping.rawValue, 0x10)
        XCTAssertEqual(MsgType.pong.rawValue, 0x11)
        XCTAssertEqual(MsgType.onPhoneScreen.rawValue, 0x12)
        XCTAssertEqual(MsgType.offPhoneScreen.rawValue, 0x13)
        XCTAssertEqual(MsgType.dance.rawValue, 0x14)
        XCTAssertEqual(MsgType.getAvatarPosture.rawValue, 0x15)
        XCTAssertEqual(MsgType.deviceOffline.rawValue, 0x16)
        XCTAssertEqual(MsgType.deviceOnline.rawValue, 0x17)
        XCTAssertEqual(MsgType.onAudio.rawValue, 0x18)
        XCTAssertEqual(MsgType.offAudio.rawValue, 0x19)
        XCTAssertEqual(MsgType.aimedTakePhoto.rawValue, 0x1A)
        XCTAssertEqual(MsgType.appLanAddress.rawValue, 0x1B)
        XCTAssertEqual(MsgType.allCases.count, 25, "官方消息类型表共 25 项（docs/spec/03 §2.2 的表内容；小节标题写的 24 是文档口径差异）")
    }

    func testFirmwareSkippedTypesAreMarked() {
        // docs/spec/03 §2.5.6：固件跳过 0x15 / 0x16 / 0x17
        XCTAssertFalse(MsgType.getAvatarPosture.isImplementedByDevice)
        XCTAssertFalse(MsgType.deviceOffline.isImplementedByDevice)
        XCTAssertFalse(MsgType.deviceOnline.isImplementedByDevice)
        XCTAssertTrue(MsgType.dance.isImplementedByDevice)
        XCTAssertFalse(MsgType.getAvatarPosture.isImplementedByApp)
    }
}
