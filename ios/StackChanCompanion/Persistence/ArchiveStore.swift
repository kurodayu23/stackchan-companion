import Foundation

/// 关系档案里的一条记录。
///
/// ⭐ 档案语义出处：`docs/spec/04-产品战略与护城河总纲.md` §3.6（设备即档案）、
///    `docs/research/58-iOS端架构决策.md` §4.3
///    「设备上的表情是稀疏采样，手机上的是连续记录 ⇒ **关系档案必须建在 App 端**」。
///
/// ⛔ **隐私红线**（`docs/research/58` §2 / §7）：
///    - 档案**只落本地**，**永不同步、永不入库**。
///    - 档案**不得**经 `CloudGateway` 出网（`RecallStackChanMemory` 只能查本地）。
public struct ArchiveEntry: Identifiable, Equatable, Sendable, Codable {

    /// 记录类型。
    public enum Kind: String, CaseIterable, Sendable, Codable {
        /// 一条记忆。
        case memory
        /// 一个时刻（"小栈的一天"里的一条）。
        case moment
        /// 一个里程碑。
        case milestone
    }

    /// 本地唯一标识。
    public let id: UUID
    /// 创建时间。
    public let createdAt: Date
    /// 记录类型。
    public let kind: Kind
    /// 正文。
    public let text: String

    public init(id: UUID = UUID(),
                createdAt: Date = Date(),
                kind: Kind,
                text: String) {
        self.id = id
        self.createdAt = createdAt
        self.kind = kind
        self.text = text
    }
}

/// 档案存储协议。
///
/// ⚠️ **只读本地**：这个协议**故意没有**同步 / 上传方法
///    （`docs/research/58` §7 硬约束 ④「只读本地存储」）。
public protocol ArchiveStore: AnyObject {
    /// 读取全部记录（按创建时间升序）。
    func load() throws -> [ArchiveEntry]
    /// 覆盖写入全部记录。
    func save(_ entries: [ArchiveEntry]) throws
}

/// 基于本地 JSON 文件的档案存储。
///
/// ⭐ 为什么用文件而不是 SwiftData：
///    - 档案是**只读本地、永不同步**的个人数据，用纯文件最容易被审计
///      （`docs/research/58` §2「`PersonalStore` 只读本地（SwiftData/SQLite/Keychain）」——
///      文件是该清单里最透明的一种实现）。
///    - 目录设了 `isExcludedFromBackup = true` ⇒ 不进 iCloud 备份，不出网。
///
/// ⚠️ **本机未验证**：Windows 上没有 Swift 编译器，**这段代码一次都没编译过**。
public final class FileArchiveStore: ArchiveStore {

    /// 存储文件所在目录。
    private let directory: URL

    /// 存储文件名。
    private let filename: String

    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    /// - Parameters:
    ///   - filename: 存储文件名。
    ///   - directory: 存储目录；缺省用 Application Support 下的 `StackChanCompanion`。
    public init(filename: String = "archive.json", directory: URL? = nil) {
        self.filename = filename
        if let directory {
            self.directory = directory
        } else {
            let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
                ?? URL(fileURLWithPath: NSTemporaryDirectory())
            self.directory = base.appendingPathComponent("StackChanCompanion", isDirectory: true)
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder
    }

    /// 存储文件的完整路径。
    public var fileURL: URL {
        directory.appendingPathComponent(filename, isDirectory: false)
    }

    public func load() throws -> [ArchiveEntry] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        let entries = try decoder.decode([ArchiveEntry].self, from: data)
        return entries.sorted { $0.createdAt < $1.createdAt }
    }

    public func save(_ entries: [ArchiveEntry]) throws {
        try ensureDirectory()
        let data = try encoder.encode(entries.sorted { $0.createdAt < $1.createdAt })
        try data.write(to: fileURL, options: [.atomic])
    }

    /// 确保目录存在，并标记为**不参与 iCloud 备份**。
    private func ensureDirectory() throws {
        if !FileManager.default.fileExists(atPath: directory.path) {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        }
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutableDirectory = directory
        try? mutableDirectory.setResourceValues(values)
    }
}
