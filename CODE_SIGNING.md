# Code signing policy

## 当前状态 / Current status

AudioBule 于 2026-10-16 向 SignPath Foundation 申请免费开源签名，同日收到未获批准的通知：当前项目的公众可见度和社区采用信号未达到该计划要求。当前未接入代码签名。

常规用户请选择 Release 中的 `_Setup.exe` 安装程序。安装程序和应用 EXE 未签名，可能显示 Windows 未知发布者或 SmartScreen 提示；安装无需导入自签名证书。受组织应用控制策略限制的环境可能阻止运行。标有 `unsigned` 的 MSIX 仅供开发使用，正式安装需要签名。微软运行时依赖保留原有签名。

The SignPath Foundation application submitted on 2026-10-16 was not approved because the project did not yet meet the program's public visibility criteria. No production signing is enabled. Use the unsigned EXE installer for ordinary installation; Windows security prompts or organizational restrictions may apply. Microsoft runtime packages retain their original signatures.

## 维护与审批 / Maintainers and approvers

| 角色 / Role | 负责人 / Maintainer |
| --- | --- |
| 提交者与审查者 / Committer and reviewer | [dreambocn](https://github.com/dreambocn) |
| 发布签名审批者 / Signing approver | [dreambocn](https://github.com/dreambocn) |

外部贡献需由维护者审查后合入。正式启用签名前，参与签名的成员必须在 GitHub 与 SignPath 启用双因素认证。每个发布版本的签名请求由审批者人工批准，不向未经审查的 Pull Request 提供签名凭据。

External contributions require maintainer review. Signing participants must enable multi-factor authentication on GitHub and SignPath before production signing is enabled. Each release signing request requires manual approval by the signing approver.

## 签名范围与构建 / Scope and builds

- 签名范围为本仓库源码构建的 AudioBule 应用 EXE，以及包含该应用的 MSIX；x64 与 ARM64 使用同一发布审核流程。
- 不重新签署微软或其他第三方提供的二进制文件；分发包中的依赖保留其原始签名和许可证。
- 构建来自公开的 [GitHub Actions 工作流](https://github.com/dreambocn/AudioBlue/actions/workflows/build.yml)，产物对应确定的源码提交和版本标签。
- 正式接入时，签名步骤必须验证文件产品名称、版本与构建来源，并在发布前验证签名。

Production signing is intended for the project's own executable and MSIX packages built from this repository. Third-party binaries will not be re-signed. Signing will be tied to an identified source revision, with product metadata and signatures verified before publication.

## 隐私与联系 / Privacy and contact

隐私说明见 [Privacy policy](PRIVACY.md)。AudioBule 不包含统计、广告或由项目维护者运营的数据上传服务。

Privacy details are documented in the [privacy policy](PRIVACY.md). Report signing concerns through [GitHub Issues](https://github.com/dreambocn/AudioBlue/issues); do not post passwords, tokens or other secrets.
