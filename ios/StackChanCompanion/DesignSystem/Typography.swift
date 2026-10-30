import SwiftUI

// ============================================================================
// 排版 —— 全部走**系统 text style**，不手写 pt。
//
// 为什么不用手写字号（这是**机制性硬线**，不是视觉偏好）：
//   - `docs/spec/02-交付感与质感规范.md` §2.1 Q-6
//     「字号**必须**取自系统 text style，**不手写 pt**」
//   - HIG `typography.md` Large(default) 表给出官方阶梯：
//     Large Title 34/41、Title1 28/34、Title2 22/28、Title3 20/25、
//     Headline 17/22、Body 17/22、Callout 16/21、Subhead 15/20、
//     Footnote 13/18、Caption1 12/16、Caption2 11/13（Large 档）
//   - ⭐ 用 `.font(.body)` 等语义样式 ⇒ Dynamic Type **自动**跟随，
//     且放大 ≥200% 时不会崩（HIG `accessibility.md:34`）。
//   - 最小正文 11pt（HIG `accessibility.md:40`）⇒ Caption2 是下限。
//
// 数值（等宽字形）同样用语义样式 + `.monospacedDigit()`
//   （`docs/spec/02` §2.2「数字用等宽字形，避免数值跳动时布局抖」）。
//
// ⛔ 本文件不得出现 `.system(size:)` —— 由 `ios/tools/validate_project.py` 强制。
// ============================================================================

/// 排版槽位（**语义角色**）。
public enum TextRole: String, CaseIterable, Sendable {
    /// 全屏大标题。
    case largeTitle
    /// 模态 / 次级页标题。
    case pageTitle
    /// 区块主标题 / 卡片标题。
    case sectionTitle
    /// 列表分组标题。
    case groupTitle
    /// 气泡标题 / 状态条主文案。
    case headline
    /// 对话正文。
    case body
    /// 辅助正文。
    case callout
    /// 卡片描述 / 列表行副文案。
    case subhead
    /// 时间戳 / 单位。
    case footnote
    /// 极次要说明。
    case caption
    /// 数值（等宽字形）。
    case numeric
}

/// 排版 token —— **语义角色 → 系统 text style**。
public enum Typography {

    /// 全屏大标题（Large Title 34pt @ Large）。
    public static let largeTitle = Font.largeTitle
    /// 页面标题（Title2 22pt @ Large —— 二级页用 Title2，不抢 Large Title）。
    public static let pageTitle = Font.title2
    /// 区块标题（Title3 20pt @ Large）。
    public static let sectionTitle = Font.title3
    /// 分组标题（Headline 17pt @ Large）。
    public static let groupTitle = Font.headline
    /// 气泡标题 / 状态条主文案（Headline 17pt）。
    public static let headline = Font.headline
    /// 对话正文（Body 17pt）。
    public static let body = Font.body
    /// 辅助正文（Callout 16pt）。
    public static let callout = Font.callout
    /// 卡片描述 / 列表行副文案（Subhead 15pt）。
    public static let subhead = Font.subheadline
    /// 时间戳 / 单位（Footnote 13pt）。
    public static let footnote = Font.footnote
    /// 极次要说明（Caption1 12pt —— **不用 Caption2**，留给纯装饰性文字）。
    public static let caption = Font.caption
    /// 数值（等宽字形）。⚠️ 用 `.monospacedDigit()`，不另开字号。
    public static let numeric = Font.body.monospacedDigit()

    /// 分组标题的**字重**（SF Pro Semibold；iOS 列表分组标题惯例）。
    public static let groupTitleWeight = Font.Weight.semibold
    /// 区块标题的字重。
    public static let sectionTitleWeight = Font.Weight.semibold
    /// 正文字重（regular）。
    public static let bodyWeight = Font.Weight.regular
    /// 气泡标题的字重（semibold —— 气泡是视觉焦点）。
    public static let headlineWeight = Font.Weight.semibold
}
