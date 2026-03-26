; AudioBlue 安装器共享模板。
; 通过包装脚本定义输出文件名，并决定是否内置 WebView2 Runtime 离线安装器。

#ifndef InstallerOutputBaseFilename
  #error "InstallerOutputBaseFilename 必须由包装脚本定义。"
#endif

#ifndef BundleWebView2Runtime
  #define BundleWebView2Runtime "0"
#endif

#ifndef ReleaseArchitectureLabel
  #define ReleaseArchitectureLabel "x64"
#endif

#ifndef BundledReleaseFileName
  #define BundledReleaseFileName "AudioBlue-Setup-With-WebView2-x64.exe"
#endif

#define WebView2RuntimeClientGuid "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

#ifndef WebView2RuntimeRelativePath
#define WebView2RuntimeRelativePath "..\dist\webview2\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
#endif

#ifndef WebView2BundledInstallerName
  #define WebView2BundledInstallerName "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
#endif

[Setup]
AppId={{7EFAE4E9-D6EF-4A57-BE35-8C2D205EF001}
AppName=AudioBlue
AppVersion=0.1.2
AppPublisher=AudioBlue Team
DefaultDirName={autopf}\AudioBlue
DefaultGroupName=AudioBlue
SetupIconFile=..\assets\branding\audioblue-icon.ico
UninstallDisplayIcon={app}\audioblue.exe
OutputDir=..\dist\installer
OutputBaseFilename={#InstallerOutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "startmenu"; Description: "Create Start Menu shortcuts"; GroupDescription: "Shortcuts:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "autostart"; Description: "Start AudioBlue when signing in to Windows"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "..\dist\AudioBlue\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
#if BundleWebView2Runtime == "1"
Source: "{#WebView2RuntimeRelativePath}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AudioBlue"; ValueData: """{app}\audioblue.exe"" --background"; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AudioBlue"; Flags: deletevalue uninsdeletevalue; Tasks: autostart

[Icons]
Name: "{group}\AudioBlue"; Filename: "{app}\audioblue.exe"; Tasks: startmenu
Name: "{group}\Uninstall AudioBlue"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\AudioBlue"; Filename: "{app}\audioblue.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\audioblue.exe"; Description: "Launch AudioBlue"; Flags: nowait postinstall skipifsilent; Check: CanLaunchAudioBlue

[Code]
const
  WebView2RuntimeClientGuid = '{#WebView2RuntimeClientGuid}';
  WebView2DownloadPage = 'https://developer.microsoft.com/en-us/microsoft-edge/webview2/';
  ReleaseArchitectureLabel = '{#ReleaseArchitectureLabel}';
  WebView2BundledReleaseName = '{#BundledReleaseFileName}';
  WebView2BundledInstallerName = '{#WebView2BundledInstallerName}';

var
  WebView2WarningShown: Boolean;
  WebView2InstallFailed: Boolean;
  WebView2RestartRequired: Boolean;

function HasValidVersion(const Value: string): Boolean;
var
  NormalizedValue: string;
begin
  NormalizedValue := Trim(Value);
  Result := (NormalizedValue <> '') and (CompareText(NormalizedValue, '0.0.0.0') <> 0);
end;

function QueryWebView2RuntimeVersion(const RootKey: Integer; const SubKey: string; var Version: string): Boolean;
begin
  Version := '';
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and HasValidVersion(Version);
end;

function IsWebView2RuntimeInstalled(): Boolean;
var
  Version: string;
begin
  Result :=
    QueryWebView2RuntimeVersion(
      HKLM32,
      'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2RuntimeClientGuid,
      Version
    ) or QueryWebView2RuntimeVersion(
      HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\' + WebView2RuntimeClientGuid,
      Version
    );
end;

function GetMissingWebView2Reminder(): string;
begin
  Result :=
    '未检测到 Microsoft Edge WebView2 Runtime。' + #13#10#13#10 +
    '当前安装包架构：' + ReleaseArchitectureLabel + #13#10 +
    'AudioBlue 的主界面依赖 WebView2 才能打开。当前安装包不会自动下载该组件。' + #13#10 +
    '建议改用 GitHub Release 中的 "' + WebView2BundledReleaseName + '"，' + #13#10 +
    '或先从微软官方页面安装 WebView2 Runtime：' + #13#10 +
    WebView2DownloadPage;
end;

function GetBundledWebView2FailureReminder(): string;
begin
  Result :=
    '已尝试安装随包附带的 Microsoft Edge WebView2 Runtime，但未检测到安装成功。' + #13#10#13#10 +
    '请重新运行 "' + WebView2BundledReleaseName + '"，' + #13#10 +
    '或先从微软官方页面单独安装 WebView2 Runtime：' + #13#10 +
    WebView2DownloadPage;
end;

function GetBundledWebView2RestartReminder(): string;
begin
  Result :=
    'Microsoft Edge WebView2 Runtime 已安装，但系统要求重启后再启动 AudioBlue。' + #13#10#13#10 +
    '请在重启系统后再打开 AudioBlue。';
end;

procedure ShowMissingWebView2Reminder();
begin
  if WebView2WarningShown then
    exit;

  SuppressibleMsgBox(GetMissingWebView2Reminder(), mbInformation, MB_OK, IDOK);
  WebView2WarningShown := True;
end;

function InstallBundledWebView2Runtime(): Boolean;
var
  ExitCode: Integer;
begin
  Result := True;
  if IsWebView2RuntimeInstalled() then
    exit;

  if not Exec(
    ExpandConstant('{tmp}\' + WebView2BundledInstallerName),
    '/silent /install',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ExitCode
  ) then
  begin
    Result := False;
    exit;
  end;

  if ExitCode = 3010 then
    WebView2RestartRequired := True;

  Result := ((ExitCode = 0) or (ExitCode = 3010)) and IsWebView2RuntimeInstalled();
end;

function CanLaunchAudioBlue(): Boolean;
begin
  Result :=
    IsWebView2RuntimeInstalled() and
    (not WebView2InstallFailed) and
    (not WebView2RestartRequired);
end;

procedure InitializeWizard();
begin
  WebView2WarningShown := False;
  WebView2InstallFailed := False;
  WebView2RestartRequired := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
#if BundleWebView2Runtime == "0"
  if (CurPageID = wpReady) and (not IsWebView2RuntimeInstalled()) then
    ShowMissingWebView2Reminder();
#endif
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    exit;

#if BundleWebView2Runtime == "1"
  if not InstallBundledWebView2Runtime() then
  begin
    WebView2InstallFailed := True;
    SuppressibleMsgBox(GetBundledWebView2FailureReminder(), mbCriticalError, MB_OK, IDOK);
    exit;
  end;

  if WebView2RestartRequired then
    SuppressibleMsgBox(GetBundledWebView2RestartReminder(), mbInformation, MB_OK, IDOK);
#else
  if not IsWebView2RuntimeInstalled() then
    ShowMissingWebView2Reminder();
#endif
end;
