from datetime import timezone
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import *
from .forms import CategoryForm, OrderForm, OrderTrackingForm, ProductForm, VisitorPasswordChangeForm, VisitorProfileUpdateForm, VisitorRegistrationForm
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client as TwilioClient
from django.contrib import messages
import io
from reportlab.pdfgen import canvas
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
from .models import DeliveryAddress
from .forms import DeliveryAddressForm
from django.contrib.auth import update_session_auth_hash
from reportlab.lib.pagesizes import letter
from django.db.models import Q
from .models import (
    CustomUser, ADMIN, COMPANY, DELIVERY_PERSONNEL,
    Company, DeliveryPersonnel, Order, OrderTracking, DeliveryLog
)


from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView, ListView
from .forms import (
    CompanyRegistrationForm, DeliveryPersonnelRegistrationForm, 
    CustomLoginForm
)

def landing_page(request):
    """View for the main landing page"""
    categories = Category.objects.all().order_by('name')[:6]  # Limit to top 6 categories
    companies = Company.objects.all().order_by('name')[:8]    # Limit to top 8 companies
    
    # Get a few featured products
    featured_products = Product.objects.filter(available=True).order_by('-created_at')[:6]
    context = {
        'categories': categories,
        'companies': companies,
        'featured_products': featured_products,
    }
    return render(request, 'orders/landing_page.html',context)

@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY])
@login_required
def create_order(request):
    """
    View for creating orders directly (for Admin and Company users).
    """
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            
            # If company user, set company automatically
            if request.user.role == COMPANY:
                order.company = request.user.company_profile
            
            # Set initial payment status
            order.payment_status = 'pending'
                
            # If the user is logged in as a visitor, link the order to their account
            if request.user.role == VISITOR:
                order.visitor_user = request.user
                
            order.save()
            messages.success(request, "Order created successfully! Proceeding to payment.")
            
            # Redirect to payment confirmation page
            return redirect('initiate_payment', order_id=order.id)
    else:
        form = OrderForm()
        
        # If company user, filter clients to only show company's clients
        if request.user.role == COMPANY:
            form.fields['company'].initial = request.user.company_profile
            form.fields['company'].widget = forms.HiddenInput()
    
    return render(request, 'orders/create_order.html', {'form': form})
@login_required
def order_list(request):
    # Filter orders based on user role
    user = request.user
    
    if user.role == ADMIN:
        orders = Order.objects.all().order_by('-id')
    elif user.role == COMPANY:
        company = user.company_profile
        orders = Order.objects.filter(company=company).order_by('-id')
    elif user.role == VISITOR:
        try:
            # Get the visitor profile
            visitor = user.visitor_profile
            
            # Find orders by matching email
            orders = Order.objects.filter(client_email=visitor.user.email).order_by('-id')
            
            # Optional: Add name matching for additional reliability
            # orders = Order.objects.filter(
            #     client_email=visitor.email,
            #     client_name=visitor.name
            # ).order_by('-id')
            
        except Visitor.DoesNotExist:
            orders = Order.objects.none()
    elif user.role == DELIVERY_PERSONNEL:
        delivery_personnel = user.delivery_profile
        orders = Order.objects.filter(ordertracking__assigned_to=delivery_personnel).order_by('-id')
    else:
        orders = Order.objects.none()
    
    # Count orders by status for dashboard stats
    pending_count = orders.filter(status='pending').count()
    transit_count = orders.filter(status='transit').count()
    delivered_count = orders.filter(status='delivered').count()
    
    context = {
        'orders': orders,
        'pending_count': pending_count,
        'transit_count': transit_count,
        'delivered_count': delivered_count,
    }
    return render(request, 'orders/order_list.html', context)

def assign_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        form = OrderTrackingForm(request.POST)
        if form.is_valid():
            tracking = form.save(commit=False)
            tracking.order = order
            
            # Mark the assigned delivery personnel as unavailable
            delivery_person = form.cleaned_data['assigned_to']
            delivery_person.available = False
            delivery_person.save()
            
            tracking.save()
            order.status = 'pending'  # Update order status
            order.save()
            messages.success(request, "Delivery personnel assigned successfully!")
            return redirect('order_tracking', order_id=order.id)
    else:
        form = OrderTrackingForm()
    return render(request, 'orders/assign_delivery.html', {'form': form, 'order': order})

def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    tracking_info = OrderTracking.objects.filter(order=order)
    return render(request, 'orders/order_tracking.html', {'order': order, 'tracking_info': tracking_info})

def add_delivery_log(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        distance_traveled = request.POST['distance_traveled']
        feedback = request.POST['feedback']
        delivery_personnel = request.user.delivery_profile  # Assuming the user is a delivery personnel
        DeliveryLog.objects.create(
            order=order,
            delivery_personnel=delivery_personnel,
            distance_traveled=distance_traveled,
            feedback=feedback
        )
        messages.success(request, "Delivery log added successfully!")
        return redirect('order_tracking', order_id=order.id)

def send_order_update_email(order):
    subject = f"Order #{order.id} Status Updated"
    message = f"Your order has been updated. New Status: {order.status}"
    
    # Check if client email is provided
    if order.client_email:
        recipient_list = [order.client_email]
        send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)

