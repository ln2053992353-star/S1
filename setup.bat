@echo off
chcp 65001 >nul
title 智能搜索项目 — 环境配置工具
echo ============================================
echo  智能搜索项目 - 一键环境配置脚本
echo ============================================
echo.

:: 检查Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装 Python 3.13
    pause
    exit /b 1
)
echo [OK] Python 检测成功
python --version

:: 检查虚拟环境
if not exist ".venv" (
    echo.
    echo [信息] 未检测到虚拟环境，正在创建...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
) else (
    echo [OK] 虚拟环境已存在
)

:: 激活虚拟环境并安装依赖
echo.
echo [信息] 正在安装依赖（使用清华镜像源）...
call .venv\Scripts\activate.bat && pip install -r requirements_current.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，请检查 requirements_current.txt
) else (
    echo [OK] 依赖安装完成
)

:: 检查 .env 文件
echo.
if exist ".env" (
    echo [OK] .env 文件已存在
) else (
    echo [警告] 未找到 .env 文件！请从项目文档复制配置并创建 .env 文件
)

:: 检查数据目录
echo.
if exist "data\faiss_index.bin" (
    echo [OK] FAISS索引文件已存在
) else (
    echo [信息] FAISS索引文件不存在，启动时将自动构建
)

:: 检查PDF目录
echo.
if exist "D:\code\pdfs_to_process" (
    echo [OK] PDF处理目录已存在
) else (
    echo [信息] 创建 PDF 处理目录...
    mkdir "D:\code\pdfs_to_process" 2>nul
    mkdir "D:\code\processed_pdfs" 2>nul
    echo [OK] PDF目录已创建
)

:: 运行数据库迁移
echo.
echo [信息] 运行数据库迁移...
python manage.py migrate
if %errorlevel% neq 0 (
    echo [警告] 数据库迁移失败，请检查MySQL是否已启动以及 .env 配置是否正确
) else (
    echo [OK] 数据库迁移完成
)

echo.
echo ============================================
echo  环境配置完成！
echo.
echo  启动开发服务器:
echo    python manage.py runserver 0.0.0.0:8000
echo.
echo  访问搜索页面:
echo    http://localhost:8000/?q=测试
echo.
echo  运行PDF提取（需放置PDF到 D:\code\pdfs_to_process）:
echo    cd 250 ^&^& python 250.py
echo ============================================
pause
