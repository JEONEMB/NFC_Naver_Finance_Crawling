from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('naver/', include('pjt06.naver.urls'))
]