def order_update(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        new_status = request.POST['status']
        order.status = new_status
        order.save()
        
        # If order is delivered or canceled, mark delivery personnel as available again
        if new_status in ['delivered', 'canceled']:
            try:
                tracking = OrderTracking.objects.get(order=order)
                if tracking.assigned_to:
                    delivery_person = tracking.assigned_to
                    delivery_person.available = True
                    delivery_person.save()
            except OrderTracking.DoesNotExist:
                pass
                
        send_order_update_email(order)  # Send notification
        
        # If client phone is available, send SMS
        if order.client_phone:
            send_sms_notification(order)
            
        messages.success(request, "Order status updated successfully!")
        return redirect('order_tracking', order_id=order.id)

def send_sms(phone_number, message):
    # Import your Twilio client setup
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    # Format the phone number to E.164
    # Assuming Nigerian numbers (adjust the country code as needed)
    formatted_number = phone_number
    
    # If number starts with 0, replace it with country code
    if phone_number.startswith('0'):
        formatted_number = '+234' + phone_number[1:]
    # If number doesn't have + but has country code, add +
    elif not phone_number.startswith('+'):
        formatted_number = '+' + phone_number
    
    try:
        # Send the message with the formatted number
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=formatted_number
        )
    except Exception as e:
        # Log the error but don't break application flow
        print(f"Failed to send SMS: {e}")
        # Potentially log this to your logging system

def send_sms_notification(order):
    message = f"Your order #{order.id} has been updated. Status: {order.status}"
    send_sms(order.client_phone, message)

from paystackapi.transaction import Transaction

def initiate_payment(request, order_id):
    """View for initiating Paystack payment for an order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Determine amount to charge: total_cost if it exists and > 0, otherwise delivery_cost
    if hasattr(order, 'total_cost') and order.total_cost and order.total_cost > 0:
        payment_amount = order.total_cost
    else:
        payment_amount = order.delivery_cost
    
    # Convert to kobo (Paystack accepts amount in smallest currency unit)
    amount = int(payment_amount * 100)
    
    # If client email is not provided, use company email or a default
    # Replace the problematic section with:
    email_to_use = order.client_email or request.user.email

    if not email_to_use:
        messages.error(request, "Email address is required for payment processing.")
        return redirect('order_detail', order_id=order.id)
    
    
    # Generate a unique reference by combining order ID with timestamp
    from datetime import datetime
    unique_ref = f"order-{order.id}-{int(datetime.now().timestamp())}"
    
    # Set up metadata for tracking
    metadata = {
        'order_id': order.id,
        'client_name': order.client_name,
        'company_id': order.company.id if order.company else None,
        'payment_amount': str(payment_amount),  # Include amount in metadata for tracking
    }
    
    # Get the callback URL for Paystack to return to
    callback_url = request.build_absolute_uri(reverse('payment_callback'))
    
    try:
        # Initialize transaction with Paystack
        from paystackapi.transaction import Transaction
        response = Transaction.initialize(
            email=email_to_use,
            amount=amount,
            reference=unique_ref,
            callback_url=callback_url,
            metadata=metadata
        )
        
        if 'status' in response and response['status']:
            # Save payment reference to order or a separate payment model
            order.payment_reference = unique_ref
            order.save()
            
            # Redirect to Paystack payment page
            return redirect(response['data']['authorization_url'])
        else:
            messages.error(request, "Payment initialization failed. Please try again.")
            return redirect('order_detail', order_id=order.id)
            
    except Exception as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect('order_detail', order_id=order.id)

def payment_callback(request):
    """Handle the callback from Paystack after payment"""
    reference = request.GET.get('reference', None)
    
    if not reference:
        messages.error(request, "Payment verification failed. No reference provided.")
        return redirect('order_list')
    
    try:
        # Verify the transaction
        from paystackapi.transaction import Transaction
        from django.utils import timezone
        
        response = Transaction.verify(reference)
        
        # First try to find the order directly by payment reference
        try:
            order = Order.objects.get(payment_reference=reference)
        except Order.DoesNotExist:
            # If not found by reference, try to extract order ID from metadata
            if 'data' in response and 'metadata' in response['data'] and 'order_id' in response['data']['metadata']:
                order_id = response['data']['metadata']['order_id']
                try:
                    order = Order.objects.get(id=order_id)
                except Order.DoesNotExist:
                    messages.error(request, "Order not found with metadata ID.")
                    return redirect('order_list')
            else:
                # Try to extract from reference if it follows our format
                import re
                match = re.search(r'order-(\d+)-', reference)
                if match:
                    order_id = match.group(1)
                    try:
                        order = Order.objects.get(id=order_id)
                    except Order.DoesNotExist:
                        messages.error(request, "Order not found with reference pattern.")
                        return redirect('order_list')
                else:
                    messages.error(request, "Could not determine order from payment reference.")
                    return redirect('order_list')
        
        # Now check if payment was successful
        if 'data' in response and response['data']['status'] == 'success':
            # Update the order with payment information
            order.payment_status = 'paid'
            order.payment_date = timezone.now()
            order.save()
            
            # Log the successful payment
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Payment successful for order #{order.id}, reference: {reference}")
            
            messages.success(request, "Payment successful! Your order is now being processed.")
            return redirect('order_detail', order_id=order.id)
        else:
            # Payment failed or is pending
            payment_status = response.get('data', {}).get('status', 'unknown')
            order.payment_status = 'failed' if payment_status == 'failed' else 'pending'
            order.save()
            
            messages.warning(request, f"Payment status: {payment_status}. Please try again if needed.")
            return redirect('order_detail', order_id=order.id)
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Payment verification error: {str(e)}")
        
        messages.error(request, f"Payment verification error: {str(e)}")
        return redirect('order_list')
def payment_confirmation(request, order_id):
    """
    View to show payment confirmation page before redirecting to Paystack
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Convert to kobo (Paystack accepts amount in smallest currency unit)
    amount = int(order.delivery_cost * 100)
    
    # If client email is not provided, use company email or a default
    # Replace the problematic section with:
    email_to_use = order.client_email or request.user.email

    if not email_to_use:
        messages.error(request, "Email address is required for payment processing.")
        return redirect('order_detail', order_id=order.id)
    
    # Generate a unique reference by combining order ID with timestamp
    from datetime import datetime
    unique_ref = f"order-{order.id}-{int(datetime.now().timestamp())}"
    
    # Set up metadata for tracking
    metadata = {
        'order_id': order.id,
        'client_name': order.client_name,
        'company_id': order.company.id if order.company else None,
    }
    
    # Get the callback URL for Paystack to return to
    callback_url = request.build_absolute_uri(reverse('payment_callback'))
    
    try:
        # Initialize transaction with Paystack
        from paystackapi.transaction import Transaction
        response = Transaction.initialize(
            email=email_to_use,
            amount=amount,
            reference=unique_ref,
            callback_url=callback_url,
            metadata=metadata
        )
        
        if 'status' in response and response['status']:
            # Save payment reference to order
            order.payment_reference = unique_ref
            order.save()
            
            # Render the confirmation page with payment URL
            context = {
                'order': order,
                'payment_url': response['data']['authorization_url']
            }
            return render(request, 'orders/payment_confirmation.html', context)
        else:
            messages.error(request, "Payment initialization failed. Please try again.")
            return redirect('order_detail', order_id=order.id)
            
    except Exception as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect('order_detail', order_id=order.id)
    
