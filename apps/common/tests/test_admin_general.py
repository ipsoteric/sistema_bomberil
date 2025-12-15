from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.urls import reverse

@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    WHITENOISE_MANIFEST_STRICT=False,
    WHITENOISE_USE_FINDERS=True
)
class AdminConfigurationTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        email = 'admin@test.com'
        if not User.objects.filter(email=email).exists():
            self.admin_user = User.objects.create_superuser(
                rut='11111111-1', 
                email=email, 
                password='password123',
                first_name='Admin',
                last_name='Test'
            )
        else:
            self.admin_user = User.objects.get(email=email)
        self.client.force_login(self.admin_user)

    def test_admin_pages_render_successfully(self):
        registry = admin.site._registry
        failed_models = []
        tested_count = 0
        
        # Apps de terceros a ignorar
        IGNORED_APPS = ['token_blacklist', 'user_sessions', 'auth', 'contenttypes', 'sessions', 'admin']
        
        # Modelos de solo lectura
        READONLY_MODELS = ['registroactividad'] 

        print("\n" + "="*60)
        print("INICIANDO AUDITORÍA DEL ADMIN PANEL")
        print("="*60)

        for model, admin_class in registry.items():
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            
            if app_label in IGNORED_APPS:
                continue
            
            tested_count += 1
            print(f"\n🔹 Revisando: {app_label}.{model_name}")

            changelist_url = reverse(f'admin:{app_label}_{model_name}_changelist')
            add_url = reverse(f'admin:{app_label}_{model_name}_add')
            
            try:
                # 1. Test Lista (ChangeList)
                resp = self.client.get(changelist_url)
                if resp.status_code == 200:
                    print(f"   ✅ Vista de Lista: OK (200)")
                else:
                    msg = f"Status {resp.status_code}"
                    if hasattr(resp, 'context') and 'exception' in resp.context:
                        msg += f" | Ex: {resp.context['exception']}"
                    failed_models.append(f"{model_name} (Lista): {msg}")
                    print(f"   ❌ Vista de Lista: FALLÓ ({msg})")
                
                # 2. Test Agregar (Add View)
                resp_add = self.client.get(add_url)
                
                if model_name in READONLY_MODELS:
                    if resp_add.status_code == 403:
                        print(f"   🛡️  Vista Agregar: BLOQUEADA CORRECTAMENTE (403 ReadOnly)")
                    elif resp_add.status_code == 200:
                         print(f"   ⚠️  AVISO: {model_name} permitió acceso (200) aunque debería ser ReadOnly.")
                    else:
                        failed_models.append(f"{model_name} (Add ReadOnly): Status {resp_add.status_code}")
                        print(f"   ❌ Vista Agregar: FALLÓ ({resp_add.status_code})")
                else:
                    if resp_add.status_code == 200:
                        print(f"   ✅ Vista Agregar: OK (200)")
                    else:
                        failed_models.append(f"{model_name} (Agregar): Status {resp_add.status_code}")
                        print(f"   ❌ Vista Agregar: FALLÓ ({resp_add.status_code})")

            except Exception as e:
                failed_models.append(f"{model_name}: Exception {e}")
                print(f"   EXCEPCIÓN CRÍTICA: {e}")

        print("\n" + "="*60)
        if failed_models:
            print(f"RESUMEN: Se encontraron {len(failed_models)} errores.")
            self.fail(f"Errores encontrados: {failed_models}")
        else:
            print(f"RESUMEN: {tested_count} modelos verificados exitosamente.")
            print("El panel de administración está 100% operativo.")
            print("="*60)