from django.urls import path

from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view()),
    path('auth/login/', views.LoginView.as_view()),
    path('auth/token/refresh/', views.TokenRefreshView.as_view()),
    path('me/', views.MeView.as_view()),
    path('artifacts/', views.ArtifactListCreateView.as_view()),
    path('artifacts/remove-by-external/', views.ArtifactRemoveByExternalView.as_view()),
    path('artifacts/<int:pk>/', views.ArtifactDetailView.as_view()),
    path('favorites/toggle/', views.FavoriteToggleView.as_view()),
    path('recent-searches/', views.RecentSearchListView.as_view()),
    path('recent-searches/clear/', views.RecentSearchClearView.as_view()),
    path('bookings/', views.BookingListCreateView.as_view()),
    path('bookings/<int:pk>/cancel/', views.BookingCancelView.as_view()),
    path('flights/', views.FlightListView.as_view()),
    path('hotels/', views.HotelListView.as_view()),
    path('travel/agent/', views.TravelAgentView.as_view()),
]
