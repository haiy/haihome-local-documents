# 构建与验证

在 macOS Apple Silicon 上安装 Python 3 与 Xcode Command Line Tools。自行准备合法取得的原版 WPS 12.1.29182 ARM64 应用。主程序预期 SHA-256：`ba9b1f18a0948bb3eee3265a18a15ba105553a31185f7bfdd74e17719bbc02b1`。构建会验证原版签名与字节，不支持的版本直接失败，不修改输入原件。

```sh
python3 tools/build_local.py core --source '/path/to/wpsoffice.app' --output-root build.noindex --standalone
python3 tools/package_launcher.py core package --output-root build.noindex --standalone
codesign --verify --deep --strict 'build.noindex/package/海家本地文档.app'
```

产物位于 `build.noindex/package/海家本地文档.app`。每次使用新的输出目录或候选标签；不要在使用中的应用上逐文件修改。`.noindex` 避免测试副本出现在 Spotlight。

```sh
python3 -m compileall -q tools
python3 -m unittest discover -s tools/tests
xcrun clang++ -fsyntax-only -x objective-c++ -std=c++17 tools/local_policy.cpp
ditto -c -k --sequesterRsrc --keepParent 'build.noindex/package/海家本地文档.app' Haihome-Local-Documents-0.1.1-macOS-arm64.zip
shasum -a 256 Haihome-Local-Documents-0.1.1-macOS-arm64.zip > SHA256SUMS.txt
```

可选的默认关联工具需要 duti。先安装完整应用，再执行以下命令；macOS 如果要求确认，完成该项后用同一报告续跑。未确认时工具停止，不批量制造后续提示。

```sh
python3 tools/set_defaults.py "$HOME/Applications/海家本地文档.app" --report defaults-change.json --apply
```

新 WPS 版本必须重新分析依赖、原始字节、签名和真实读写行为，不能直接复用当前补丁。测试应使用合成文档，不覆盖个人原件。
