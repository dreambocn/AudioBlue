# Code signing policy

## 当前状态 / Current status

AudioBule 已于 2026-10-16 向 SignPath Foundation 提交开源签名申请，目前等待审核，尚未接入正式代码签名。当前发布的应用 EXE 和标有 `unsigned` 的 MSIX 均未签名；包内由微软提供的运行时依赖保留原有签名。

AudioBule submitted its application to the SignPath Foundation open-source program on 2026-10-16. Review and production signing are pending. Current application executables and MSIX packages marked `unsigned` are not signed by the project.

申请获批并正式启用后，签名服务和证书来源将标注为：

> Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

这段说明不表示当前版本已经获得该服务或签名。

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
