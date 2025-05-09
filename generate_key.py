# generate_key.py
from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    # Genera una clave secreta de 50 caracteres
    secret_key = get_random_secret_key()
    print(f"Generated SECRET_KEY: {secret_key}")
    
    # Opcional: escribir directamente al archivo .env
    with open('.env', 'a') as env_file:
        env_file.write(f"\nSECRET_KEY={secret_key}\n")
        print("SECRET_KEY añadida al archivo .env")