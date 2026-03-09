; Inno Setup script for Backup Organizer Lite
#define MyAppName "Backup Organizer Lite"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Backup Organizer"
#define MyAppExeName "BackupOrganizerLite.exe"

[Setup]
AppId={{5C66D9E5-8CB5-466B-9764-0131A2CD5A82}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Backup Organizer Lite
DefaultGroupName=Backup Organizer Lite
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=BackupOrganizerLite_Setup

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\BackupOrganizerLite\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\docs\HELPME_UI.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\Backup Organizer Lite"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar Backup Organizer Lite"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Backup Organizer Lite"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar Backup Organizer Lite agora"; Flags: nowait postinstall skipifsilent
