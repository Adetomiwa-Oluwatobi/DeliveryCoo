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
    path('register/client/', views.VisitorRegistrationView.as_view(), name='register_client'),
    
    
    
    
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
    path('payment/', views.initiate_payment, name='initiate_payment'),
    path('order/<int:order_id>/payment/', views.payment_confirmation, name='initiates_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('order/<int:order_id>/verify-payment/', views.verify_payment, name='verify_payment'),
    
    
    
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.create_product, name='create_product'),
    path('products/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('products/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    
    # Category management (admin only)
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.create_category, name='create_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    
    # Public facing URLs
   
    path('search/', views.search_products, name='search_products'),
    path('company/<int:company_id>/', views.company_detail, name='company_detail'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Cart Management
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('checkout/', views.checkout, name='checkout'),
    
    # Public order tracking
    path('track-order/', views.public_order_tracking, name='public_order_tracking'),
    
    # Payment handling for public users
    path('payment/public/', views.public_initiate_payment, name='public_initiate_payment'),
    
    
    #delivery adresss
    path('delivery-addresses/', views.delivery_address_list, name='delivery_address_list'),
    path('delivery-addresses/create/', views.delivery_address_create, name='delivery_address_create'),
    path('delivery-addresses/<int:pk>/edit/', views.delivery_address_edit, name='delivery_address_edit'),
    path('delivery-addresses/<int:pk>/delete/', views.delivery_address_delete, name='delivery_address_delete'),
    path('delivery-addresses/<int:pk>/toggle/', views.delivery_address_toggle_status, name='delivery_address_toggle'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

   