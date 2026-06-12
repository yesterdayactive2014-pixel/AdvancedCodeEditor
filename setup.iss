; Advanced Code Editor + Alan AI — Inno Setup
; Requires Inno Setup 6+ (https://jrsoftware.org/isdl.php)

#define MyAppName "Advanced Code Editor + Alan AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AnzerScript"
#define MyAppURL "https://github.com/anzerscript/alan-code-editor"
#define MyAppExeName "CodeEditor.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\CodeEditor
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Windows 7 SP1 and newer
MinVersion=6.1.7601
PrivilegesRequired=admin
OutputDir=installer
OutputBaseFilename=CodeEditor_Setup_{#MyAppVersion}
;SetupIconFile=assets\python-original.svg  ; конвертируйте .svg → .ico для иконки
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra
SolidCompression=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: checkablealone

[Files]
; Главный исполняемый файл редактора
Source: "dist\CodeEditor.exe"; DestDir: "{app}"; Flags: ignoreversion

; Ollama — встроенный движок
Source: "ollama\ollama.exe"; DestDir: "{app}\ollama"; Flags: ignoreversion

; AlanTrain (скрипты обучения, нейросеть)
Source: "AlanTrain\*"; DestDir: "{app}\AlanTrain"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ресурсы (иконки языков)
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; version.json для автообновления (локальная копия)
Source: "version.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Запускаем редактор после установки
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Останавливаем ollama если запущен
Filename: "{app}\ollama\ollama.exe"; Parameters: "stop llama3:8b"; Flags: runhidden skipifdoesntexist

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;