def verify_payment(request, order_id):
    """
    Manually verify a payment status with Paystack
    This is useful when the callback fails to update the status
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Make sure the order has a payment reference
    if not order.payment_reference:
        messages.error(request, "No payment reference found for this order.")
        return redirect('order_detail', order_id=order.id)
    
    try:
        # Verify the transaction
        from paystackapi.transaction import Transaction
        from django.utils import timezone
        
        response = Transaction.verify(order.payment_reference)
        
        # Check if payment was successful
        if 'data' in response and response['data']['status'] == 'success':
            # Update the order with payment information
            order.payment_status = 'paid'
            order.payment_date = timezone.now()
            order.save()
            
            messages.success(request, "Payment verified successfully! Your order is now marked as paid.")
        else:
            # Payment failed or is pending
            payment_status = response.get('data', {}).get('status', 'unknown')
            order.payment_status = 'failed' if payment_status == 'failed' else 'pending'
            order.save()
            
            messages.warning(request, f"Payment status from Paystack: {payment_status}")
            
    except Exception as e:
        messages.error(request, f"Payment verification error: {str(e)}")
    
    return redirect('order_detail', order_id=order.id)

def order_detail(request, order_id):
    """View for displaying order details"""
    order = get_object_or_404(Order, id=order_id)
    tracking_info = OrderTracking.objects.filter(order=order).order_by('-timestamp')
    
    context = {
        'order': order,
        'tracking_info': tracking_info,
    }
    return render(request, 'orders/order_detail.html', context)

def edit_order(request, order_id):
    """View for editing an existing order"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f"Order #{order.id} updated successfully!")
            return redirect('order_detail', order_id=order.id)
    else:
        form = OrderForm(instance=order)
        
        # If company user, hide the company field
        if request.user.role == COMPANY:
            form.fields['company'].widget = forms.HiddenInput()
    
    context = {
        'form': form,
        'order': order,
    }
    return render(request, 'orders/edit_order.html', context)

def print_label(request, order_id):
    """View for generating a printable shipping label"""
    order = get_object_or_404(Order, id=order_id)
     
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
     
    # Add content to the PDF
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"Shipping Label - Order #{order.id}")
    # 
    p.setFont("Helvetica", 12)
    p.drawString(100, 700, f"To: {order.client_name}")
    p.drawString(100, 680, f"Address: {order.delivery_address}")
    p.drawString(100, 660, f"Phone: {order.client_phone}")
    # 
    p.save()
    buffer.seek(0)
    
    # Create the HTTP response with PDF
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="order_{order.id}_label.pdf"'
    #return response
    # For HTML template rendering approach
    context = {
        'order': order,
        'response': response,
    }
    return render(request, 'orders/print_label.html', context)
    
    # Alternatively, generate a PDF on-the-fly:
    # buffer = io.BytesIO()
    # p = canvas.Canvas(buffer, pagesize=letter)
    # 
    # # Add content to the PDF
    # p.setFont("Helvetica-Bold", 16)
    # p.drawString(100, 750, f"Shipping Label - Order #{order.id}")
    # 
    # p.setFont("Helvetica", 12)
    # p.drawString(100, 700, f"To: {order.client_name}")
    # p.drawString(100, 680, f"Address: {order.delivery_address}")
    # p.drawString(100, 660, f"Phone: {order.client_phone}")
    # 
    # p.save()
    # buffer.seek(0)
    # 
    # # Create the HTTP response with PDF
    # response = HttpResponse(buffer, content_type='application/pdf')
    # response['Content-Disposition'] = f'attachment; filename="order_{order.id}_label.pdf"'
    # return response

