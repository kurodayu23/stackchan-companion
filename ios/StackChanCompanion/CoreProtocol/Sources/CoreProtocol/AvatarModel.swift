import Foundation

/// 表情元素参数：3 元素（leftEye / rightEye / mouth）× 5 参数。
///
/// ⭐ 事实来源：`docs/spec/03` §2.5.1
///    ```json
///    { "leftEye":  { "x": int, "y": int, "rotation": int, "weight": int, "size": int },
///      "rightEye": { ... },
///      "mouth":    { ... } }
///    ```
///    量纲（`docs/research/53` §3.2）：
///    `x`/`y` ∈ [-100,100]｜`rotation` ∈ 0.1°（3600 = 360°）｜`weight` ∈ [0,100]｜`size` ∈ [-100,100]
///
/// ⚠️ 固件侧逐字段 `is<int>()` 判断，**未知/错类型字段静默忽略**
///    （`docs/research/53` §3.1）⇒ 所以本地必须有 schema 校验（`docs/research/53` §7 事实 2）。
public struct AvatarFeature: Equatable, Sendable, Codable {

    /// 归一化横坐标（-100 ~ 100）。像素换算见 ``AvatarCoordinate``。
    public var x: Int
    /// 归一化纵坐标（-100 ~ 100）。
    public var y: Int
    /// 旋转角，单位 **0.1 度**。
    public var rotation: Int
    /// 强度 0 ~ 100。极性见 ``WeightPolarity``。
    public var weight: Int
    /// 尺寸缩放（-100 ~ 100，0 = 正常）。
    public var size: Int

    public init(x: Int = 0, y: Int = 0, rotation: Int = 0, weight: Int = 0, size: Int = 0) {
        self.x = x
        self.y = y
        self.rotation = rotation
        self.weight = weight
        self.size = size
    }
}

/// 一个表情的 3 个元素。
///
/// ⭐ 出处：`docs/spec/03` §2.4（`ExpressionData` 的 3 个字段与官方 15 维参数结构一致）
///    `docs/spec/06-表情参数模型.md` §1.1（3 元素 × 5 字段的完整定义）
public struct AvatarModel: Equatable, Sendable, Codable {

    public var leftEye: AvatarFeature
    public var rightEye: AvatarFeature
    public var mouth: AvatarFeature

    public init(leftEye: AvatarFeature = AvatarFeature(),
                rightEye: AvatarFeature = AvatarFeature(),
                mouth: AvatarFeature = AvatarFeature()) {
        self.leftEye = leftEye
        self.rightEye = rightEye
        self.mouth = mouth
    }

    /// **规范默认值**：任何端在"没有下发任何表情"时都必须渲染成这一组。
    ///
    /// ⭐ 出处：`docs/spec/06-表情参数模型.md` §3
    ///    （= 固件构造函数自己的初始状态：眼睛 `setSize(0)` / `setWeight(100)`、嘴 `setWeight(0)`，
    ///    **不是**我们另选的一套）
    public static let restingDefault = AvatarModel(
        leftEye: AvatarFeature(x: 0, y: 0, rotation: 0, weight: 100, size: 0),
        rightEye: AvatarFeature(x: 0, y: 0, rotation: 0, weight: 100, size: 0),
        mouth: AvatarFeature(x: 0, y: 0, rotation: 0, weight: 0, size: 0)
    )
}

/// 舵机目标：角度 + 速度参数。
///
/// ⭐ 出处：`docs/spec/03` §2.4
///    `{"type":"bleMotion","pitchServo":{"angle":N,"speed":500},"yawServo":{"angle":N,"speed":500}}`
/// ⚠️ `speed` 实际是**弹簧刚度**，不是舵机速度（`docs/research/53` §5.4）。
public struct ServoTarget: Equatable, Sendable, Codable {

    /// 目标角，单位 **0.1 度**。
    public var angle: Int
    /// 速度参数（固件侧实际当作弹簧刚度）。
    public var speed: Int

    public init(angle: Int = 0, speed: Int = 0) {
        self.angle = angle
        self.speed = speed
    }
}

/// 双舵机目标姿态。
public struct MotionModel: Equatable, Sendable, Codable {

    public var yawServo: ServoTarget
    public var pitchServo: ServoTarget

    public init(yawServo: ServoTarget = ServoTarget(),
                pitchServo: ServoTarget = ServoTarget()) {
        self.yawServo = yawServo
        self.pitchServo = pitchServo
    }
}

