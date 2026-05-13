; Inno Setup script for MelodySheet (Windows installer)
;
; Build with: ISCC.exe installer\melody-sheet.iss
; Expects dist\MelodySheet\ to already exist (produced by PyInstaller).
; Output: installer\out\MelodySheet-Setup.exe

#define MyAppName "MelodySheet"
#define MyAppNameZh "小提琴旋律谱"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "MelodySheet"
#define MyAppURL "https://github.com/zhang2qaz/MelodySheet-Violin"
#define MyAppExeName "MelodySheet.exe"

[Setup]
AppId={{A5F6CA3E-5A6D-4B4F-90F1-2D9C0D11B4F1}
AppName={#MyAppNameZh}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppNameZh}
DisableProgramGroupPage=yes
OutputDir=out
OutputBaseFilename=MelodySheet-Setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=melody-sheet.ico
DisableDirPage=no
DisableReadyPage=no
LicenseFile=

[Languages]
; Chocolatey's Inno Setup install only ships the default (English) language
; file. The app's UI strings (AppName, group, shortcuts) already contain
; Chinese text via constants, so the wizard chrome being English is fine.
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Recurse the PyInstaller output. The repo-relative `..\dist\MelodySheet\*`
; must exist before running ISCC.
Source: "..\dist\MelodySheet\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppNameZh}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppNameZh}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameZh}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppNameZh}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Don't keep storage caches under Program Files (the launcher writes to %APPDATA%
; instead). Just clean Program Files.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
