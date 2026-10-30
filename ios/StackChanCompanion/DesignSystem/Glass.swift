import SwiftUI

// ============================================================================
// 玻璃材质 —— **只用于功能层**，内容层一律不许。
//
// 硬线（不是可选项，可以照做）：
//   - `DESIGN.md` §7.1 原则 1：`glassEffect(_:in:)` **只允许**出现在
//     导航栏 / 标签栏 / Sheet 浮层 / 悬浮工具键；
//     **页面背景、列表、卡片一律用 standard material 或纯色表面**。
//     （HIG `materials.md`："Don't use Liquid Glass in the content layer."）
//   - 同 §7.1 原则 2：自定义控件上的玻璃每屏 ≤ 1 处；**系统组件不手动套** `glassEffect`
//     （Tab Bar / Sidebar / Button / Toolbar 的玻璃由系统自动提供）。
//   - 同 §7.1 原则 3：默认只用 `.regular`，`.clear` **不启用**
//     （准入条件是"底层是视觉丰富的背景"，我们的背景是内容层，不满足）。
//   - 同 §7.2：SwiftUI Liquid Glass 真实 API 与可用平台（iOS 26.0+），
//     我们的最低部署是 iOS 17 ⇒ 这些 API 全部走 `#available(iOS 26.0, *)` 渐进增强。
//
// ⭐ 本文件**只提供**：
//   ① 允许用玻璃的位置清单（自检入口）；
//   ② iOS 17 基线下的 `Material` 映射；
//   ③ iOS 26+ 的 Liquid Glass 渐进增强入口。
// ============================================================================

/// 玻璃材质**允许出现的位置**。
public enum GlassPlacement: String, CaseIterable, Sendable {
    /// 底部标签栏。
    case tabBar
    /// 顶部导航栏。
    case topNavigation
    /// Sheet / 模态浮层。
    case sheet
    /// 悬浮工具键（自定义控件，每屏 ≤ 1 处，原则 2）。
    case floatingControl
}

/// 玻璃材质配置。
public enum Glass {

    /// 允许使用玻璃的位置清单（自检用：任何 `glassEffect` 调用点都应落在其中）。
    public static let allowedPlacements: Set<GlassPlacement> = [
        .tabBar, .topNavigation, .sheet, .floatingControl
    ]

    /// iOS 17 基线材质（`Material`）。
    ///
    /// ⛔ 只用 `.regular` / `.thin` —— `.clear` 不启用（原则 3）。
    public enum BaselineMaterial {
        /// 常规（对应 `.regular` 玻璃）。
        public static let regular = Material.regular
        /// 薄（对应 `.thin` 玻璃）。
        public static let thin = Material.thin
    }

    /// 玻璃变体（iOS 26+ 的 Liquid Glass）。
    ///
    /// ⚠️ 最低部署 iOS 17 ⇒ 调用点必须自己判 `if #available(iOS 26.0, *)`。
    /// 这里只暴露**意图**，不提供 iOS 26 独占类型，避免把整个工程拖高到 iOS 26。
    public enum Variant {
        /// 常规玻璃（唯一允许启用的变体）。
        case regular
        /// 透明玻璃（**不启用** —— 原则 3：我们的背景是内容层，不满足准入条件）。
        case clear
    }

    /// 玻璃形状策略。
    ///
    /// - `.containerRelative`：模态浮层用 `ContainerRelativeShape`，与容器圆角同心
    ///   （`DESIGN.md` §5「不硬编码」）。
    /// - `.fixed`：固定圆角，用 `Shapes` 里的档位。
    public enum ShapeStrategy {
        /// 容器相对形状（模态 / Sheet）。
        case containerRelative
        /// 固定圆角。
        case fixed(CornerRole)
    }

    /// 玻璃 tint 策略：品牌暖色只作 `.tint`（交互提示），**不作控件底色**
    /// （`DESIGN.md` §2.1）。
    public static func tint(_ accent: Color) -> Color { accent }
}
