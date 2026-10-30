import CoreProtocol

/// App 侧使用的情绪类型。
///
/// ⚠️ **归属说明**：官方 6 情绪枚举（`Neutral / Happy / Angry / Sad / Doubt / Sleepy`）
///    与它们的眼参数映射表是**协议/固件事实**，因此定义在协议层 `CoreProtocol.Mood`
///    （出处：`docs/research/53-固件表情引擎与动作合成通道取证.md` §2，
///    原始出处 `firmware/main/stackchan/avatar/skins/default/eyes.cpp:87-120`）。
///
///    本文件只做一层转发，**不复制任何取值**，避免出现第二份真相。
///
/// ⛔ 情绪在 UI 上怎么表达（图形 / 颜色 / 文案）属于视觉层，**待拍板**。
public typealias Mood = CoreProtocol.Mood
