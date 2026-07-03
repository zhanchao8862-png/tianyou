@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   天佑编辑器 - EXE 构建
echo ========================================
echo.

REM 删除旧 EXE
if exist "dist\tianyou_editor.exe" del "dist\tianyou_editor.exe"

REM 清理上次 build
rd /s /q "build\tianyou_editor" 2>nul

REM 确保 CRT manifest 存在（解决 MSVCR90.dll 0xc0000142 问题）
if not exist "build\Microsoft.VC90.CRT.manifest" (
    echo 错误：缺少 build\Microsoft.VC90.CRT.manifest
    pause
    exit /b 1
)

echo 正在打包...
pyinstaller --onefile --noconsole ^
    --add-binary="C:\Python27\msvcr90.dll;." ^
    --add-binary="build\Microsoft.VC90.CRT.manifest;." ^
    --distpath="dist" ^
    --workpath="build" ^
    --specpath="build" ^
    --name="tianyou_editor" ^
    "tianyou_editor.py"

if exist "dist\tianyou_editor.exe" (
    echo.
    echo ========================================
    echo   ✅ 构建成功！
    echo   %cd%\dist\tianyou_editor.exe
    echo ========================================
) else (
    echo.
    echo ========================================
    echo   ❌ 构建失败
    echo ========================================
)
pause
