from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class CustomUserManager(BaseUserManager):

    def email_validator(self, email):
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Ingrese una dirección de correo electrónico válida")
        


    def create_user(self, email : str, first_name : str, last_name : str, password : str, **extra_fields):
        if email:
            email=self.normalize_email(email)
            self.email_validator(email)
        else:
            raise ValidationError("El email es obligatorio")
        if not first_name:
            raise ValidationError("El nombre es obligatorio")
        if not last_name:
            raise ValidationError("El apellido es obligatorio")
        
        is_superuser = extra_fields.get('is_superuser')
        rut = extra_fields.get('rut')

        if not is_superuser and not rut:
            raise ValueError('El campo "rut" es requerido.')
        
        user=self.model(email=email.lower(), first_name=first_name.upper(), last_name=last_name.upper(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user
    
    

    def create_superuser(self, email, first_name, last_name, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValidationError("is_staff debe ser True para administración")
        
        if extra_fields.get("is_superuser") is not True:
            raise ValidationError("is_superuser debe ser True para administración")
        
        user=self.create_user(email, first_name, last_name, password, **extra_fields)

        return user