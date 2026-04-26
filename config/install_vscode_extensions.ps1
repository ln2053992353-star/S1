# VS Code扩展自动安装脚本 (PowerShell版本)
# 以管理员身份运行或在普通PowerShell中运行

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "VS Code扩展自动安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查code命令是否可用
$codeCmd = $null
if (Get-Command code -ErrorAction SilentlyContinue) {
    $codeCmd = "code"
    Write-Host "✅ 找到code命令" -ForegroundColor Green
} else {
    Write-Host "⚠️  未在PATH中找到code命令，尝试使用默认路径..." -ForegroundColor Yellow
    $defaultPath = "D:\Microsoft VS Code\bin\code"
    if (Test-Path $defaultPath) {
        $codeCmd = $defaultPath
        Write-Host "✅ 使用默认路径: $codeCmd" -ForegroundColor Green
    } else {
        Write-Host "❌ 未找到VS Code，请确保已安装VS Code" -ForegroundColor Red
        exit 1
    }
}

# 必需扩展列表
$requiredExtensions = @(
    "ms-python.python",           # Python扩展
    "ms-python.vscode-pylance",   # Pylance语言服务器
    "batisteo.vscode-django",     # Django扩展
    "cweijan.vscode-mysql-client2" # MySQL扩展
)

Write-Host "正在检查已安装的扩展..." -ForegroundColor Cyan
Write-Host ""

# 获取已安装扩展列表
try {
    $installedExtensions = & $codeCmd --list-extensions
} catch {
    Write-Host "❌ 无法获取已安装扩展列表: $_" -ForegroundColor Red
    exit 1
}

Write-Host "必需扩展列表：" -ForegroundColor Cyan
Write-Host "--------------------" -ForegroundColor Cyan

$installedCount = 0
$missingExtensions = @()

foreach ($ext in $requiredExtensions) {
    if ($installedExtensions -match [regex]::Escape($ext)) {
        Write-Host "✅ $ext - 已安装" -ForegroundColor Green
        $installedCount++
    } else {
        Write-Host "❌ $ext - 未安装" -ForegroundColor Red
        $missingExtensions += $ext
    }
}

Write-Host ""
Write-Host "统计: 已安装 $installedCount/4，缺失 $($missingExtensions.Count)/4" -ForegroundColor Cyan
Write-Host ""

if ($missingExtensions.Count -gt 0) {
    Write-Host "正在安装缺失的扩展..." -ForegroundColor Cyan
    Write-Host ""

    foreach ($ext in $missingExtensions) {
        Write-Host "安装 $ext..." -ForegroundColor Yellow
        try {
            & $codeCmd --install-extension $ext
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ $ext 安装成功" -ForegroundColor Green
            } else {
                Write-Host "❌ $ext 安装失败" -ForegroundColor Red
            }
        } catch {
            Write-Host "❌ $ext 安装出错: $_" -ForegroundColor Red
        }
        Write-Host ""
    }

    Write-Host "安装完成！" -ForegroundColor Green
} else {
    Write-Host "所有必需扩展已安装 ✓" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "脚本执行完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "接下来请：" -ForegroundColor Cyan
Write-Host "1. 在VS Code中打开项目文件夹" -ForegroundColor White
Write-Host "2. 按 Ctrl+Shift+P，输入 'Python: Select Interpreter'" -ForegroundColor White
Write-Host "3. 选择您的Python环境（Conda环境）" -ForegroundColor White
Write-Host "4. 按 F5 启动Django服务器" -ForegroundColor White
Write-Host ""
Write-Host "按任意键继续..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")