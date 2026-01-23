from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Thêm đường dẫn gốc (rỗng) trỏ về home
    path('', views.home, name='index'),
    path('home/', views.home, name='home'),

    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),

    path('quest/', views.question_page, name="quest-page"),
    path('question/<int:id>/', views.question_detail, name='question_detail'),
    path('ask/', views.add_question, name='add_question'),

    path('users/', views.users_view, name='users'),
    path('user/<str:username>/', views.user_profile, name='user_profile'),

    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
         name='password_reset'),

    # 2. Thông báo "Đã gửi email"
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),

    # 3. Trang nhập mật khẩu mới (Link từ email trỏ về đây)
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),

    # 4. Thông báo "Đổi mật khẩu thành công"
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),


    path('admin-dashboard/',views.admin_dashboard, name='admin_dashboard'),
    path('delete-question/<int:id>/', views.delete_question, name='delete_question'),
    path('admin-users/', views.admin_users, name='admin_users'),
    path('toggle-staff/<int:user_id>/', views.toggle_staff, name='toggle_staff'),
    path('toggle-active/<int:user_id>/', views.toggle_active, name='toggle_active'),
    path('api/search_similar/', views.search_similar_questions, name='search_similar_questions'),

    path('answer/<int:id>/', views.accept_answer, name='accept_answer'),
    #path('account/',views.manage_account,name='manage_account'),
    path('tags/',views.tags_view,name='tags'),

    path('api/search_similar/', views.search_similar_questions, name='search_similar_questions'),

    path('answer/<int:id>/', views.accept_answer, name='accept_answer'),
    path('manage-account/', views.manage_account, name='manage_account'),
    path('admin-question/',views.admin_question, name='admin_question'),
    path('admin-tag/',views.admin_tag, name='admin_tag'),
    path('delete-adquestion/<int:id>/', views.delete_admin_question, name='delete-adquestion'),
   path('delete-adtag/<int:id>/', views.del_tag, name='delete-adtag'),
    path('admin-answer/',views.admin_answer, name='admin_answer'),
    path('delete-adanswer/<int:id>/', views.del_answer, name='delete-adanswer'),
    path('toggle-answer/<int:id>/', views.toggle_answer, name='toggle-answer'),
    path('admin-report/', views.admin_report, name='admin_report'),
    path('resolve-report/<int:id>/', views.resolve_report, name='resolve_report'),

    path('answer/toggle-hide/<int:id>/', views.toggle_hide_answer, name='toggle_hide_answer'),
    path('report/<str:content_type>/<int:content_id>/', views.report_content, name='report_content'),
    path('question/<int:question_id>/toggle-lock/', views.toggle_lock_question, name='toggle_lock_question'),
    path('vote/<str:content_type>/<int:content_id>/<str:vote_type>/', views.vote, name='vote'),
]