// MARK: - 舵机限位

/// 舵机限位（0.1 度单位）。
///
/// ⭐ 出处：`docs/spec/03` §2.4
///    —— 固件限幅 `yaw: Vector2i(-1280, 1280)`、`pitch: Vector2i(30, 870)`
///    —— 即 `yaw ∈ [-128.0°, +128.0°]`、`pitch ∈ [3.0°, 87.0°]`
///    —— 原始出处：`firmware/main/hal/hal_servo.cpp` `servo_init()`
public enum ServoLimit {

    /// 偏航（左右）限位，0.1 度。
    public static let yawRange = -1280...1280
    /// 俯仰（上下）限位，0.1 度。
    public static let pitchRange = 30...870

    /// 0.1 度 → 度。
    public static func degrees(_ raw: Int) -> Double {
        Double(raw) / 10.0
    }

    /// 判断一个偏航角是否在限位内。
    public static func isValidYaw(_ raw: Int) -> Bool { yawRange.contains(raw) }
    /// 判断一个俯仰角是否在限位内。
    public static func isValidPitch(_ raw: Int) -> Bool { pitchRange.contains(raw) }
}

// MARK: - weight 极性

/// `weight` 的极性常量。
///
/// ⭐ 事实链（`docs/research/53` §2 情绪映射表，原始出处 `firmware/main/stackchan/avatar/skins/default/eyes.cpp:87-120`）：
///
/// | Emotion | eye weight | 视觉含义 |
/// |---|---|---|
/// | Neutral | 100 | 全睁、平视 |
/// | Happy | 72 | 眯眼上斜 |
/// | Angry | 70 | 眼角下压 |
/// | Sad | 70 | 眼角上挑 |
/// | Doubt | 75 | 半眯 |
/// | Sleepy | 35 | 几乎闭 |
///
/// ⇒ **眼睛 weight 越大 = 越睁开**（Neutral=100 全睁，Sleepy=35 几乎闭）。
///    固件参数名叫"眼睑下沉"，但**数值方向是反的** —— 这是最容易写反的一处。
///
/// ⭐ 嘴的 weight 越大 = 越张开（`mouth` 的 weight 语义 = 开合，`docs/research/53` §3.2；
///    固件出处 `firmware/main/stackchan/avatar/skins/default/mouth.cpp:55-59`；
///    `SpeakingModifier` 随机改写嘴 weight 实现开合，`docs/research/53` §6）。
///
/// ⇒ 两者**方向一致**（都是"越大越开"），但**眼睛与嘴是两组不同的极性常量**，
///    各自写死，避免调用方误用。
///
/// ⚠️ **真机极性未实测**：`docs/research/63` §六 记「真机眼睛 weight 极性 / 舵机限位 / 弹簧手感」
///    需 BLE 实测（需用户点两下屏幕）。本文件的值来自**固件源码取证**，不是真机实测。
public enum WeightPolarity {

    /// 眼睛 weight：越大越睁开。
    public enum EyeWeight {
        /// `false` = 数值越大越睁开（不反转）。
        public static let inverted = false
    }

    /// 嘴 weight：越大越张开。
    public enum MouthWeight {
        /// `false` = 数值越大越张开（不反转）。
        public static let inverted = false
    }

    /// 把固件语义下的 weight 换算成"开合度"（0 = 全闭，1 = 全开）。
    /// - Parameter element: 元素（左右眼 / 嘴）。**左右眼共用同一套极性**，
    ///   协议侧的三个键是 `leftEye` / `rightEye` / `mouth`（`docs/spec/03` §2.3）。
    /// - Parameter weight: 固件 weight（0 ~ 100）。
    public static func openness(element: AvatarElement, weight: Int) -> Double {
        let clamped = Double(min(max(weight, 0), 100)) / 100.0
        switch element {
        case .leftEye, .rightEye:
            return EyeWeight.inverted ? 1.0 - clamped : clamped
        case .mouth:
            return MouthWeight.inverted ? 1.0 - clamped : clamped
        }
    }
}

/// 表情的 3 个元素类别。
public enum AvatarElement: String, CaseIterable, Sendable {
    case leftEye
    case rightEye
    case mouth
}

// MARK: - 坐标换算

