from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/company/', views.CompanyRegistrationView.as_view(), name='register_company'),
    path('register/delivery/', views.DeliveryPersonnelRegistrationView.as_view(), name='register_delivery'),
    
    
    # Dashboard URLs
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/company/', views.company_dashboard, name='company_dashboard'),
    path('dashboard/delivery/', views.delivery_dashboard, name='delivery_dashboard'),
    
    
    path('create/', views.create_order, name='create_order'),
    path('list/', views.order_list, name='order_list'),
    path('assign/<int:order_id>/', views.assign_delivery, name='assign_delivery'),
    path('tracking/<int:order_id>/', views.order_tracking, name='order_tracking'),
    path('orders/new/', views.new_order, name='new_order'),
    
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/edit/', views.edit_order, name='edit_order'),
    path('orders/<int:order_id>/delete/', views.delete_order, name='delete_order'),
    
    # Order management and tracking
    
    path('orders/<int:order_id>/update/', views.order_update, name='order_update'),
    path('orders/<int:order_id>/log/', views.add_delivery_log, name='add_delivery_log'),
    
    # Shipping label
    path('orders/<int:order_id>/label/', views.print_label, name='print_label'),
    
    # Payment processing
    path('orders/<int:order_id>/payment/', views.initiate_payment, name='initiate_payment'),
    path('order/<int:order_id>/payment/', views.payment_confirmation, name='initiate_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('order/<int:order_id>/verify-payment/', views.verify_payment, name='verify_payment'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

   