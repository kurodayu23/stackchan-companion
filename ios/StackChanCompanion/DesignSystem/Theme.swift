import SwiftUI

// ============================================================================
// 主题 —— **4 套方案**（用户 2026-10-25 拍板「风格都做」，最后由用户选）。
//
// 本文件只做**机制**：方案枚举 + 取值路由 + 注入点。
// 具体色值在 `Tokens.swift` 的 `ThemePalette` 实现里；字号/圆角/动效分别在
// `Typography.swift` / `Shapes.swift` / `Motion.swift`。
//
// 为什么是「方案」而不是「浅色/深色」：
//   - 4 套方案里 3 套是浅底、1 套（Tuck Dark Calm）是深底
//     ⇒ 「深浅」不是**正交维度**，而是**方案的属性**（`isDarkBased`）。
//   - 系统外观（`ColorScheme`）仍然生效：浅底方案在系统深色下由 UI 层
//     提示「本方案仅浅色可用」，而不是硬切一套没设计过的深色值。
//
// 取值出处见 `Tokens.swift` 文件头；对比度复核见
// `docs/research/67-四套视觉方案token提取与对比度复核.md`。
// ============================================================================

/// 视觉方案的**唯一切换点**。
public enum ThemeChoice: String, CaseIterable, Sendable, Identifiable {
    /// 方案 01：纸感陶土（暖白纸感 + 陶土红，浅底）。
    case paperTerracotta
    /// 方案 03：纯白留白（极简纯白，浅底）。
    case pureWhiteBlank
    /// 方案 17：暖纸衬线（暖纸 + 衬线，浅底）。
    case warmPaperSerif
    /// 方案 18：深色静谧（深色底）。
    case tuckDarkCalm

    public var id: String { rawValue }

    /// 展示名（给用户看）。
    public var displayName: String {
        switch self {
        case .paperTerracotta: return "纸感陶土"
        case .pureWhiteBlank:   return "纯白留白"
        case .warmPaperSerif:   return "暖纸衬线"
        case .tuckDarkCalm:     return "深色静谧"
        }
    }

    /// 一句话描述（设置页里给用户看差别）。
    public var summary: String {
        switch self {
        case .paperTerracotta: return "暖白纸底 + 陶土红，像一本旧笔记本"
        case .pureWhiteBlank:   return "纯白 + 大留白，克制到几乎无表情"
        case .warmPaperSerif:   return "米色暖纸 + 衬线字，像一本摊开的书"
        case .tuckDarkCalm:     return "近黑底 + 琥珀金，深夜不刺眼"
        }
    }

    /// 该方案是否只适用于**深色**底。
    public var isDarkBased: Bool {
        palette.isDarkBased
    }

    /// 对应的色值方案。
    public var palette: any ThemePalette {
        switch self {
        case .paperTerracotta: return PaperTerracottaPalette()
        case .pureWhiteBlank:   return PureWhiteBlankPalette()
        case .warmPaperSerif:   return WarmPaperSerifPalette()
        case .tuckDarkCalm:     return TuckDarkCalmPalette()
        }
    }
}

/// 主题协议（取**色值槽位**；其余维度由同级文件负责）。
public protocol Theme {
    /// 主题标识（调试 / 日志用）。
    var identifier: String { get }
    /// 取某个槽位的色值。
    func color(for token: ThemeToken) -> Color
}

/// 由 `ThemePalette` 适配出的 `Theme`（**唯一实现**，避免两套结构漂移）。
public struct PaletteTheme: Theme {
    private let palette: any ThemePalette
    public init(_ palette: any ThemePalette) { self.palette = palette }
    public var identifier: String { palette.identifier }
    public func color(for token: ThemeToken) -> Color { palette.color(for: token) }
}

extension ThemeChoice {
    /// 切换点：把 case 映射到具体实现。
    public var theme: Theme { PaletteTheme(palette) }
}

/// 已解析主题（注入环境，供视图读取）。
public struct ResolvedTheme: Sendable {
    /// 当前方案选择。
    public let choice: ThemeChoice
    /// 当前系统外观。
    public let scheme: ColorScheme
    /// 当前对比度偏好。
    public let contrast: AccessibilityContrast

    public init(choice: ThemeChoice, scheme: ColorScheme, contrast: AccessibilityContrast) {
        self.choice = choice
        self.scheme = scheme
        self.contrast = contrast
    }

    /// 取槽位色值。
    public func color(for token: ThemeToken) -> Color {
        choice.palette.color(for: token)
    }
}

private struct ThemeChoiceKey: EnvironmentKey {
    static let defaultValue: ThemeChoice = .paperTerracotta
}

extension EnvironmentValues {
    /// 当前方案选择（注入点：``StackChanCompanionApp``）。
    public var themeChoice: ThemeChoice {
        get { self[ThemeChoiceKey.self] }
        set { self[ThemeChoiceKey.self] = newValue }
    }
}