def delete_order(request, order_id):
    """View for deleting an order"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        order.delete()
        messages.success(request, "Order deleted successfully!")
        return redirect('order_list')
    
    context = {
        'order': order,
    }
    return render(request, 'orders/delete_order.html', context)

def new_order(request):
    """Alias for create_order to match the URL in template"""
    return create_order(request)

# Helper functions for role-based access control
def is_admin(user):
    return user.is_authenticated and user.role == ADMIN

def is_company(user):
    return user.is_authenticated and user.role == COMPANY

def is_delivery(user):
    return user.is_authenticated and user.role == DELIVERY_PERSONNEL

def is_visitor(user):
    return user.is_authenticated and user.role == VISITOR
# Custom login view
class CustomLoginView(FormView):
    template_name = 'orders/login.html'
    form_class = CustomLoginForm
    success_url = reverse_lazy('dashboard')
    
    def form_valid(self, form):
        email = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(email=email, password=password)
        
        if user is not None:
            login(self.request, user)
            
            # Redirect based on user role
            if user.role == ADMIN:
                self.success_url = reverse_lazy('admin_dashboard')
            elif user.role == COMPANY:
                self.success_url = reverse_lazy('company_dashboard')
            elif user.role == DELIVERY_PERSONNEL:
                self.success_url = reverse_lazy('delivery_dashboard')
            
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

# Registration views
class CompanyRegistrationView(CreateView):
    template_name = 'orders/company_register.html'
    form_class = CompanyRegistrationForm
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Company account created successfully. You can now login.")
        return response

class DeliveryPersonnelRegistrationView(CreateView):
    template_name = 'orders/delivery_register.html'
    form_class = DeliveryPersonnelRegistrationForm
    success_url = reverse_lazy('login')
    
    @method_decorator(login_required)
    @method_decorator(user_passes_test(is_admin))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Delivery personnel account created successfully.")
        return response

class VisitorRegistrationView(FormView):
    template_name = 'orders/visitor_register.html'
    form_class = VisitorRegistrationForm
    success_url = reverse_lazy('login')  # Redirect to login page after registration
    
    def form_valid(self, form):
        # Form now handles both CustomUser and Visitor creation
        visitor = form.save(commit=True)
        
        # Access the user through the visitor's related field
        user = visitor.user
        
        messages.success(self.request, "Registration successful. You can now log in.")
        return super().form_valid(form)
@login_required
def dashboard_redirect(request):
    """Redirects to the appropriate dashboard based on user role"""
    user = request.user
    if user.role == ADMIN:
        return redirect('admin_dashboard')
    elif user.role == COMPANY:
        return redirect('company_dashboard')
    elif user.role == DELIVERY_PERSONNEL:
        return redirect('delivery_dashboard')
    elif user.role == VISITOR:
        return redirect('visitor_dashboard')
    
    else:
        # Fallback to a common dashboard or login page
        return redirect('login')

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    companies = Company.objects.all()
    total_orders = Order.objects.count()
    
    # Get all delivery personnel
    delivery_personnel = DeliveryPersonnel.objects.all()
    total_delivery_personnel = delivery_personnel.count()
    available_delivery_personnel = delivery_personnel.filter(available=True).count()
    
    context = {
        'companies': companies,
        'total_orders': total_orders,
        'delivery_personnel': delivery_personnel,
        'total_delivery_personnel': total_delivery_personnel,
        'available_delivery_personnel': available_delivery_personnel,
    }
    
    return render(request, 'orders/admin_dashboard.html', context)

@login_required
@user_passes_test(is_company)
def company_dashboard(request):
    company = request.user.company_profile
    orders = Order.objects.filter(company=company).order_by('-ordered_at')
    
    # Count orders by status for dashboard stats
    pending_count = orders.filter(status='pending').count()
    delivered_count = orders.filter(status='delivered').count()
    canceled_count = orders.filter(status='canceled').count()
    
    context = {
        'company': company,
        'orders': orders[:10],  # Latest 10 orders
        'pending_count': pending_count,
        'delivered_count': delivered_count,
        'canceled_count': canceled_count,
        'total_orders': orders.count(),
    }
    
    return render(request, 'orders/company_dashboard.html', context)

@login_required
@user_passes_test(is_delivery)
def delivery_dashboard(request):
    delivery_personnel = request.user.delivery_profile
    assigned_orders = Order.objects.filter(ordertracking__assigned_to=delivery_personnel).order_by('-ordered_at')
    
    context = {
        'delivery_personnel': delivery_personnel,
        'assigned_orders': assigned_orders,
    }
    
    return render(request, 'orders/delivery_dashboard.html', context)

# Logout view
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')



@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY,VISITOR])
def product_list(request):
    """View to list products based on user role"""
    user = request.user
    
    if user.role == ADMIN:
        products = Product.objects.all().order_by('-created_at')
    elif user.role == COMPANY:
        company = user.company_profile
        products = Product.objects.filter(company=company).order_by('-created_at')
    if user.role == VISITOR:
        products = Product.objects.all().order_by('-created_at')
    else:
        products = Product.objects.all().order_by('-created_at')
    
    context = {
        'products': products,
    }
    return render(request, 'orders/product_list.html', context)

@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY])
def create_product(request):
    """View to create a new product"""
    if request.method == 'POST':
        if request.user.role == COMPANY:
            form = ProductForm(request.POST, request.FILES, company=request.user.company_profile)
        else:
            form = ProductForm(request.POST, request.FILES)
            
        if form.is_valid():
            product = form.save(commit=False)
            
            # If company user, set company automatically
            if request.user.role == COMPANY:
                product.company = request.user.company_profile
                
            product.save()
            messages.success(request, "Product created successfully!")
            return redirect('product_list')
    else:
        if request.user.role == COMPANY:
            form = ProductForm(company=request.user.company_profile)
        else:
            form = ProductForm()
    
    return render(request, 'orders/create_product.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY])
def edit_product(request, product_id):
    """View to edit an existing product"""
    if request.user.role == COMPANY:
        product = get_object_or_404(Product, id=product_id, company=request.user.company_profile)
    else:
        product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        if request.user.role == COMPANY:
            form = ProductForm(request.POST, request.FILES, instance=product, company=request.user.company_profile)
        else:
            form = ProductForm(request.POST, request.FILES, instance=product)
            
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated successfully!")
            return redirect('product_list')
    else:
        if request.user.role == COMPANY:
            form = ProductForm(instance=product, company=request.user.company_profile)
        else:
            form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
    }
    return render(request, 'orders/edit_product.html', context)

@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY])
def delete_product(request, product_id):
    """View to delete a product"""
    if request.user.role == COMPANY:
        product = get_object_or_404(Product, id=product_id, company=request.user.company_profile)
    else:
        product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Product deleted successfully!")
        return redirect('product_list')
    
    context = {
        'product': product,
    }
    return render(request, 'orders/delete_product.html', context)

# Category management views
@login_required

def category_list(request):
    """View to list all categories (admin only)"""
    categories = Category.objects.all().order_by('name')
    
    context = {
        'categories': categories,
    }
    return render(request, 'orders/category_list.html', context)

@login_required
@user_passes_test(is_admin)
def create_category(request):
    """View to create a new category (admin only)"""
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully!")
            return redirect('category_list')
    else:
        form = CategoryForm()
    
    return render(request, 'orders/create_category.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_category(request, category_id):
    """View to edit an existing category (admin only)"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated successfully!")
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
    }
    return render(request, 'orders/edit_category.html', context)

