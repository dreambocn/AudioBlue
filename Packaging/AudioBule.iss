; 版本、架构和完整负载由 Publish.ps1 传入，安装程序无需联网。
[Setup]
AppId={{9C798D70-A8E1-4485-904E-EBE558077E01}
AppName=AudioBule
AppVersion={#AppVersion}
AppPublisher=dreambocn
AppPublisherURL=https://github.com/dreambocn/AudioBlue
DefaultDirName={localappdata}\Programs\AudioBule
DefaultGroupName=AudioBule
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0.19041
#if AppArchitecture == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
#else
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
OutputDir={#PackageOutput}
OutputBaseFilename=AudioBule_{#AppVersion}_{#AppArchitecture}_Setup
SetupIconFile={#PayloadDirectory}\Assets\AppIcon.ico
UninstallDisplayIcon={app}\AudioBule.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\AudioBule.Installation
CloseApplications=no
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "chinesesimplified"; MessagesFile: "Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.RuntimeStatus=正在安装 Windows App Runtime，请稍候……
chinesesimplified.RuntimeFailed=运行时安装失败，尚未安装 AudioBule。请查看日志：
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.LaunchApp=启动 AudioBule
english.RuntimeStatus=Installing Windows App Runtime. Please wait...
english.RuntimeFailed=Runtime installation failed. AudioBule has not been installed. See the log:
english.DesktopShortcut=Create a desktop shortcut
english.LaunchApp=Launch AudioBule

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
Source: "Languages\LICENSE-ChineseTranslation.txt"; DestDir: "{app}\Licenses"; Flags: ignoreversion
Source: "{#PayloadDirectory}\*"; DestDir: "{app}"; Excludes: "Dependencies\*,Install-Runtime.ps1"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDirectory}\Dependencies\*.txt"; DestDir: "{app}\Licenses"; Flags: ignoreversion
; 运行时只在安装准备阶段解压；失败会停止安装，不留下成功的应用安装记录。
Source: "{#PayloadDirectory}\Dependencies\*.msix"; DestDir: "{tmp}\Dependencies"; Flags: dontcopy
Source: "{#PayloadDirectory}\Install-Runtime.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\AudioBule"; Filename: "{app}\AudioBule.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AudioBule"; Filename: "{app}\AudioBule.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\AudioBule.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
  LogPath: String;
begin
  Result := '';
  WizardForm.StatusLabel.Caption := CustomMessage('RuntimeStatus');
  ExtractTemporaryFiles('{tmp}\Dependencies\*.msix');
  ExtractTemporaryFile('Install-Runtime.ps1');
  LogPath := ExpandConstant('{localappdata}\AudioBule\install-runtime.log');
  ForceDirectories(ExtractFileDir(LogPath));
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\Install-Runtime.ps1') +
    '" -LogPath "' + LogPath + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := CustomMessage('RuntimeFailed') + #13#10 + LogPath
  else if ExitCode <> 0 then
    Result := CustomMessage('RuntimeFailed') + #13#10 + LogPath;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then begin
    // 仅清理指向本安装目录的启动项，保留用户设置和共享运行时。
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AudioBule', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\AudioBule.exe') + '" --startup') = 0 then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AudioBule');
  end;
end;
