#!/usr/bin/env python
import os
import sys

# 加载环境变量（从.env文件）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv未安装，跳过

# 清理环境变量中的代理设置，确保Django服务器启动时不受代理影响
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

os.environ['NO_PROXY'] = 'ark.cn-beijing.volces.com,localhost,127.0.0.1'

# =========================================================
# (!!!) 网络修复模块：必须放在最前面 (!!!)
# =========================================================
# 1. 强制走国内镜像 (解决 Hugging Face 连接超时)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 2. 暴力解决 SSL 证书报错
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


# =========================================================

def main():
    """Run administrative tasks."""
    # (!!!) 这里已经帮您改好了，指向 smart_search_project.settings (!!!)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_search_project.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()