from django.urls import path
from .views import RoutePlanAPIView, map_view

urlpatterns = [
    path("", map_view, name="map_view"),
    path("api/route/", RoutePlanAPIView.as_view(), name="api_route"),
]