@login_required
@user_passes_test(is_admin)
def delete_category(request, category_id):
    """View to delete a category (admin only)"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted successfully!")
        return redirect('category_list')
    
    context = {
        'category': category,
    }
    return render(request, 'orders/delete_category.html', context)





def search_products(request):
    """Search functionality for products by category, company, or keyword"""
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    company_id = request.GET.get('company', '')
    
    products = Product.objects.filter(available=True)
    
    # Apply filters
    if query:
        products = products.filter(
            models.Q(name__icontains=query) | 
            models.Q(description__icontains=query) |
            models.Q(company__name__icontains=query)
        )
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if company_id:
        products = products.filter(company_id=company_id)
    
    # Get all categories and companies for filter options
    categories = Category.objects.all().order_by('name')
    companies = Company.objects.all().order_by('name')
    
    context = {
        'products': products,
        'categories': categories,
        'companies': companies,
        'query': query,
        'selected_category': int(category_id) if category_id else None,
        'selected_company': int(company_id) if company_id else None,
    }
    return render(request, 'orders/search_results.html', context)


def company_detail(request, company_id):
    """View to display a company profile and its products"""
    company = get_object_or_404(Company, id=company_id)
    products = Product.objects.filter(company=company, available=True)
    
    # Group products by category
    products_by_category = {}
    for product in products:
        category = product.category
        if category not in products_by_category:
            products_by_category[category] = []
        products_by_category[category].append(product)
    
    context = {
        'company': company,
        'products_by_category': products_by_category,
    }
    return render(request, 'orders/company_detail.html', context)

def category_detail(request, category_id):
    """View to display all products in a specific category"""
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category, available=True)
    
    # Group products by company
    products_by_company = {}
    for product in products:
        company = product.company
        if company not in products_by_company:
            products_by_company[company] = []
        products_by_company[company].append(product)
    
    context = {
        'category': category,
        'products_by_company': products_by_company,
    }
    return render(request, 'orders/category_detail.html', context)

def product_detail(request, product_id):
    """View to display detailed information for a single product"""
    product = get_object_or_404(Product, id=product_id, available=True)
    
    # Get related products (same category, different company)
    related_products = Product.objects.filter(
        category=product.category, 
        available=True
    ).exclude(id=product.id)[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'orders/product_detail.html', context)






def get_or_create_cart(request):
    """Helper function to get or create cart from session"""
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
    
    cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart
@login_required
def add_to_cart(request, product_id):
    """Add a product to the shopping cart"""
    product = get_object_or_404(Product, id=product_id, available=True)
    
    # Get quantity from form, default to 1
    quantity = int(request.POST.get('quantity', 1))
    
    cart = get_or_create_cart(request)
    
    # Check if product is already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    # If product already exists in cart, update quantity
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f"{product.name} added to cart.")
    
    # Redirect back to the product page or to the referring page
    next_url = request.POST.get('next', request.META.get('HTTP_REFERER'))
    if not next_url:
        next_url = reverse('cart_view')
    
    return redirect(next_url)

def cart_view(request):
    """View the shopping cart contents"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'product__company').all()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
    }
    return render(request, 'orders/cart.html', context)

