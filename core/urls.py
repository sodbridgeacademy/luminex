from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView, ProfileView, OrganizationViewSet, UserListView, OrgRegisterView, OrganizationListView, \
    AssessmentViewSet, QuestionViewSet, StartTestView, NextQuestionView, SubmitAnswerView, CompleteTestView, ResultReviewView, \
     ForgotPasswordView,ResetPasswordView

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/org-register/', OrgRegisterView.as_view(), name='org-register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('organizations/', OrganizationListView.as_view(), name='org-list'),

    path("auth/forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("auth/reset-password/", ResetPasswordView.as_view(), name="reset-password"),

    path('assessments/', AssessmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='assessment-list'),
    path('assessments/<int:pk>/', AssessmentViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update', 
        'delete': 'destroy'
    }), name='assessment-detail'),
    
    path('questions/', QuestionViewSet.as_view({'get': 'list', 'post': 'create'}), name='question-list'),
    path('questions/<int:pk>/', QuestionViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update', 
        'delete': 'destroy'
    }), name='question-detail'),

    path('tests/start/', StartTestView.as_view(), name='start-test'),
    path('tests/<int:session_id>/next/', NextQuestionView.as_view(), name='next-question'),
    path('tests/<int:session_id>/submit/', SubmitAnswerView.as_view(), name='submit-answer'),
    path('tests/<int:session_id>/complete/', CompleteTestView.as_view(), name='complete-test'),
    path('results/<int:session_id>/review/', ResultReviewView.as_view(), name='result-review'),

    
    # Organizations
    path('', include(router.urls)),
]


# https://forms.gle/ynyY64TAnY5rqYUM8
