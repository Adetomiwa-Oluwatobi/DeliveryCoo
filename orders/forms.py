from django import forms
from .models import VISITOR, Order, OrderTracking, DeliveryPersonnel, CustomUser,Product, Category, Company, COMPANY, DELIVERY_PERSONNEL, Visitor
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm


class OrderForm(forms.ModelForm):
    """Form for creating a new order with client information included"""
    client_name = forms.CharField(max_length=100, required=True, label="Client Name")
    client_phone = forms.CharField(max_length=15, required=True, label="Client Phone Number")
    client_email = forms.EmailField(required=False, label="Client Email")
    
    class Meta:
        model = Order
        fields = [
            'company', 'client_name', 'client_phone', 'client_email',
            'delivery_address', 'delivery_time','weight','delivery_cost',
        ]
        
class OrderTrackingForm(forms.ModelForm):
    class Meta:
        model = OrderTracking
        fields = ['assigned_to', 'status_update']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show available delivery personnel
        self.fields['assigned_to'].queryset = DeliveryPersonnel.objects.filter(available=True)

class CustomUserCreationForm(UserCreationForm):
    """Base form for creating a new user"""
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'first_name', 'last_name', 'password1', 'password2')

class CompanyRegistrationForm(forms.ModelForm):
    """Form for registering a new company"""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    
    class Meta:
        model = Company
        fields = ('name', 'address', 'logo')
    
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=30, required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def save(self, commit=True):
        # Create user first
        user_data = {
            'email': self.cleaned_data['email'],
            'username': self.cleaned_data['username'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'role': COMPANY
        }
        user = CustomUser.objects.create_user(
            email=user_data['email'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            password=self.cleaned_data['password1'],
            role=COMPANY
        )
        
        # Then create the company profile
        company = super().save(commit=False)
        company.user = user
        
        if commit:
            company.save()
        
        return company

class DeliveryPersonnelRegistrationForm(forms.ModelForm):
    email = forms.EmailField(label="Email")
    username = forms.CharField(label="Username")
    first_name = forms.CharField(label="Firstname")
    last_name = forms.CharField(label="Lastname")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="Confirm Password", widget=forms.PasswordInput)
    
    class Meta:
        model = DeliveryPersonnel
        fields = ['phone_number', 'available']
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data
    
    def save(self, commit=True):
        # Create user first
        user_data = {
            'email': self.cleaned_data['email'],
            'username': self.cleaned_data['username'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'role': DELIVERY_PERSONNEL
        }
        user = CustomUser.objects.create_user(
            email=user_data['email'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            password=self.cleaned_data['password'],
            role=user_data['role']
        )
        
        # Then create delivery personnel profile
        delivery_personnel = super().save(commit=False)
        delivery_personnel.user = user
        
        if commit:
            delivery_personnel.save()
        
        return delivery_personnel

class VisitorRegistrationForm(forms.ModelForm):
    """Form for registering a new visitor with minimal fields"""
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=30, required=True)
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    phone_number = forms.CharField(max_length=15, required=False)
    
    class Meta:
        model = Visitor
        fields = ['phone_number']  
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def save(self, commit=True):
        # Create user with minimal info
        user = CustomUser.objects.create_user(
            email=self.cleaned_data['email'],
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
            role=VISITOR
        )
        
        # Create visitor instance
        visitor = Visitor.objects.create(
            name=user.username,
            email=user.email,
            phone_number=self.cleaned_data.get('phone_number', '')
        )
        
        return user
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'category', 'available', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super(ProductForm, self).__init__(*args, **kwargs)
        
        # Company users should only see their own products
        if company:
            self.instance.company = company
            
            
class CustomLoginForm(AuthenticationForm):
    """Custom login form"""
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True}))
  
  
    
    
