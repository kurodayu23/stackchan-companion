import SwiftUI

// ============================================================================
// 视觉 token —— 槽位（角色）+ **多套方案取值**。
//
// ⭐ 2026-10-25 用户拍板：
//   - 视觉方向：**4 套方案全做**，最后由用户选 ⇒ 这里不是「一套 token」，
//     而是「一套**槽位** × 4 套**取值**」。
//   - 强调色：**各方案自带** ⇒ accent 不再是全局常量，而是**方案级** token。
//   - 定位：陪伴聊天为主 + 设备遥控都要 ⇒ 不影响 token，只影响信息架构。
//   - 脸：镜像 + 风格化两种都要 ⇒ 见 `Features/Companion/Face/`。
//
// 槽位（角色）划分沿用仓库既有文档，不新增决策：
//   - 画布 / 表面 / 次级表面 → `DESIGN.md` §2.1
//   - 主文字 / 次文字 / 分割线 → `DESIGN.md` §2.1
//   - 品牌暖色 → `DESIGN.md` §2.1
//   - success / warning / danger / 在线 → `DESIGN.md` §2.3
//
// 取值来源（**可追溯**，不许拍脑袋）：
//   - 4 套方案的色值逐项抄自 `prototype/variants/` 的 4 个原型：
//     `01-paper-terracotta` / `03-pure-white-blank` /
//     `17-warm-paper-serif` / `18-tuck-dark-calm`
//   - 对比度复核见 `docs/research/67-四套视觉方案token提取与对比度复核.md`
//     （判据 = HIG `accessibility.md:60-62`，正文 ≥ 4.5:1）
//   - 圆角 / 间距 / 动效：**iOS 连续曲率**惯例值，见 `docs/spec/02` §4 与
//     `docs/research/19` §1.2/§1.5（触控 ≥ 44×44pt；无小于 11pt 的文本）。
//
// ⛔ 除本文件与同级的 Typography / Shapes / Motion / Glass 外，
//    其他 Swift 文件一律不得出现视觉字面量（由 `ios/tools/validate_project.py` 强制）。
// ============================================================================

/// 主题槽位清单（**角色**，不是取值）。
public enum ThemeToken: String, CaseIterable, Sendable {
    /// 画布（页面底）。
    case canvas
    /// 表面（次级表面）。
    case surface
    /// 抬升表面（第三层）。
    case surfaceElevated
    /// 主文字。
    case textPrimary
    /// 次文字。
    case textSecondary
    /// 三级文字。
    case textTertiary
    /// 分割线。
    case separator
    /// 品牌暖色（**方案级** —— 各方案自带，不跨方案共用）。
    case accent
    /// 品牌色之上的文字色。
    case onAccent
    /// 成功状态色。
    case success
    /// 警告状态色。
    case warning
    /// 危险状态色。
    case danger
    /// 在线 / 工作中状态色。
    case online
}

/// 一套方案的**全部色值**。
///
/// ⭐ 4 套方案各自的取值来自对应原型的 CSS 变量（逐项抄录 + 对比度复核）。
/// 新增方案 = 新增一个 `ThemePalette` 实现 + 在 `ThemeChoice` 加一个 case。
public protocol ThemePalette: Sendable {
    /// 方案标识。
    var identifier: String { get }
    /// 展示名（给用户看的名字）。
    var displayName: String { get }
    /// 该方案是否只适用于**深色**底（决定能否在浅色系统外观下使用）。
    var isDarkBased: Bool { get }
    /// 取槽位色值。
    func color(for token: ThemeToken) -> Color
}

// MARK: - 方案 01：Paper Terracotta（暖白纸感 + 陶土红）
//
// 色值抄自 `prototype/variants/01-paper-terracotta.html` 的 `:root` 变量：
//   --bg:#FAF8F5  --surface:#FFFDFA  --surface-2:#F1ECE4
//   --text:#241F1B  --accent:#AF4C37
// ⚠️ 强调色对比度实测 ≈ 4.3:1（浅底）⇒ 属「粗体/大字号可用」档，
//    正文级用途请用 `textPrimary` 而非 `accent`。
public struct PaperTerracottaPalette: ThemePalette {
    public init() {}