/// x/y 坐标的单位换算。
///
/// ⭐ 出处：`docs/research/53` §3.2 —— 眼睛渲染映射（`eyes.cpp:14-18`）：
///    眼位基准 `(-70, -16)`，**位置偏移限幅 ±16**；JSON 侧 `x`/`y` ∈ [-100, 100]。
/// ⇒ 系数 = 100 / 16 = **6.25**（JSON 单位 ↔ 像素）。
///
/// ⚠️ 真实固件源码不在本仓库（`firmware/` 只有占位），该系数转引自 `docs/research/53` §3.2。
public enum AvatarCoordinate {

    /// JSON 单位 → 像素 的除数（100 JSON 单位 = 16 像素）。
    public static let jsonToPixelFactor: Double = 6.25

    /// JSON 归一化坐标 → 像素偏移。
    public static func jsonToPixel(_ jsonValue: Int) -> Double {
        Double(jsonValue) / jsonToPixelFactor
    }

    /// 像素偏移 → JSON 归一化坐标（四舍五入到整数）。
    public static func pixelToJson(_ pixelValue: Double) -> Int {
        Int((pixelValue * jsonToPixelFactor).rounded())
    }
}

// MARK: - 官方情绪表

/// 设备端的 6 种情绪（**不可远程设置**，只能间接触发）。
///
/// ⭐ 出处：`docs/spec/06-表情参数模型.md` §5.1（表 A · 固件事实）
///    原始出处 `firmware/main/stackchan/avatar/skins/default/eyes.cpp:103-122`
///    —— 设备端只有 `Neutral / Happy / Angry / Sad / Doubt / Sleepy` 六种。
///    `docs/research/53` §1 亦记：无惊讶 / 兴奋 / 失望等更细情绪。
///
/// ⚠️ **情绪会覆盖远程表情**（写的是同一批 weight/rotation 字段，后写者胜，
///    `docs/research/53` §2.1 事实 A）。
///
/// ⚠️ **嘴没有情绪表**：`DefaultMouth` 未覆写 `setEmotion` ⇒ 固件情绪**只作用于眼睛**，
///    嘴一律按规范默认值（`weight = 0`，闭嘴）——
///    出处：`docs/spec/06` §0.1 补注 + §5.1 + §5.2（表 B 嘴的参数待拍板前不填值）。
public enum Mood: String, CaseIterable, Sendable, Codable {
    case neutral = "Neutral"
    case happy = "Happy"
    case angry = "Angry"
    case sad = "Sad"
    case doubt = "Doubt"
    case sleepy = "Sleepy"

    /// 眼睛 weight（越大越睁开）。
    public var eyeWeight: Int {
        switch self {
        case .neutral: return 100
        case .happy: return 72
        case .angry: return 70
        case .sad: return 70
        case .doubt: return 75
        case .sleepy: return 35
        }
    }

    /// 左眼 rotation（0.1 度）—— **固件视觉值（带符号，照抄固件表）**。
    ///
    /// ⚠️ 下发时**不要直接用这个值**，用 ``leftEyeRotationForWire``。
    public var leftEyeRotation: Int {
        switch self {
        case .neutral: return 0
        case .happy: return 1550
        case .angry: return 450
        case .sad: return -400
        case .doubt: return 0
        case .sleepy: return -50
        }
    }

    /// 右眼 rotation（0.1 度）—— **固件视觉值（带符号，照抄固件表）**。
    public var rightEyeRotation: Int {
        switch self {
        case .neutral: return 0
        case .happy: return -1550
        case .angry: return -450
        case .sad: return 400
        case .doubt: return 0
        case .sleepy: return 50
        }
    }

    /// 左眼 rotation 的**下发值**（0…3600）。
    ///
    /// ⭐ 规则：`docs/spec/06` §4.3「**不要下发负 rotation**，用 `3600-θ` 表达反向」
    ///    —— 因为固件 `Element::setRotation` 把存储值钳到 0…3600，负值读回是 0
    ///    （`docs/spec/06` §0.1 C-3）。
    ///
    /// ⚠️ **⚠️ 文档里有一处算术笔误，本实现按"意图"而不是按字面**：
    ///    `docs/spec/06` §5.1 表注写「我们下发时用 **3560** 表达 −40°」，
    ///    但 3560（0.1°）= 356° = **−4°**，不是 −40°；
    ///    正确换算是 **3600 − 400 = 3200**（0.1° 单位下相减）。
    ///    本仓库不擅自改 `docs/spec/06`（他人所有权）⇒ 此处按 3200 实现并公开订正。
    public var leftEyeRotationForWire: Int {
        AvatarGeometry.wireRotation(leftEyeRotation)
    }

