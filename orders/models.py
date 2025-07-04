from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from cloudinary.models import CloudinaryField
from django.contrib.auth import get_user_model

# User roles constants
ADMIN = 'admin'
COMPANY = 'company'
DELIVERY_PERSONNEL = 'delivery'
VISITOR='visitor'

USER_ROLE_CHOICES = [
    (ADMIN, 'Admin'),
    (COMPANY, 'Company'),
    (DELIVERY_PERSONNEL, 'Delivery Personnel'),
    (VISITOR, 'Visitor'),
    
]

class CustomUserManager(BaseUserManager):
    """Custom user manager for the CustomUser model"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom user model with role-based authentication"""
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=10, choices=USER_ROLE_CHOICES, default=VISITOR)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_short_name(self):
        return self.first_name

# Order status choices
PENDING = 'pending'
DELIVERED = 'delivered'
CANCELED = 'canceled'
STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (DELIVERED, 'Delivered'),
    (CANCELED, 'Canceled'),
]

# Update the Company model
class Company(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='company_profile')
    name = models.CharField(max_length=100)
    address = models.TextField()
    logo = CloudinaryField('image',folder='company_logos/', null=True, blank=True)
    
    def __str__(self):
        return self.name

# Client model is still associated with Company but not a user
class Client(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, related_name='clients', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
     
    def __str__(self):
        return self.name
class Visitor(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='visitor_profile')
    phone_number = models.CharField(max_length=15)
    profile_image = CloudinaryField(
        'image', 
        folder='visitor_profiles/', 
        null=True, 
        blank=True,
        help_text='Optional profile picture'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"
    
    def get_profile_image_url(self):
        """Get profile image URL or return default"""
        if self.profile_image:
            return self.profile_image.url
        return None

# Update the DeliveryPersonnel model
class DeliveryPersonnel(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='delivery_profile')
    phone_number = models.CharField(max_length=15)
    available = models.BooleanField(default=True)
    
    def __str__(self):
        return self.user.get_full_name() or self.user.username or self.user.first_name or self.user.last_name
# Add payment status choices
PAYMENT_STATUS_CHOICES = (
('pending', 'Pending'),
('paid', 'Paid'),
('failed', 'Failed'),
('refunded', 'Refunded'),
)
class DeliveryAddress(models.Model):
    """Predefined delivery addresses/landmarks"""
    name = models.CharField(max_length=255, unique=True, verbose_name="Delivery Location")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    class Meta:
        verbose_name = "Delivery Address"
        verbose_name_plural = "Delivery Addresses"
        ordering = ['name']
    
    def __str__(self):
        return self.name

# Add these transportation choices at the top of your models.py file
TRANSPORTATION_CHOICES = [
    ('bicycle', 'Bicycle'),
    ('keke_napep', 'Keke Napep (Tricycle)'),
]

class Order(models.Model):
    company = models.ForeignKey(Company, related_name='orders', on_delete=models.CASCADE)
    # Client information directly from visitor profile
    client_name = models.CharField(max_length=100, default="no recipient")
    client_phone = models.CharField(max_length=15, default=000)
    client_email = models.EmailField(blank=True, null=True)
    delivery_address = models.ForeignKey(
        DeliveryAddress, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Delivery Location"
    )
    ordered_at = models.DateTimeField(auto_now_add=True)
    delivery_time = models.DateTimeField()
    weight = models.FloatField(max_length=4, default=30.9)
    
    # Add transportation mode field
    transportation_mode = models.CharField(
        max_length=20, 
        choices=TRANSPORTATION_CHOICES, 
        default='bicycle',
        verbose_name='Transportation Mode'
    )
    
    # Add subtotal and total cost fields
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name='Subtotal'
    )
    
    delivery_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=100.00,
        verbose_name='Delivery Cost'
    )
    
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name='Total Cost'
    )
    
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name='Payment Status'
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Payment Reference'
    )
    payment_date = models.DateTimeField(blank=True, null=True, verbose_name='Payment Date')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)

    def __str__(self):
        return f"Order #{self.id} - {self.client_name}"
    
    def save(self, *args, **kwargs):
        # Calculate total_cost before saving
        self.total_cost = self.subtotal + self.delivery_cost
        super().save(*args, **kwargs)
    
class OrderNote(models.Model):
    """Notes attached to orders (from customers or staff)"""
    order = models.ForeignKey(Order, related_name='notes', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100)  # Name of creator (user or customer)
    
    def __str__(self):
        return f"Note on Order #{self.order.id}"

class OrderTracking(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(DeliveryPersonnel, on_delete=models.SET_NULL, null=True, blank=True)
    status_update = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking - {self.order.id} - {self.status_update}"

class DeliveryLog(models.Model):
    order = models.ForeignKey(Order, related_name='delivery_logs', on_delete=models.CASCADE)
    delivery_personnel = models.ForeignKey(DeliveryPersonnel, on_delete=models.CASCADE)
    time = models.DateTimeField(auto_now_add=True)
    distance_traveled = models.FloatField()  # in kilometers
    feedback = models.TextField()

    def __str__(self):
        return f"Delivery Log - {self.order.id} - {self.time}"
    
    
    # Product category model
class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = CloudinaryField('image', folder='category_images/', null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

# Product model
class Product(models.Model):
    company = models.ForeignKey(Company, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True)
    available = models.BooleanField(default=True)
    image = CloudinaryField('image', folder='product_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"
    
    
# Add these models to your models.py file

class Cart(models.Model):
    """Shopping cart for storing items before checkout"""
    session_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart {self.id} - {self.session_key}"
    
    @property
    def total_price(self):
        """Calculate total price of all cart items"""
        return sum(item.subtotal for item in self.items.all())
    
    @property
    def item_count(self):
        """Count total number of items in cart"""
        return self.items.count()

class CartItem(models.Model):
    """Individual item in a shopping cart"""
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('cart', 'product')
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def subtotal(self):
        """Calculate price for this cart item"""
        if self.product.price:
            return self.product.price * self.quantity
        return 0
    
class OrderItem(models.Model):
    """Individual product items in an order"""
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)  # Store name in case product is deleted
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    
    def __str__(self):
        return f"{self.quantity} x {self.product_name}"
    
    @property
    def subtotal(self):
        return self.price * self.quantity
    
    from .models import DeliveryAddress, Order

