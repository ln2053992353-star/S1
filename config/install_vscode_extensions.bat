@echo off
echo ========================================
echo VS Code扩展自动安装脚本
echo ========================================
echo.

REM 检查code命令是否可用
where code >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到code命令，请确保VS Code已安装并添加到PATH
    echo 尝试使用默认路径...
    set "CODE_CMD=D:\Microsoft VS Code\bin\code"
) else (
    set "CODE_CMD=code"
)

REM 必需扩展列表
set "EXTENSIONS[0]=ms-python.python"
set "EXTENSIONS[1]=ms-python.vscode-pylance"
set "EXTENSIONS[2]=batisteo.vscode-django"
set "EXTENSIONS[3]=cweijan.vscode-mysql-client2"

echo 正在检查已安装的扩展...
echo.

REM 获取已安装扩展列表
"%CODE_CMD%" --list-extensions > installed_extensions.txt 2>&1

setlocal enabledelayedexpansion
set /a installed_count=0
set /a missing_count=0

echo 必需扩展列表：
echo --------------------

for %%i in (0 1 2 3) do (
    set "ext=!EXTENSIONS[%%i]!"

    REM 检查扩展是否已安装
    findstr /i "!ext!" installed_extensions.txt >nul
    if !errorlevel! equ 0 (
        echo ✅ !ext! - 已安装
        set /a installed_count+=1
    ) else (
        echo ❌ !ext! - 未安装
        set /a missing_count+=1
        set "MISSING[!missing_count!]=!ext!"
    )
)

echo.
echo 统计: 已安装 !installed_count!/4，缺失 !missing_count!/4
echo.

if !missing_count! gtr 0 (
    echo 正在安装缺失的扩展...
    echo.

    for /l %%i in (1,1,!missing_count!) do (
        set "ext=!MISSING[%%i]!"
        echo 安装 !ext!...
        "%CODE_CMD%" --install-extension !ext!
        if !errorlevel! equ 0 (
            echo ✅ !ext! 安装成功
        ) else (
            echo ❌ !ext! 安装失败
        )
        echo.
    )

    echo 安装完成！
) else (
    echo 所有必需扩展已安装 ✓
)

REM 清理临时文件
del installed_extensions.txt >nul 2>&1

echo.
echo ========================================
echo 脚本执行完成
echo ========================================
echo.
echo 接下来请：
echo 1. 在VS Code中打开项目文件夹
echo 2. 按 Ctrl+Shift+P，输入 "Python: Select Interpreter"
echo 3. 选择您的Python环境（Conda环境）
echo 4. 按 F5 启动Django服务器
echo.
pause