def update_cart_item(request, item_id):
    """Update quantity of an item in cart"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__session_key=request.session.session_key)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"{cart_item.product.name} quantity increased.")
        
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
                messages.success(request, f"{cart_item.product.name} quantity decreased.")
            else:
                cart_item.delete()
                messages.success(request, f"{cart_item.product.name} removed from cart.")
        
        elif action == 'remove':
            cart_item.delete()
            messages.success(request, f"{cart_item.product.name} removed from cart.")
    
    return redirect('cart_view')


@login_required
def checkout(request):
    """Process checkout from cart to create an order for Visitors"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'product__company').all()
    
    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_view')
    
    # Group items by company for potential multi-company checkout
    items_by_company = {}
    for item in cart_items:
        company = item.product.company
        if company not in items_by_company:
            items_by_company[company] = []
        items_by_company[company].append(item)
    
    # Get available delivery addresses
    delivery_addresses = DeliveryAddress.objects.filter(is_active=True)
    
    # Transportation choices for template
    transportation_choices = [
        ('bicycle', 'Bicycle (₦100 base delivery)'),
        ('keke_napep', 'Keke Napep/Tricycle (₦300 base delivery)'),
    ]
    
    # Get Visitor information if user is authenticated
    initial_data = {}
    visitor_data = None
    
    if request.user.is_authenticated and request.user.role == VISITOR:
        try:
            # Try to get the visitor profile associated with this user
            visitor = Visitor.objects.get(user=request.user)
            visitor_data = {
                'client_name': visitor.user.username,
                'client_phone': visitor.phone_number,
                'client_email': visitor.user.email,
            }
            
            # Prepare initial form data
            initial_data = {
                'client_name': visitor.user.username,
                'client_phone': visitor.phone_number,
                'client_email': visitor.user.email,
            }
        except (AttributeError, ObjectDoesNotExist):
            # If there's no visitor profile, fall back to basic user info
            initial_data = {
                'client_name': request.user.get_full_name() or request.user.username,
                'client_email': request.user.email,
            }
    
    if request.method == 'POST':
        # Determine if we need to collect client info from form
        collect_client_info = not bool(visitor_data)
        
        # If collecting from form, validate those fields
        if collect_client_info:
            client_name = request.POST.get('client_name')
            client_phone = request.POST.get('client_phone')
            client_email = request.POST.get('client_email')
            
            # Validate required client fields
            if not all([client_name, client_phone]):
                messages.error(request, "Please provide your name and phone number.")
                return redirect('checkout')
        else:
            # Use data from visitor profile
            client_name = visitor_data['client_name']
            client_phone = visitor_data['client_phone']
            client_email = visitor_data['client_email']
        
        # Always collect these fields from the form
        delivery_address_id = request.POST.get('delivery_address')
        transportation_mode = request.POST.get('transportation_mode', 'bicycle')
        
        # Get the DeliveryAddress object
        try:
            delivery_address_obj = DeliveryAddress.objects.get(id=delivery_address_id, is_active=True)
            delivery_address_name = delivery_address_obj.name
        except (DeliveryAddress.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Please select a valid delivery address.")
            return redirect('checkout')
        
        # Get package weight and delivery date
        try:
            weight = float(request.POST.get('weight', 30.9))
        except ValueError:
            weight = 30.9  # Default value if conversion fails
            
        delivery_date_str = request.POST.get('delivery_date')
        order_notes = request.POST.get('order_notes', '')
        
        # Validate required form fields (that aren't auto-filled)
        if not all([delivery_address_id, delivery_date_str]):
            messages.error(request, "Please fill in delivery address and delivery date.")
            return redirect('checkout')
        
        # Convert delivery date to datetime
        try:
            from datetime import datetime, time
            from django.utils import timezone
            import pytz
            
            # Parse the date from the input
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
            
            # Add a default time (noon)
            delivery_time = datetime.combine(delivery_date, time(12, 0))
            
            # Make timezone-aware
            tz = pytz.timezone('Africa/Lagos')  # Assuming Nigerian timezone
            delivery_time = tz.localize(delivery_time)
        except ValueError:
            # If date parsing fails, default to 24 hours from now
            delivery_time = timezone.now() + timezone.timedelta(days=1)
        
        # Create orders for each company
        orders = []
        for company, items in items_by_company.items():
            # Calculate subtotal for this company's items
            subtotal = sum(item.subtotal for item in items)
            
            # Calculate delivery cost based on transportation mode and weight
            if transportation_mode == 'bicycle':
                base_delivery_fee = 100
            elif transportation_mode == 'keke_napep':
                base_delivery_fee = 300
            else:
                base_delivery_fee = 100  # Default to bicycle
            
            # Add weight factor to delivery cost
            weight_factor = weight / 10  # Adjust based on weight
            delivery_cost = base_delivery_fee * (1 + weight_factor)
            
            from decimal import Decimal
            delivery_cost = Decimal(str(delivery_cost))
            subtotal = Decimal(str(subtotal))
            
            # Total cost including items and delivery
            total_cost = subtotal + delivery_cost
            
            # Create the order with all the new fields
            order = Order.objects.create(
                company=company,
                client_name=client_name,
                client_phone=client_phone,
                client_email=client_email,
                delivery_address=delivery_address_obj,
                delivery_time=delivery_time,
                weight=weight,
                transportation_mode=transportation_mode,
                subtotal=subtotal,
                delivery_cost=delivery_cost,
                total_cost=total_cost,
                status='pending',
                payment_status='pending'
            )
            
            # Store the ordered items in OrderItem model
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    price=item.product.price or 0
                )
            
            # Add order notes if provided
            if order_notes:
                OrderNote.objects.create(
                    order=order,
                    content=order_notes,
                    created_by=request.user.get_full_name() or request.user.username
                )
            
            orders.append(order)
        
        # Clear the cart after successful order creation
        cart.items.all().delete()
        
        # If only one order was created, redirect to payment
        if len(orders) == 1:
            messages.success(request, f"Order #{orders[0].id} placed successfully. Proceeding to payment.")
            return redirect('initiate_payment', order_id=orders[0].id)
        else:
            # For multiple orders, you might need a different approach
            # For now, redirect to the first order's payment
            messages.success(request, f"{len(orders)} orders placed successfully. Processing payment for the first order.")
            # Store other order IDs in session to process after first payment
            request.session['pending_orders'] = [order.id for order in orders[1:]]
            return redirect('initiate_payment', order_id=orders[0].id)
    
    # Calculate totals for the GET request (for display purposes)
    cart_subtotal = sum(item.subtotal for item in cart_items)
    default_delivery_cost = 100  # Default bicycle delivery
    cart_total = cart_subtotal + default_delivery_cost
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'items_by_company': items_by_company,
        'initial_data': initial_data,
        'is_authenticated': request.user.is_authenticated and request.user.role == VISITOR,
        'visitor_data': visitor_data,
        'delivery_addresses': delivery_addresses,
        'transportation_choices': transportation_choices,
        'cart_subtotal': cart_subtotal,
        'default_delivery_cost': default_delivery_cost,
        'cart_total': cart_total,
    }
    return render(request, 'orders/checkout.html', context)

