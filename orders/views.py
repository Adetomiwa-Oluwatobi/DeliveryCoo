from datetime import timezone
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import *
from .forms import OrderForm, OrderTrackingForm
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client as TwilioClient
from django.contrib import messages
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
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
    return render(request, 'orders/landing_page.html')

@login_required
@user_passes_test(lambda u: u.role in [ADMIN, COMPANY])
def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            
            # If company user, set company automatically
            if request.user.role == COMPANY:
                order.company = request.user.company_profile
                
            # Set initial payment status
            order.payment_status = 'pending'
                
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
    
    # Convert to kobo (Paystack accepts amount in smallest currency unit)
    amount = int(order.delivery_cost * 100)
    
    # If client email is not provided, use company email or a default
    email_to_use = order.client_email
    if not email_to_use:
        if request.user.role == COMPANY:
            email_to_use = request.user.email
        else:
            messages.error(request, "Client email is required for payment processing.")
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
    email_to_use = order.client_email
    if not email_to_use:
        if request.user.role == COMPANY:
            email_to_use = request.user.email
        else:
            messages.error(request, "Client email is required for payment processing.")
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
    
    # For HTML template rendering approach
    context = {
        'order': order,
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

# Dashboard views based on roles
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