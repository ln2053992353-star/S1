# VS Code 开发环境配置指南

## 概述
本文档指导您将 `smart_search_project` Django 项目从 PyCharm 迁移到 VS Code 进行开发。

## 已完成配置
✅ 已创建以下配置文件：
- `requirements.txt` - Python依赖清单
- `.vscode/launch.json` - 调试配置
- `.vscode/settings.json` - VS Code设置
- `.env` - 环境变量文件
- `manage.py` - 已添加dotenv支持

## 第一步：安装VS Code扩展

### 必需扩展
1. **Python** (ms-python.python) - Python语言支持
2. **Pylance** (ms-python.vscode-pylance) - Python智能提示
3. **Django** (batisteo.vscode-django) - Django语法高亮
4. **MySQL** (cweijan.vscode-mysql-client2) - 数据库管理

### 安装方法
- 打开VS Code
- 点击左侧活动栏的扩展图标（或按 `Ctrl+Shift+X`）
- 搜索扩展名称并安装

## 第二步：打开项目并配置Python解释器

1. **打开项目**
   - 启动VS Code
   - 文件 → 打开文件夹 → 选择 `D:\code\smart_search_project`
   - 或使用命令面板：`Ctrl+Shift+P` → "File: Open Folder"

2. **选择Python解释器**
   - 按 `Ctrl+Shift+P` 打开命令面板
   - 输入 "Python: Select Interpreter"
   - 选择您的Conda环境Python路径，例如：
     - `C:\Users\<用户名>\anaconda3\envs\<环境名>\python.exe`
     - 或系统Python路径

3. **验证环境**
   - 打开集成终端：`Ctrl+``
   - 运行：`python --version`
   - 应该显示Python 3.9或3.11

## 第三步：安装依赖包

如果尚未安装依赖，在终端中运行：
```bash
# 激活Conda环境（如果使用Conda）
conda activate <环境名>

# 安装依赖
pip install -r requirements.txt
```

## 第四步：配置数据库

1. **确保MySQL服务运行**
   ```bash
   # 启动MySQL服务（Windows）
   net start MySQL80
   ```

2. **验证数据库连接**
   - 数据库配置已在 `.env` 文件中设置
   - 默认配置：
     - 主机：localhost
     - 端口：3306
     - 数据库：demo1
     - 用户：root
     - 密码：123456

3. **运行数据库迁移**
   ```bash
   python manage.py migrate
   ```

## 第五步：运行和调试项目

### 运行Django服务器
1. **方法一：使用VS Code调试**
   - 按 `F5` 或点击左侧运行和调试图标
   - 选择 "Django: Run Server"
   - 访问 http://127.0.0.1:8000

2. **方法二：使用终端**
   ```bash
   python manage.py runserver
   ```

### 调试功能
1. **设置断点**
   - 在代码行号左侧点击设置断点（红色圆点）
   - 推荐在 `search_engine/views.py` 的 `search_view` 函数中测试

2. **启动调试**
   - 按 `F5` 选择 "Django: Debug Server"
   - 访问网站触发断点
   - 使用调试工具栏：继续、单步执行、查看变量

### 可用调试配置
- **Django: Run Server** - 正常启动服务器
- **Django: Debug Server** - 调试模式启动（无自动重载）
- **Django: Make Migrations** - 创建迁移文件
- **Django: Migrate** - 应用数据库迁移
- **Django: Run Tests** - 运行测试

## 第六步：常用开发命令

### Django管理命令
```bash
# 创建超级用户
python manage.py createsuperuser

# 检查项目配置
python manage.py check

# 创建应用
python manage.py startapp <app_name>

# 运行测试
python manage.py test
```

### 搜索功能测试
1. 启动Django服务器
2. 访问 http://127.0.0.1:8000/search/
3. 输入查询词（如 "Metabolism"）
4. 查看搜索结果和AI分析

## 第七步：代码质量和格式化

### 代码格式化
- 保存时自动格式化：已配置
- 格式化工具：Black（行宽88字符）
- 自动组织导入：已启用

### 代码检查
- Pylint已启用，配置了Django插件
- 在问题面板查看代码问题

## 第八步：MySQL数据库管理（可选）

### 使用VS Code MySQL扩展
1. 安装MySQL扩展后，点击左侧数据库图标
2. 添加新连接：
   - 主机：localhost
   - 端口：3306
   - 用户：root
   - 密码：123456
   - 数据库：demo1

3. 功能：
   - 查看和编辑表数据
   - 执行SQL查询
   - 导出数据

## 故障排除

### 常见问题

#### 1. Python解释器未找到
- 确保Conda环境已创建并激活
- 在VS Code中重新选择解释器

#### 2. 数据库连接失败
```bash
# 检查MySQL服务状态
net start MySQL80

# 测试连接
python -c "import pymysql; conn = pymysql.connect(host='localhost', user='root', password='123456', database='demo1', port=3306)"
```

#### 3. 依赖包安装失败
- 使用国内镜像：
  ```bash
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

#### 4. Hugging Face模型下载慢
- 已配置国内镜像：`HF_ENDPOINT=https://hf-mirror.com`
- 检查 `.env` 文件中的设置

#### 5. VS Code无法识别Django项目
- 确保安装了Django扩展
- 重启VS Code
- 检查 `.vscode/settings.json` 配置

### 网络配置
- **HF镜像**：已设置为 `https://hf-mirror.com`
- **代理排除**：`ark.cn-beijing.volces.com,localhost,127.0.0.1`
- **SSL验证**：已在 `manage.py` 中禁用（仅开发环境）

## 从PyCharm迁移的注意事项

### 配置差异
1. **运行配置**：PyCharm的运行配置已转换为VS Code的 `launch.json`
2. **代码风格**：PyCharm代码风格设置已迁移到VS Code格式化配置
3. **数据库工具**：使用VS Code的MySQL扩展替代PyCharm的数据库工具

### 保留文件
- `.idea/` 目录：可保留或删除，不影响VS Code使用
- PyCharm运行配置：已不再需要

### 建议工作流
1. **版本控制**：考虑初始化Git仓库
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **依赖管理**：使用 `requirements.txt` 记录所有依赖
3. **环境隔离**：继续使用Conda环境进行依赖管理

## 高级配置（可选）

### 自定义设置
编辑 `.vscode/settings.json` 可修改：
- 代码格式化规则
- 文件排除模式
- 终端环境变量

### 添加新调试配置
编辑 `.vscode/launch.json` 可添加：
- 自定义Python脚本调试
- 测试运行器配置
- 其他Django管理命令

## 技术支持
- VS Code文档：https://code.visualstudio.com/docs
- Django文档：https://docs.djangoproject.com
- Python扩展文档：https://code.visualstudio.com/docs/python/python-tutorial

## 下一步
1. 测试所有搜索功能是否正常工作
2. 运行完整测试套件：`python manage.py test`
3. 考虑设置持续集成（CI）
4. 优化开发工作流

---
*最后更新：2026-03-17*
*配置文件版本：1.0*