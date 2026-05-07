"""
Django settings for smart_search_project project.
"""

from pathlib import Path
import os  # <--- 确保这一行存在 (我们上次修复的)

# 清理环境变量中的代理设置，确保Django配置加载时不受代理影响
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# (您可以保留您文件中已有的key，或者用这个新的)
SECRET_KEY = 'django-insecure-@d(7_i!f#i8!q$9^c*0@a+v5o!g+g@f+f)t#k*h&a9=y7'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'database',
    'search_engine'# <--- (!!!) 在这里添加我们的 'database' app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'smart_search_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_search_project.wsgi.application'


# (!!!) 数据库配置 (!!!)
# 替换成您的 MySQL (demo1) 数据库信息
# 优先使用 .env 文件中的配置，否则使用默认硬编码值
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.getenv('DB_NAME', 'demo1'),         # 您的数据库名
        'USER': os.getenv('DB_USER', '13892277786'),          # 您的 MySQL 用户名
        'PASSWORD': os.getenv('DB_PASSWORD', 'ln20050924'),    # 您的 MySQL 密码
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '3306'),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us' # 从 'zh-hans' 改为 'en-us'
TIME_ZONE = 'UTC'       # 从 'Asia/Shanghai' 改为 'UTC' (标准时间)
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'frontend',
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================================================
# 自定义配置 - 智能搜索引擎
# ==============================================================================

# 火山引擎API配置
LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL_NAME = "ep-20251211173243-qklb7"

# 向量模型配置
EMBEDDING_MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"
EMBEDDING_DIMENSION = 768

# 搜索阈值配置
VECTOR_INITIAL_THRESHOLD = 0.1      # 向量搜索初始阈值（保证召回率）
VECTOR_FINAL_THRESHOLD = 0.2        # 最终过滤阈值
MIN_RESULTS_THRESHOLD = 5           # 最小结果数量阈值

# FAISS索引配置
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "data", "faiss_index.bin")

# 日志配置
LOGGING_LEVEL = "INFO"
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"