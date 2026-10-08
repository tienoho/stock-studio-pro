#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{5E6A7D8F-2B4C-4E1A-8B9C-3D5E7F9A1B2C}
AppName=AutoStock Studio Pro
AppVersion={#AppVersion}
AppVerName=AutoStock Studio Pro {#AppVersion}
AppPublisher=AutoStock Studio
AppPublisherURL=https://github.com/tienoho/stock-studio-pro
AppSupportURL=https://github.com/tienoho/stock-studio-pro/issues
AppUpdatesURL=https://github.com/tienoho/stock-studio-pro/releases
DefaultDirName={autopf}\AutoStock Studio Pro
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AutoStockStudio-Setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\AutoStockStudio.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "release_autostock_studio\AutoStockStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "release_autostock_studio\run_exe.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "release_autostock_studio\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AutoStock Studio Pro"; Filename: "{app}\AutoStockStudio.exe"
Name: "{autodesktop}\AutoStock Studio Pro"; Filename: "{app}\AutoStockStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AutoStockStudio.exe"; Description: "{cm:LaunchProgram,AutoStock Studio Pro}"; Flags: nowait postinstall skipifsilent