    public var identifier: String { "paper-terracotta" }
    public var displayName: String { "纸感陶土" }
    public var isDarkBased: Bool { false }

    public func color(for token: ThemeToken) -> Color {
        switch token {
        case .canvas:         return Color(red: 0.980, green: 0.973, blue: 0.961)
        case .surface:        return Color(red: 1.000, green: 0.992, blue: 0.980)
        case .surfaceElevated:return Color(red: 0.945, green: 0.925, blue: 0.894)
        case .textPrimary:    return Color(red: 0.141, green: 0.122, blue: 0.106)
        case .textSecondary:  return Color(red: 0.219, green: 0.173, blue: 0.141)
        case .textTertiary:   return Color(red: 0.278, green: 0.231, blue: 0.196)
        case .separator:      return Color(red: 0.141, green: 0.122, blue: 0.106).opacity(0.12)
        case .accent:         return Color(red: 0.686, green: 0.298, blue: 0.216)
        case .onAccent:       return Color(red: 1.000, green: 1.000, blue: 1.000)
        case .success:        return Color(red: 0.204, green: 0.522, blue: 0.349)
        case .warning:        return Color(red: 0.722, green: 0.475, blue: 0.153)
        case .danger:         return Color(red: 0.686, green: 0.298, blue: 0.216)
        case .online:         return Color(red: 0.204, green: 0.522, blue: 0.349)
        }
    }
}

// MARK: - 方案 03：Pure White Blank（极简纯白）
//
// 色值抄自 `prototype/variants/03-pure-white-blank.html`：
//   --bg:#FFFFFF  --surface:#F5F6F8  --surface2:#FAFAFB
//   --text:#1D1D1F  --accent:#B74332  --on-accent:#FFFFFF
public struct PureWhiteBlankPalette: ThemePalette {
    public init() {}

    public var identifier: String { "pure-white-blank" }
    public var displayName: String { "纯白留白" }
    public var isDarkBased: Bool { false }

    public func color(for token: ThemeToken) -> Color {
        switch token {
        case .canvas:         return Color(red: 1.000, green: 1.000, blue: 1.000)
        case .surface:        return Color(red: 0.961, green: 0.965, blue: 0.973)
        case .surfaceElevated:return Color(red: 0.980, green: 0.980, blue: 0.984)
        case .textPrimary:    return Color(red: 0.114, green: 0.114, blue: 0.122)
        case .textSecondary:  return Color(red: 0.114, green: 0.114, blue: 0.122)
        case .textTertiary:   return Color(red: 0.114, green: 0.114, blue: 0.122)
        case .separator:      return Color(red: 0.114, green: 0.114, blue: 0.122).opacity(0.12)
        case .accent:         return Color(red: 0.718, green: 0.263, blue: 0.196)
        case .onAccent:       return Color(red: 1.000, green: 1.000, blue: 1.000)
        case .success:        return Color(red: 0.204, green: 0.522, blue: 0.349)
        case .warning:        return Color(red: 0.722, green: 0.475, blue: 0.153)
        case .danger:         return Color(red: 0.718, green: 0.263, blue: 0.196)
        case .online:         return Color(red: 0.204, green: 0.522, blue: 0.349)
        }
    }
}

// MARK: - 方案 17：Warm Paper Serif（暖纸 + 衬线）
//
// 色值抄自 `prototype/variants/17-warm-paper-serif.html`：
//   --bg:#EAE6DE  --surface:#F7F4EE  --surface2:#E3DED4
//   --text:#2A231C  --text2:#4C4237  --text3:#696053
//   --accent:#9E3B26  --on-accent:#FFFFFF
public struct WarmPaperSerifPalette: ThemePalette {
    public init() {}