def public_initiate_payment(request):
    """Handle payment initialization for public users (cart checkout)"""
    # This is a wrapper for initiate_payment that handles public user scenarios
    # Get the order ID from session or parameter
    order_id = request.GET.get('order_id')
    
    if order_id:
        return initiate_payment(request, order_id)
    else:
        messages.error(request, "No order found for payment.")
        return redirect('cart_view')

def payment_callback(request):
    """Handle the callback from Paystack after payment"""
    reference = request.GET.get('reference', None)
    
    if not reference:
        messages.error(request, "Payment verification failed. No reference provided.")
        return redirect('landing_page')
    
    try:
        # Verify the transaction
        from paystackapi.transaction import Transaction
        from django.utils import timezone
        
        response = Transaction.verify(reference)
        
        # First try to find the order directly by payment reference
        try:
            order = Order.objects.get(payment_reference=reference)
        except Order.DoesNotExist:
            # If not found by reference, try to extract order ID from metadata
            if 'data' in response and 'metadata' in response['data'] and 'order_id' in response['data']['metadata']:
                order_id = response['data']['metadata']['order_id']
                try:
                    order = Order.objects.get(id=order_id)
                except Order.DoesNotExist:
                    messages.error(request, "Order not found with metadata ID.")
                    return redirect('landing_page')
            else:
                # Try to extract from reference if it follows our format
                import re
                match = re.search(r'order-(\d+)-', reference)
                if match:
                    order_id = match.group(1)
                    try:
                        order = Order.objects.get(id=order_id)
                    except Order.DoesNotExist:
                        messages.error(request, "Order not found with reference pattern.")
                        return redirect('landing_page')
                else:
                    messages.error(request, "Could not determine order from payment reference.")
                    return redirect('landing_page')
        
        # Now check if payment was successful
        if 'data' in response and response['data']['status'] == 'success':
            # Update the order with payment information
            order.payment_status = 'paid'
            order.payment_date = timezone.now()
            order.save()
            
            # Log the successful payment
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Payment successful for order #{order.id}, reference: {reference}")
            
            messages.success(request, "Payment successful! Your order is now being processed.")
            
            # Check if there are more orders to process (for multi-company checkouts)
            pending_orders = request.session.get('pending_orders', [])
            if pending_orders:
                # Remove the first order from pending and redirect to its payment
                next_order_id = pending_orders.pop(0)
                request.session['pending_orders'] = pending_orders
                messages.info(request, "Processing payment for next order...")
                return redirect('initiate_payment', order_id=next_order_id)
            
            # Use the standard order_tracking view for visitors too
            return redirect('order_tracking', order_id=order.id)
            
        else:
            # Payment failed or is pending
            payment_status = response.get('data', {}).get('status', 'unknown')
            order.payment_status = 'failed' if payment_status == 'failed' else 'pending'
            order.save()
            
            messages.warning(request, f"Payment status: {payment_status}. Please try again if needed.")
            return redirect('cart_view')
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Payment verification error: {str(e)}")
        
        messages.error(request, f"Payment verification error: {str(e)}")
        return redirect('cart_view')

def public_order_tracking(request):
    """Allow public users to track their orders"""
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        email_or_phone = request.POST.get('email_or_phone')
        
        try:
            # Try to find the order by ID and matching email or phone
            order = Order.objects.filter(
                Q(client_email=email_or_phone) | Q(client_phone=email_or_phone),
                id=order_id).get()
            
            # Get tracking information
            tracking_info = OrderTracking.objects.filter(order=order).order_by('-timestamp')
            
            context = {
                'order': order,
                'tracking_info': tracking_info,
                'found': True
            }
            return render(request, 'orders/public_order_detail.html', context)
            
        except Order.DoesNotExist:
            messages.error(request, "Order not found. Please check your order number and contact details.")
            return redirect('public_order_tracking')
    
    return render(request, 'orders/public_order_tracking.html')





