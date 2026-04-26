from django.contrib import admin
from django.urls import path, include # 确保导入了 'include'

urlpatterns = [
    path('admin/', admin.site.urls),
    # (!!!) 关键 (!!!)
    # 当用户访问根目录时，将请求转发到 'search_engine.urls'
    path('', include('search_engine.urls')), 
]