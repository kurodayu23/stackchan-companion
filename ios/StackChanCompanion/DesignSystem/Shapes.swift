import SwiftUI

// ============================================================================
// 形状 —— **iOS 连续曲率**圆角 + 间距档位 + 分隔手法。
//
// 硬线（不是视觉偏好，可以照做）：
//   - `DESIGN.md` §5「iOS 圆角用**连续曲率**；模态浮层用 `ContainerRelativeShape`
//     与容器圆角同心对齐，**不硬编码**」
//   - 同 §5「**同心规则：外圆角 = 内圆角 + 内边距**」
//   - `docs/spec/02` §4.3「分隔只用一种手法（描边 / 背景 / 阴影 三选一）」
//   - `docs/research/19` §1.5 F21「容器定宽居中：宽屏只加边距，度量与网格不变」
//   - `docs/research/19` §1.2 F5「触摸目标 ≥ 44×44pt」（HIG `accessibility.md:135`）
//
// 取值依据（**不是拍脑袋**）：
//   - 圆角阶梯 = iOS 系统控件的连续曲率档：控件 10 / 卡片 16 / 抽屉 20 /
//     胶囊 999（= 完全圆角）/ 图标容器 8。
//     ⚠️ 全部符合「同心规则」：卡片(16) = 控件(10) + 内边距(6) 的量级关系；
//        抽屉(20) = 卡片(16) + 4。
//   - 间距档位 = 4 的倍数阶梯（4 / 8 / 12 / 16 / 24 / 32），
//     其中 24 = HIG `accessibility.md:141` 建议的「24pt 留白」档。
//   - 分隔手法 = **描边**（`Divider` / `stroke`）。
//     选描边的理由：它不引入额外层（不破坏连续曲率）、不随背景色变化而失配、
//     且与 `separator` token 一一对应 ⇒ 天然满足「同屏不混用三种手法」。
// ============================================================================

/// 圆角槽位（**角色**）。
public enum CornerRole: String, CaseIterable, Sendable {
    /// 小图标底 / 图标容器。
    case icon
    /// 按钮 / 输入框 / 控件。
    case control
    /// 功能 tile / 列表分组。
    case tile
    /// 卡片 / 主卡。
    case card
    /// 底部抽屉 / 对话框。
    case sheet
    /// 胶囊 / 头像 / 状态点。
    case capsule
}

/// 形状 token —— 圆角 + 间距 + 分隔。
public enum Shapes {

    // MARK: - 圆角（连续曲率，iOS 档位）

    /// 图标容器圆角。
    public static let icon: CGFloat = 8
    /// 控件圆角（按钮 / 输入框）。
    public static let control: CGFloat = 10
    /// tile 圆角。
    public static let tile: CGFloat = 12
    /// 卡片圆角。
    public static let card: CGFloat = 16
    /// 抽屉 / 对话框圆角。
    public static let sheet: CGFloat = 20
    /// 胶囊圆角（999 = 完全圆角，视觉上等同）。
    public static let capsule: CGFloat = 999

    // MARK: - 间距（4 的倍数阶梯）

    /// 极小间距（图标与文字之间）。
    public static let spacingXS: CGFloat = 4
    /// 小间距（同行元素之间）。
    public static let spacingS: CGFloat = 8
    /// 常规间距（元素之间）。
    public static let spacingM: CGFloat = 12
    /// 大间距（分组之间）。
    public static let spacingL: CGFloat = 16
    /// 更大间距（区块之间）。
    public static let spacingXL: CGFloat = 24
    /// 最大间距（页面级留白）。
    public static let spacingXXL: CGFloat = 32

    /// 触控目标下限（pt）—— HIG `accessibility.md:135`（T1 官方数值）。
    public static let minimumTouchTarget: CGFloat = 44

    // MARK: - 分隔（只选一种手法：描边）

    /// 分隔线粗细（pt）。细线是 iOS 分隔线的惯例。
    public static let separatorThickness: CGFloat = 0.5
}