@login_required
@user_passes_test(is_admin, login_url='login')
def delivery_address_list(request):
    """List all delivery addresses - Admin only"""
    search_query = request.GET.get('search', '')
    show_inactive = request.GET.get('show_inactive', False)
    
    # Filter addresses
    addresses = DeliveryAddress.objects.all()
    
    if search_query:
        addresses = addresses.filter(name__icontains=search_query)
    
    if not show_inactive:
        addresses = addresses.filter(is_active=True)
    
    # Pagination
    paginator = Paginator(addresses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'show_inactive': show_inactive,
        'total_count': addresses.count(),
    }
    
    return render(request, 'orders/delivery_addresses_list.html', context)

@user_passes_test(is_admin, login_url='login')
def delivery_address_create(request):
    """Create new delivery address - Admin only"""
    if request.method == 'POST':
        form = DeliveryAddressForm(request.POST)
        if form.is_valid():
            address = form.save()
            messages.success(request, f'Delivery address "{address.name}" created successfully.')
            return redirect('delivery_address_list')
    else:
        form = DeliveryAddressForm()
    
    context = {
        'form': form,
        'title': 'Add New Delivery Address',
        'submit_text': 'Create Address'
    }
    
    return render(request, 'orders/delivery_addresses_form.html', context)

@login_required
@user_passes_test(is_admin, login_url='login')
def delivery_address_edit(request, pk):
    """Edit delivery address - Admin only"""
    address = get_object_or_404(DeliveryAddress, pk=pk)
    
    if request.method == 'POST':
        form = DeliveryAddressForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save()
            messages.success(request, f'Delivery address "{address.name}" updated successfully.')
            return redirect('delivery_address_list')
    else:
        form = DeliveryAddressForm(instance=address)
    
    context = {
        'form': form,
        'address': address,
        'title': f'Edit: {address.name}',
        'submit_text': 'Update Address'
    }
    
    return render(request, 'orders/delivery_addresses_form.html', context)

@login_required
@user_passes_test(is_admin, login_url='login')
def delivery_address_delete(request, pk):
    """Delete delivery address - Admin only"""
    address = get_object_or_404(DeliveryAddress, pk=pk)
    
    # Check if address is being used in any orders
    orders_count = address.order_set.count()
    
    if request.method == 'POST':
        if orders_count > 0:
            # Soft delete - just deactivate instead of deleting
            address.is_active = False
            address.save()
            messages.warning(
                request, 
                f'Delivery address "{address.name}" has been deactivated because it\'s used in {orders_count} orders.'
            )
        else:
            # Hard delete if no orders are using it
            address_name = address.name
            address.delete()
            messages.success(request, f'Delivery address "{address_name}" deleted successfully.')
        
        return redirect('delivery_address_list')
    
    context = {
        'address': address,
        'orders_count': orders_count,
    }
    
    return render(request, 'orders/delivery_addresses_delete.html', context)

@login_required
@user_passes_test(is_admin, login_url='login')
def delivery_address_toggle_status(request, pk):
    """Toggle active status of delivery address - Admin only"""
    address = get_object_or_404(DeliveryAddress, pk=pk)
    
    address.is_active = not address.is_active
    address.save()
    
    status = "activated" if address.is_active else "deactivated"
    messages.success(request, f'Delivery address "{address.name}" {status} successfully.')
    
    return redirect('delivery_address_list')



@login_required
def visitor_dashboard(request):
    """Main dashboard for visitors"""
    if request.user.role != VISITOR:
        messages.error(request, 'Access denied. This page is for visitors only.')
        return redirect('landing_page')
    
    # Get visitor profile or create if doesn't exist
    visitor, created = Visitor.objects.get_or_create(
        user=request.user,
        defaults={'phone_number': ''}
    )
    
    # Get recent orders (if any - visitors might not have direct orders)
    recent_orders = Order.objects.filter(
        client_email=request.user.email
    ).order_by('-ordered_at')[:5]
    
    # Get cart items
    cart = None
    cart_items = []
    if not request.user.is_anonymous:
        try:
            cart = Cart.objects.get(session_key=request.session.session_key)
            cart_items = cart.items.all()
        except Cart.DoesNotExist:
            pass
    
    # Get some featured products
    featured_products = Product.objects.filter(available=True)[:6]
    
    context = {
        'visitor': visitor,
        'recent_orders': recent_orders,
        'cart_items': cart_items,
        'cart': cart,
        'featured_products': featured_products,
        'total_orders': recent_orders.count(),
    }
    
    return render(request, 'orders/visitors_dashboard.html', context)

@login_required
def visitor_profile(request):
    """Visitor profile page with edit functionality"""
    if request.user.role != VISITOR:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    visitor, created = Visitor.objects.get_or_create(
        user=request.user,
        defaults={'phone_number': ''}
    )
    
    if request.method == 'POST':
        form = VisitorProfileUpdateForm(
            request.POST, 
            request.FILES, 
            instance=visitor, 
            user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('visitor_profile')
    else:
        form = VisitorProfileUpdateForm(instance=visitor, user=request.user)
    
    context = {
        'form': form,
        'visitor': visitor,
    }
    
    return render(request, 'orders/visitors_profile.html', context)

@login_required
def visitor_change_password(request):
    """Change password for visitors"""
    if request.user.role != VISITOR:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    if request.method == 'POST':
        form = VisitorPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)  # Keep user logged in
            messages.success(request, 'Password changed successfully!')
            return redirect('visitor_profile')
    else:
        form = VisitorPasswordChangeForm(request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'orders/visitors_change_password.html', context)
