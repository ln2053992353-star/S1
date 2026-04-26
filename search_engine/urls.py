from django.urls import path
from . import views

urlpatterns = [
    # 将根 URL (例如 127.0.0.1:8000) 指向我们的 search_view 视图
    path('', views.search_view, name='search'),
]