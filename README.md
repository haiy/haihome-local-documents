# 海家本地文档 · Haihome Local Documents

面向 macOS Apple Silicon 的本地文档应用。提供文字、表格、演示的新建、打开、编辑和保存，保留本地文件流程，移除可分离的云文档、稻壳、AI、推广和登录入口。

**[下载完整应用 0.1.1](https://github.com/haiy/haihome-local-documents/releases/latest)** · [构建说明](BUILD.md) · [第三方说明](THIRD_PARTY_NOTICES.md)

## 安装与使用

1. 在 Releases 下载 `Haihome-Local-Documents-0.1.1-macOS-arm64.zip` 和 `SHA256SUMS.txt`，核对 SHA-256。
2. 解压后将 `海家本地文档.app` 复制到 Applications 或个人 Applications 目录。更新前先保存文档并正常退出旧版。
3. 打开应用，新建文字、表格或演示，也可直接打开已有文件。Command-S 保存，Command-Shift-S 另存为。
4. “更改文档位置”可选择本地目录或已经挂载的 NAS 目录。

需要 macOS 12 或更新版本、Apple Silicon；没有 Intel 或 Windows 版本。应用采用本地 ad hoc 签名，未做 Apple 公证。若系统阻止启动，可在“隐私与安全性”中查看并决定是否允许。

运行不需要原 WPS、Python、编译器或本工程。应用使用独立沙箱，不具备网络客户端或服务端权限，不共享原厂账号、App Group 或钥匙串。文件夹访问由用户选择授权。

## 功能与边界

- 外层 Swift/AppKit 启动器：新建 DOCX/XLSX/PPTX、打开文件、记住用户选择的目录。
- 内层基于 **WPS 12.1.29182 ARM64 编辑核心**进行固定版本裁剪；这不是从零实现的办公引擎，也不是 WPS 官方发行版。
- 保留本地 Office 文档编辑与保存，移除可分离的云、AI、推广与登录组件；不修改会员、序列号或授权状态。
- 已有 GUI 验收覆盖合成 DOCX/XLSX/PPTX 的打开、编辑、保存与重开，另存为和表格求和；0.1.1 增加图标并检查与此前编辑核心的一致性。本次发布另行检查签名及压缩包完整性。
- NAS 通过已挂载目录接入；没有实现云协议或自动同步。宏、复杂嵌入对象、全部旧格式与打印机未穷举。

## 工程结构

- `tools/LocalDocuments.swift`：原生文件启动器。
- `tools/build_local.py`：原版本校验、隔离复制、组件裁剪、固定机器码补丁、沙箱与签名。
- `tools/local_policy.cpp`：本地功能过滤库。
- `tools/package_launcher.py`：组合独立应用。
- `tools/set_defaults.py`：可选的文件关联工具，逐项验证并可续跑。
- `tools/templates/`：自行生成的空白 Office 模板。
- `tools/tests/`：文件关联工具回归测试。

源码仓库不包含厂商源代码、账号数据或个人文档。完整应用放在 Release 附件中。厂商组件保留其权利和原有许可；本项目不授予 WPS 组件的再分发许可，详见第三方说明。

## 安全反馈

请勿在 Issue 中上传真实文档、账号凭据或云盘配置。报告问题时注明 macOS 版本、应用版本、操作步骤，并优先使用合成样本。保存复杂文件时建议另存副本。
