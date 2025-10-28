import os
import shutil

# Obtener el directorio actual (donde se ejecuta el script)
project_root = os.getcwd()

print(f"--- Iniciando limpieza del proyecto Django en: {project_root} ---")

for root, dirs, files in os.walk(project_root, topdown=True):
    
    # 1. Eliminar carpetas __pycache__
    if '__pycache__' in dirs:
        cache_dir = os.path.join(root, '__pycache__')
        print(f"Eliminando caché: {cache_dir}")
        try:
            shutil.rmtree(cache_dir)
            # Evita que os.walk intente entrar al directorio ya borrado
            dirs.remove('__pycache__')
        except OSError as e:
            print(f"  [ERROR] No se pudo eliminar {cache_dir}: {e}")

    # 2. Limpiar archivos de migración
    if 'migrations' in dirs:
        # Heurística simple: si hay un 'models.py' o 'apps.py' en el directorio
        # actual, asumimos que 'migrations' pertenece a una app de Django.
        if 'models.py' in files or 'apps.py' in files:
            migrations_dir = os.path.join(root, 'migrations')
            print(f"Limpiando migraciones en: {migrations_dir}")
            
            try:
                for f in os.listdir(migrations_dir):
                    file_path = os.path.join(migrations_dir, f)
                    
                    # No borrar el __init__.py, pero sí todo lo demás
                    if f != '__init__.py' and os.path.isfile(file_path):
                        if f.endswith('.py') or f.endswith('.pyc'):
                            print(f"  - Borrando archivo: {f}")
                            os.remove(file_path)
                    
                    # También limpiar __pycache__ dentro de migrations
                    elif f == '__pycache__' and os.path.isdir(file_path):
                         print(f"  - Borrando caché interno: {file_path}")
                         shutil.rmtree(file_path)
                         
            except OSError as e:
                print(f"  [ERROR] No se pudo limpiar {migrations_dir}: {e}")

# 3. Eliminar la base de datos SQLite (opcional)
db_path = os.path.join(project_root, 'db.sqlite3')
if os.path.exists(db_path):
    print(f"\nEliminando base de datos: {db_path}")
    try:
        os.remove(db_path)
        print("Base de datos eliminada.")
    except OSError as e:
        print(f"  [ERROR] No se pudo eliminar {db_path}: {e}")

print("\n--- ¡Limpieza completada! ---")
print("Ahora puedes ejecutar:")
print("1. python manage.py makemigrations")
print("2. python manage.py migrate")