    /// 右眼 rotation 的**下发值**（0…3600）。
    public var rightEyeRotationForWire: Int {
        AvatarGeometry.wireRotation(rightEyeRotation)
    }

    /// 由官方情绪表派生的眼睛参数（左右眼 weight 相同，rotation 用**下发值**）。
    ///
    /// ⚠️ 只填**眼睛**部分：嘴在 6 种情绪下长什么样是**待拍板**的槽位
    ///    （`docs/spec/06` §5.2 表 B），未拍板前一律用规范默认值。
    public func eyeFeature(side: AvatarElement) -> AvatarFeature {
        let rotation = (side == .rightEye) ? rightEyeRotationForWire : leftEyeRotationForWire
        return AvatarFeature(x: 0, y: 0, rotation: rotation, weight: eyeWeight, size: 0)
    }
}

/// 设备端渲染几何的**事实层公式**（协议参数 → 像素几何）。
///
/// ⭐ 出处：`docs/spec/06-表情参数模型.md` §2.2（单位换算）与 §6.2（渲染几何事实表）
///    原始出处 `firmware/main/stackchan/avatar/skins/default/eyes.cpp` / `mouth.cpp`。
///
/// ⛔ **这里只有几何事实，没有视觉决策**：颜色、线宽、造型一律不在本文件。
///    ⚠️ 固件端背景是**纯黑**、前景是**纯白**（`docs/spec/06` §6.2），
///    但那是**设备端**的颜色；App 端画什么颜色是视觉层的事，**待拍板**。
public enum AvatarGeometry {

    /// 设备端画布尺寸（320×240）。
    public static let deviceCanvasSize = (width: 320, height: 240)

    /// 元素基准位置（相对面板中心，320×240 画布内）。
    ///
    /// ⭐ 出处：`docs/spec/06` §2.3
    ///    左眼 (-70, -16)｜右眼 (+70, -16)｜嘴 (0, +26)
    public enum BasePosition {
        public static let leftEye = (x: -70, y: -16)
        public static let rightEye = (x: 70, y: -16)
        public static let mouth = (x: 0, y: 26)
    }

    /// 眼睛直径（像素）：`8 + (size + 100) * 24 / 200`（整数截断，size = 0 ⇒ 20 px）。
    ///
    /// ⭐ 出处：`docs/spec/06` §2.2 / §6.2（`eyes.cpp:16,137`）
    public static func eyeDiameter(size: Int) -> Int {
        let clamped = min(max(size, -100), 100)
        return 8 + (clamped + 100) * 24 / 200
    }

    /// 眼睑 y 偏移（像素，**向上为负**）：`-(眼径 * weight / 100)`。
    ///
    /// ⭐ 出处：`docs/spec/06` §2.2 / §6.2（`eyes.cpp:75,77`）
    public static func eyelidOffsetY(weight: Int, eyeDiameter: Int) -> Int {
        let clamped = min(max(weight, 0), 100)
        return -(eyeDiameter * clamped / 100)
    }

    /// 嘴的宽 / 高 / 圆角（像素）：`90 + w*(60-90)/100` / `6 + w*(50-6)/100` / `w*(16-0)/100`（整数截断）。
    ///
    /// ⭐ 出处：`docs/spec/06` §2.2 / §6.2（`mouth.cpp:52-54`）
    ///    —— weight = 0 ⇒ 90×6 圆角 0 的闭嘴细线；weight = 100 ⇒ 60×50 圆角 16 的大开口。
    public static func mouthRect(weight: Int) -> (width: Int, height: Int, cornerRadius: Int) {
        let clamped = min(max(weight, 0), 100)
        let width = 90 + clamped * (60 - 90) / 100
        let height = 6 + clamped * (50 - 6) / 100
        let corner = clamped * (16 - 0) / 100
        return (width, height, corner)
    }

    /// 把**固件视觉值**的 rotation 换算成**下发值**（0…3600）。
    ///
    /// ⭐ 规则出处：`docs/spec/06` §4.3 —— 固件存储值被钳到 0…3600，
    ///    负角要用等效正角表达（`3600 − |θ|`，0.1° 单位下相减）。
    public static func wireRotation(_ visualRotation: Int) -> Int {
        let clamped = min(max(visualRotation, -3600), 3600)
        return clamped < 0 ? 3600 + clamped : clamped
    }
}
