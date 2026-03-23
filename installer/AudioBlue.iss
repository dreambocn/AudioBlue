; AudioBlue installer scaffold for Inno Setup 6
; This script is a verification-ready baseline and may be extended by release automation.

[Setup]
AppId={{7EFAE4E9-D6EF-4A57-BE35-8C2D205EF001}
AppName=AudioBlue
AppVersion=0.1.0
AppPublisher=AudioBlue Team
DefaultDirName={autopf}\AudioBlue
DefaultGroupName=AudioBlue
SetupIconFile=..\assets\branding\audioblue-icon.ico
UninstallDisplayIcon={app}\audioblue.exe
OutputDir=..\dist\installer
OutputBaseFilename=AudioBlue-Setup
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

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AudioBlue"; ValueData: """{app}\audioblue.exe"" --background"; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AudioBlue"; Flags: deletevalue uninsdeletevalue; Tasks: autostart

[Icons]
Name: "{group}\AudioBlue"; Filename: "{app}\audioblue.exe"; Tasks: startmenu
Name: "{group}\Uninstall AudioBlue"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\AudioBlue"; Filename: "{app}\audioblue.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\audioblue.exe"; Description: "Launch AudioBlue"; Flags: nowait postinstall skipifsilent