    public var identifier: String { "warm-paper-serif" }
    public var displayName: String { "暖纸衬线" }
    public var isDarkBased: Bool { false }

    public func color(for token: ThemeToken) -> Color {
        switch token {
        case .canvas:         return Color(red: 0.918, green: 0.902, blue: 0.871)
        case .surface:        return Color(red: 0.969, green: 0.957, blue: 0.933)
        case .surfaceElevated:return Color(red: 0.890, green: 0.871, blue: 0.831)
        case .textPrimary:    return Color(red: 0.165, green: 0.137, blue: 0.110)
        case .textSecondary:  return Color(red: 0.298, green: 0.259, blue: 0.216)
        case .textTertiary:   return Color(red: 0.412, green: 0.376, blue: 0.325)
        case .separator:      return Color(red: 0.165, green: 0.137, blue: 0.110).opacity(0.14)
        case .accent:         return Color(red: 0.620, green: 0.231, blue: 0.149)
        case .onAccent:       return Color(red: 1.000, green: 1.000, blue: 1.000)
        case .success:        return Color(red: 0.259, green: 0.443, blue: 0.325)
        case .warning:        return Color(red: 0.671, green: 0.451, blue: 0.145)
        case .danger:         return Color(red: 0.620, green: 0.231, blue: 0.149)
        case .online:         return Color(red: 0.259, green: 0.443, blue: 0.325)
        }
    }
}

// MARK: - 方案 18：Tuck Dark Calm（深色安静）
//
// 色值抄自 `prototype/variants/18-tuck-dark-calm.html`：
//   --bg:#111113  --surface:#1C1C1F  --surface2:#26262A  --surface3:#1E1E21
//   --text:#ECECEE  --text2:#B6B6BE  --text3:#8D8D92
//   --accent:#E3A857  --on-accent:#1A1208
//
// ⚠️ 本方案是**深色底** ⇒ 在 iOS **浅色系统外观**下不可直接使用
//    （`isDarkBased == true` ⇒ UI 层应强制深色外观，或提示用户该方案仅深色可用）。
public struct TuckDarkCalmPalette: ThemePalette {
    public init() {}

    public var identifier: String { "tuck-dark-calm" }
    public var displayName: String { "深色静谧" }
    public var isDarkBased: Bool { true }

    public func color(for token: ThemeToken) -> Color {
        switch token {
        case .canvas:         return Color(red: 0.067, green: 0.067, blue: 0.075)
        case .surface:        return Color(red: 0.110, green: 0.110, blue: 0.122)
        case .surfaceElevated:return Color(red: 0.149, green: 0.149, blue: 0.165)
        case .textPrimary:    return Color(red: 0.925, green: 0.925, blue: 0.933)
        case .textSecondary:  return Color(red: 0.714, green: 0.714, blue: 0.745)
        case .textTertiary:   return Color(red: 0.553, green: 0.553, blue: 0.573)
        case .separator:      return Color(red: 0.925, green: 0.925, blue: 0.933).opacity(0.12)
        case .accent:         return Color(red: 0.890, green: 0.659, blue: 0.341)
        case .onAccent:       return Color(red: 0.102, green: 0.071, blue: 0.031)
        case .success:        return Color(red: 0.325, green: 0.780, blue: 0.502)
        case .warning:        return Color(red: 0.890, green: 0.659, blue: 0.341)
        case .danger:         return Color(red: 1.000, green: 0.259, blue: 0.259)
        case .online:         return Color(red: 0.325, green: 0.780, blue: 0.502)
        }
    }
}

/// 4 套方案的注册表（**新增方案只改这里 + ThemeChoice**）。
public enum PaletteRegistry {
    /// 全部方案，按展示顺序。
    public static let all: [any ThemePalette] = [
        PaperTerracottaPalette(),
        PureWhiteBlankPalette(),
        WarmPaperSerifPalette(),
        TuckDarkCalmPalette(),
    ]
}
