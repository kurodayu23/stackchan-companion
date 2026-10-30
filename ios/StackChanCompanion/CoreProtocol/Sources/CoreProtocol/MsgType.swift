import Foundation

/// 官方协议消息类型表（**25 项**）。
///
/// ⭐ 事实来源：`docs/spec/03-通信链路预设与数据契约.md` §2.2
///    （原始出处：官方 Flutter App `app/lib/model/msg_type.dart`，该文件注释明写
///    "Matches the raw values used on iOS" —— 官方本来就有 iOS 版，我们的编号与之逐字对齐）
///
/// ⚠️ **文档口径差异（公开订正）**：§2.2 的小节标题写「消息类型表（**24 个**，官方 Dart 枚举全量）」，
///    但**表里实际列了 25 项**（0x01–0x1B 去掉 0x08 与 0x0F = 25）。
///    ⇒ 本实现**以表内容为准（25 项）**；标题口径属于 `docs/` 的所有权范围，本仓库不擅自改。
///
/// ⭐ 固件侧编号同样对齐（`docs/spec/03` §2.5.6），
///    例外是 `0x15 / 0x16 / 0x17` 三个类型**固件没有实现**（收到后落到 `default: break` 静默丢弃）。
///
/// ⭐ 本文件是纯值类型，不依赖任何 target（`docs/research/58-iOS端架构决策.md` §2）。
public enum MsgType: UInt8, CaseIterable, Sendable, Hashable {

    // MARK: - 官方 24 项（编号与官方 Dart 枚举逐字一致）

    /// 音频（控制面裸包）。
    case opus = 0x01
    /// 摄像头帧。
    case jpeg = 0x02
    /// ⭐ 控制表情（3 元素 × 5 参数）。
    case controlAvatar = 0x03
    /// ⭐ 控制动作（双舵机）。
    case controlMotion = 0x04
    /// 摄像头开。
    case onCamera = 0x05
    /// 摄像头关。
    case offCamera = 0x06
    /// ⭐ 文本消息（对话主通道）。
    case textMessage = 0x07
    /// 设备主动呼叫 App（"它要找你"）。
    case requestCall = 0x09
    /// 通话应答：拒绝。
    case refuseCall = 0x0A
    /// 通话应答：同意。
    case agreeCall = 0x0B
    /// 通话应答：挂断。
    case hangupCall = 0x0C
    /// 更新设备名。
    case updateDeviceName = 0x0D
    /// 读设备名。
    case getDeviceName = 0x0E
    /// ⭐ 保活 / LAN 探测请求。
    case ping = 0x10
    /// ⭐ 保活 / LAN 探测应答。
    case pong = 0x11
    /// 手机投屏开（设备把画面推到手机）。
    case onPhoneScreen = 0x12
    /// 手机投屏关。
    case offPhoneScreen = 0x13
    /// ⭐ 舞蹈 / 关键帧时间轴（动作合成主通道）。
    case dance = 0x14
    /// 读回真实姿态 —— ⛔ **固件未实现**。
    case getAvatarPosture = 0x15
    /// 设备离线通知 —— ⛔ **固件未实现**。
    case deviceOffline = 0x16
    /// 设备上线通知 —— ⛔ **固件未实现**。
    case deviceOnline = 0x17
    /// 音频开。
    case onAudio = 0x18
    /// 音频关。
    case offAudio = 0x19
    /// 拍照。
    case aimedTakePhoto = 0x1A
    /// ⭐ 告诉设备"我的局域网地址是 X"（LAN 链路握手）。
    case appLanAddress = 0x1B

    // MARK: - 别名（同一 rawValue 的描述性叫法，便于阅读）

    /// 别名：`ping` 在固件枚举里叫 `HeartbeatPing`。
    public static let heartBeatPing = MsgType.ping
    /// 别名：`dance` 在固件侧叫 `DanceSequence`。
    public static let danceSequence = MsgType.dance
    /// 别名：`pong` 在固件枚举里叫 `HeartbeatPong`。
    public static let heartBeatPong = MsgType.pong

    // MARK: - 能力标记

    /// 固件是否实现了这个类型。
    ///
    /// ⛔ `0x15 / 0x16 / 0x17` 固件**跳过**，收到落到 `default: break` 静默丢弃。
    /// 出处：`docs/spec/03` §2.5.6 + §2.4（固件 `DataType` 枚举跳过 0x15）
    public var isImplementedByDevice: Bool {
        switch self {
        case .getAvatarPosture, .deviceOffline, .deviceOnline:
            return false
        default:
            return true
        }
    }

    /// App 侧当前实现的子集。
    ///
    /// 出处：`docs/research/58-iOS端架构决策.md` §8 预设项 4
    /// —— CoreProtocol 只实现 `0x03/0x04/0x07/0x14/0x1B/0x10/0x11/0x12/0x18/0x19`，
    ///    **过滤 `0x15/0x16/0x17`**（设备不实现）。
    public static let appImplemented: Set<MsgType> = [
        .controlAvatar, .controlMotion, .textMessage, .dance, .appLanAddress,
        .ping, .pong, .onPhoneScreen, .offPhoneScreen,
        .onAudio, .offAudio
    ]

    /// 本 App 是否实现了这个类型。
    public var isImplementedByApp: Bool {
        MsgType.appImplemented.contains(self)
    }

    /// 线上/日志用的稳定短名（与官方 Dart 枚举同名）。
    public var wireName: String {
        switch self {
        case .opus: return "opus"
        case .jpeg: return "jpeg"
        case .controlAvatar: return "controlAvatar"
        case .controlMotion: return "controlMotion"
        case .onCamera: return "onCamera"
        case .offCamera: return "offCamera"
        case .textMessage: return "textMessage"
        case .requestCall: return "requestCall"
        case .refuseCall: return "refuseCall"
        case .agreeCall: return "agreeCall"
        case .hangupCall: return "hangupCall"
        case .updateDeviceName: return "updateDeviceName"
        case .getDeviceName: return "getDeviceName"
        case .ping: return "ping"
        case .pong: return "pong"
        case .onPhoneScreen: return "onPhoneScreen"
        case .offPhoneScreen: return "offPhoneScreen"
        case .dance: return "dance"
        case .getAvatarPosture: return "getAvatarPosture"
        case .deviceOffline: return "deviceOffline"
        case .deviceOnline: return "deviceOnline"
        case .onAudio: return "onAudio"
        case .offAudio: return "offAudio"
        case .aimedTakePhoto: return "aimedTakePhoto"
        case .appLanAddress: return "appLanAddress"
        }
    }
}
