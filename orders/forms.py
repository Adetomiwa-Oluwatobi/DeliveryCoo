from django import forms
from .models import VISITOR, Order, OrderTracking, DeliveryPersonnel,DeliveryAddress, CustomUser,Product, Category, Company, COMPANY, DELIVERY_PERSONNEL, Visitor
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class DeliveryAddressForm(forms.ModelForm):
    """Form for creating and editing delivery addresses - Admin only"""
    
    class Meta:
        model = DeliveryAddress
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter landmark or location name'
            }),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().title()  # Clean and format the name
            
            # Check for duplicates (excluding current instance if editing)
            existing = DeliveryAddress.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError("A delivery address with this name already exists.")
        
        return name
    
class OrderForm(forms.ModelForm):
    """Form for creating a new order with client information included"""
    client_name = forms.CharField(max_length=100, required=True, label="Client Name")
    client_phone = forms.CharField(max_length=15, required=True, label="Client Phone Number")
    client_email = forms.EmailField(required=False, label="Client Email")
    
    class Meta:
        model = Order
        fields = [
            'company', 'client_name', 'client_phone', 'client_email',
            'delivery_address', 'delivery_time', 'weight', 'delivery_cost',
        ]
        widgets = {
            'delivery_address': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'delivery_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'delivery_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active delivery addresses
        self.fields['delivery_address'].queryset = DeliveryAddress.objects.filter(is_active=True)
        
        # Make delivery address required
        self.fields['delivery_address'].required = True
        self.fields['delivery_address'].empty_label = "Select a delivery location"
        
        # Add CSS classes and attributes
        for field_name, field in self.fields.items():
            if field_name not in ['delivery_address']:
                field.widget.attrs['class'] = 'form-control'
        
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

"""class VisitorRegistrationForm(forms.ModelForm):
   
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=30, required=True)
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    
    class Meta:
        model = Visitor
        fields = ['phone_number']
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def save(self):
        # Create user with minimal info
        user = CustomUser.objects.create_user(
            email=self.cleaned_data['email'],
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
            role=VISITOR
        )
        
        # Don't try to create a Visitor model - we'll just use CustomUser
        return user"""
class VisitorRegistrationForm(forms.ModelForm):
    """Form for registering a new visitor with full profile information"""
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=30, required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    phone_number = forms.CharField(max_length=15, required=True)
    
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
        # Create user with complete information
        user = CustomUser.objects.create_user(
            email=self.cleaned_data['email'],
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            password=self.cleaned_data['password1'],
            role=VISITOR
        )
        
        # Create the Visitor profile
        visitor = super().save(commit=False)
        visitor.user = user
        visitor.phone_number = self.cleaned_data['phone_number']
        
        if commit:
            visitor.save()
        
        return visitor
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
  
  
    
    

# Add these forms to your forms.py

class VisitorProfileUpdateForm(forms.ModelForm):
    """Form for visitors to update their profile information"""
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Visitor
        fields = ['phone_number', 'profile_image']
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your phone number'
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
            
        # Add CSS classes
        for field_name in ['first_name', 'last_name', 'email']:
            self.fields[field_name].widget.attrs['class'] = 'form-control'
    
    def save(self, commit=True):
        visitor = super().save(commit=False)
        
        if self.user:
            # Update user information
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            
            if commit:
                self.user.save()
                visitor.save()
        
        return visitor

class VisitorPasswordChangeForm(forms.Form):
    """Form for visitors to change their password"""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Current Password'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='New Password'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Confirm New Password'
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise forms.ValidationError('Current password is incorrect.')
        return current_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('New passwords do not match.')
        
        return cleaned_data
    
    def save(self):
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save()
        return self.user