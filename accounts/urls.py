from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views
from . import views_profile
from . import views_block
from . import views_block
from . import views_firebase
from . import notifications

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('search/', views.UserSearchView.as_view(), name='user_search'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # Profile Management
    path('profile/get/', views_profile.GetProfileView.as_view(), name='get_profile'),
    path('users/<int:user_id>/', views_profile.GetUserProfileView.as_view(), name='get_user_profile'),
    path('profile/update/', views_profile.UpdateProfileView.as_view(), name='update_profile'),
    path('profile/username/', views_profile.UpdateUsernameView.as_view(), name='update_username'),
    path('profile/username/check/', views_profile.CheckUsernameAvailabilityView.as_view(), name='check_username'),
    path('profile/picture/', views_profile.UploadProfilePictureView.as_view(), name='upload_profile_picture'),
    path('profile/picture/delete/', views_profile.DeleteProfilePictureView.as_view(), name='delete_profile_picture'),
    
    # Blocking
    path('block/', views_block.BlockUserView.as_view(), name='block_user'),
    path('unblock/', views_block.UnblockUserView.as_view(), name='unblock_user'),
    path('block/status/<int:user_id>/', views_block.BlockStatusView.as_view(), name='block_status'),
    
    # Firebase Sync
    path('firebase-sync/', views_firebase.FirebaseSyncView.as_view(), name='firebase_sync'),

    # Notifications (Free relay via Django)
    path('notifications/send/', notifications.send_notification, name='send_notification'),
]
