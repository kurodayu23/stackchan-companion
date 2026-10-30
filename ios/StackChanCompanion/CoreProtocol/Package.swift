// swift-tools-version:5.9
// StackChan 协议层（CoreProtocol）
//
// 为什么独立成 Swift Package 而不是 App target 的普通源码：
//   1) 58 号 §2 定的模块边界 —— CoreProtocol「不依赖任何 target」，是纯值类型 + 可测单元。
//   2) 独立 Package 才能在没有模拟器的 macOS runner 上用 `swift test` 直接跑单测
//      （App target 的测试必须起 iOS 模拟器，CI 慢且脆）。
//   3) 本机（Windows）没有 Swift 编译器，协议逻辑必须能被 macOS runner 独立验证。
//
// 出处：docs/research/58-iOS端架构决策.md §2（模块边界表）
//      docs/spec/03-通信链路预设与数据契约.md §2.3（帧格式）
import PackageDescription

let package = Package(
    name: "CoreProtocol",
    platforms: [
        // iOS 17.0：与 App target 一致（docs/spec/05 §技术选型表「iOS App = iOS 17+」）
        .iOS(.v17),
        // macOS 14：仅为让 `swift test` 能在 CI 的 macOS runner 上跑，不需要更低版本
        .macOS(.v14)
    ],
    products: [
        .library(name: "CoreProtocol", targets: ["CoreProtocol"])
    ],
    targets: [
        .target(
            name: "CoreProtocol",
            path: "Sources/CoreProtocol"
        ),
        .testTarget(
            name: "CoreProtocolTests",
            dependencies: ["CoreProtocol"],
            path: "Tests/CoreProtocolTests"
        )
    ]
)
