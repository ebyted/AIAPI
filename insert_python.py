import requests

# 1. Define la URL base de tu API
BASE_URL = "http://168.231.67.221:8011"

# 2. Prepara el payload de registro
payload = {
    "username": "caleb",
    "full_name": "Caleb",
    "password": "arkano"
}

# 3. Hace la petición POST a /register
resp = requests.post(
    f"{BASE_URL}/register",
    json=payload,
    headers={"Content-Type": "application/json"}
)

# 4. Procesa la respuesta
if resp.status_code == 201:
    print("✅ Usuario creado:", resp.json()["msg"])
elif resp.status_code == 400:
    print("❌ Error al crear usuario:", resp.json()["detail"])
else:
    print(f"⚠️ Respuesta inesperada [{resp.status_code}]:", resp.text)
