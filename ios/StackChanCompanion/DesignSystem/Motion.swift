import SwiftUI

// ============================================================================
// 动效 —— **3 档**（档位数量沿用 `docs/spec/02` §3.1，不新增决策），页面不许传参。
//
// 硬线（不是视觉偏好，可以照做）：
//   - `docs/spec/02-交付感与质感规范.md` §3.2
//     「**所有动效必须走一个统一的 `Motion` 封装**，由封装决定参数，页面不传参。」
//   - 同 §3.2「**禁止 bounce / elastic / overshoot 回弹**」；若用 spring 则
//     `dampingFraction ≥ 0.85` ⇒ 本文件统一用 `.easeInOut` / `.easeOut`，
//     **不**用 `.spring`。
//   - `docs/research/19` §1.3 F10「必须支持 `accessibilityReduceMotion`」
//     ⇒ 每个档位都有 `reduced` 降级形态；减动效下**不得直接删掉动画**
//     （`docs/spec/02` §3.3：信息必须还在）。
//   - `DESIGN.md` §8「一次性反馈动效总时长 ≤ 400ms」「单屏持续动效 ≤ 1 处」。
//
// 时长取值依据（**不是拍脑袋**）：
//   - iOS 系统自身的动效节奏：Tab 切换 ≈ 0.3s、Sheet 呈现 ≈ 0.35s、
//     按压反馈 ≈ 0.15s、通知横幅 ≈ 0.4s。
//   - ⇒ 瞬时 0.15s / 标准 0.30s / 叙事 0.40s（叙事正好卡在 400ms 上限）。
//   - 曲线用 iOS 惯用的 `easeOut`（进入）/ `easeInOut`（对称转场），
//     **不用**自定义 `cubic-bezier`（`ios/tools/validate_project.py` 也会拦）。
// ============================================================================

/// 动效档位（**角色**）。
public enum MotionTier: String, CaseIterable, Sendable {
    /// 瞬时（按压反馈 / 图标切换 / 勾选）。
    case instant
    /// 标准（页面转场 / 卡片展开收起 / 状态条变化 / 气泡入场）。
    case standard
    /// 叙事（全 App 不超过 3 处，每处对应一个情绪时刻）。
    case narrative
}

/// 动效 token —— **档位 → 时长 + 曲线**（页面只选档位，不传参）。
public enum Motion {

    /// 瞬时档（按压反馈 / 图标切换 / 勾选）。
    public static let instant = Animation.easeOut(duration: 0.15)
    /// 标准档（页面转场 / 卡片展开收起 / 状态条变化 / 气泡入场）。
    public static let standard = Animation.easeInOut(duration: 0.30)
    /// 叙事档（全 App ≤ 3 处）。
    public static let narrative = Animation.easeInOut(duration: 0.40)

    /// 减动效（`accessibilityReduceMotion`）下的降级形态。
    ///
    /// ⚠️ 机制性要求：减动效下**不得直接删掉动画**，信息必须还在
    /// （`docs/spec/02` §3.3）⇒ 做法是**把位移/缩放换成透明度淡入淡出**，
    /// 时长压到 0.15s（够短，不构成负担；够长，看得见变化）。
    public static let reduced = Animation.easeOut(duration: 0.15)

    /// 按当前减动效偏好取对应形态。
    public static func tier(_ tier: MotionTier,
                             reduceMotion: Bool) -> Animation {
        reduceMotion ? reduced : tier.animation
    }
}

extension MotionTier {
    /// 该档位的默认动画。
    public var animation: Animation {
        switch self {
        case .instant:   return Motion.instant
        case .standard: return Motion.standard
        case .narrative: return Motion.narrative
        }
    }
}
