import AppKit
import UniformTypeIdentifiers

// Offline document entry point. The editor is a separate, isolated modified
// bundle. This launcher stores folder preferences, never account credentials.
final class LocalDocuments: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var folderLabel: NSTextField!
    private var folder: URL!
    private var folderHasScope = false
    private var pending: [URL] = []
    private let fm = FileManager.default
    private let formats = ["docx", "xlsx", "pptx"]
    private let names = ["文字文档", "电子表格", "演示文稿"]

    func applicationDidFinishLaunching(_ note: Notification) {
        restoreFolder()
        installMenus()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 620, height: 350),
                          styleMask: [.titled, .closable, .miniaturizable],
                          backing: .buffered, defer: false)
        window.title = "海家本地文档"
        window.isReleasedWhenClosed = false
        window.center()
        let content = window.contentView!
        let title = NSTextField(labelWithString: "本地文档")
        title.font = .systemFont(ofSize: 28, weight: .semibold)
        title.frame = NSRect(x: 32, y: 280, width: 550, height: 40)
        content.addSubview(title)
        let subtitle = NSTextField(labelWithString: "打开、编辑和保存到你自己的文件夹。")
        subtitle.textColor = .secondaryLabelColor
        subtitle.frame = NSRect(x: 34, y: 248, width: 550, height: 24)
        content.addSubview(subtitle)
        for i in 0..<3 {
            let button = NSButton(title: "新建" + names[i], target: self, action: #selector(newDocument(_:)))
            button.tag = i
            button.bezelStyle = .rounded
            button.frame = NSRect(x: 30 + i * 185, y: 182, width: 175, height: 42)
            content.addSubview(button)
        }
        let open = NSButton(title: "打开文件…", target: self, action: #selector(openDocument))
        open.bezelStyle = .rounded
        open.frame = NSRect(x: 30, y: 125, width: 175, height: 40)
        content.addSubview(open)
        folderLabel = NSTextField(labelWithString: folder.path)
        folderLabel.lineBreakMode = .byTruncatingMiddle
        folderLabel.textColor = .secondaryLabelColor
        folderLabel.frame = NSRect(x: 34, y: 64, width: 400, height: 23)
        content.addSubview(folderLabel)
        let choose = NSButton(title: "更改文档位置…", target: self, action: #selector(chooseFolder))
        choose.bezelStyle = .rounded
        choose.frame = NSRect(x: 440, y: 57, width: 150, height: 36)
        content.addSubview(choose)
        let help = NSTextField(labelWithString: "也可选择已挂载的 NAS 文件夹。")
        help.font = .systemFont(ofSize: 12)
        help.textColor = .secondaryLabelColor
        help.frame = NSRect(x: 34, y: 30, width: 550, height: 20)
        content.addSubview(help)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        if !pending.isEmpty { let files = pending; pending = []; openInEditor(files) }
    }

    private func restoreFolder() {
        if let data = UserDefaults.standard.data(forKey: "documentFolderBookmark") {
            var stale = false
            if let url = try? URL(resolvingBookmarkData: data, options: .withSecurityScope,
                                  relativeTo: nil, bookmarkDataIsStale: &stale) {
                folder = url
                folderHasScope = url.startAccessingSecurityScopedResource()
            }
        }
        if folder == nil {
            if let path = Bundle.main.object(forInfoDictionaryKey: "HaihomeDefaultFolder") as? String {
                folder = URL(fileURLWithPath: path, isDirectory: true)
            } else {
                folder = fm.urls(for: .documentDirectory, in: .userDomainMask).first!
                    .appendingPathComponent("海家本地文档", isDirectory: true)
            }
            try? fm.createDirectory(at: folder, withIntermediateDirectories: true)
        }
    }

    private func installMenus() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu(); appItem.submenu = appMenu
        appMenu.addItem(withTitle: "退出海家本地文档", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let fileItem = NSMenuItem(); main.addItem(fileItem)
        let file = NSMenu(title: "文件"); fileItem.submenu = file
        for i in 0..<3 {
            let item = NSMenuItem(title: "新建" + names[i] + "…", action: #selector(newDocument(_:)), keyEquivalent: i == 0 ? "n" : "")
            item.target = self; item.tag = i; file.addItem(item)
        }
        file.addItem(NSMenuItem.separator())
        let open = NSMenuItem(title: "打开文件…", action: #selector(openDocument), keyEquivalent: "o")
        open.target = self; file.addItem(open)
        let location = NSMenuItem(title: "更改文档位置…", action: #selector(chooseFolder), keyEquivalent: "")
        location.target = self; file.addItem(location)
        NSApp.mainMenu = main
    }

    @objc private func newDocument(_ sender: AnyObject) {
        let index = (sender as? NSButton)?.tag ?? (sender as? NSMenuItem)?.tag ?? 0
        guard formats.indices.contains(index) else { return }
        let ext = formats[index]
        let panel = NSSavePanel()
        panel.title = "新建" + names[index]
        panel.nameFieldStringValue = "未命名." + ext
        panel.directoryURL = folder
        panel.allowedContentTypes = [UTType(filenameExtension: ext)!]
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let template = Bundle.main.resourceURL!.appendingPathComponent("Templates/blank." + ext)
            let data = try Data(contentsOf: template)
            try data.write(to: url, options: .atomic)
            openInEditor([url])
        } catch { showError(error.localizedDescription) }
    }

    @objc private func openDocument() {
        let panel = NSOpenPanel()
        panel.title = "打开本地文档"
        panel.directoryURL = folder
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = ["doc", "docx", "docm", "dot", "dotx", "dotm", "wps", "wpt",
                                     "xls", "xlsx", "xlsm", "xlt", "xltx", "xltm", "et", "ett",
                                     "ppt", "pptx", "pptm", "pot", "potx", "potm", "pps", "ppsx", "ppsm", "dps", "dpt",
                                     "rtf", "txt", "csv", "pdf"]
            .compactMap { UTType(filenameExtension: $0) }
        if panel.runModal() == .OK { openInEditor(panel.urls) }
    }

    @objc private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.title = "选择你的文档位置"
        panel.prompt = "使用这个文件夹"
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.directoryURL = folder
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let bookmark = try url.bookmarkData(options: .withSecurityScope,
                                                includingResourceValuesForKeys: nil, relativeTo: nil)
            if folderHasScope { folder.stopAccessingSecurityScopedResource() }
            folder = url
            folderHasScope = url.startAccessingSecurityScopedResource()
            UserDefaults.standard.set(bookmark, forKey: "documentFolderBookmark")
            folderLabel.stringValue = url.path
        } catch { showError(error.localizedDescription) }
    }

    private func openInEditor(_ files: [URL]) {
        let editor = Bundle.main.bundleURL.appendingPathComponent("Contents/SharedSupport/HaihomeEditor.app")
        guard Bundle(url: editor)?.bundleIdentifier == "com.haihome.wpslocal.macos" else {
            showError("找不到本地编辑器组件。请保留完整的应用包。")
            return
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        configuration.promptsUserIfNeeded = true
        // macOS open-document events also transfer selected-file access to the
        // sandboxed editor. Raw argv does not reliably open files in this build.
        NSWorkspace.shared.open(files, withApplicationAt: editor, configuration: configuration) { _, error in
            DispatchQueue.main.async {
                if let error = error { self.showError(error.localizedDescription) }
                else { self.window?.orderOut(nil) }
            }
        }
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        if window == nil { pending.append(contentsOf: urls) }
        else { openInEditor(urls) }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }

    private func showError(_ text: String) {
        let alert = NSAlert()
        alert.messageText = "未能完成操作"
        alert.informativeText = text
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = LocalDocuments()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
