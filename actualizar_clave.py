import bcrypt
from supabase import create_client

# Conexión a Supabase
url = "TU_SUPABASE_URL"
key = "TU_SUPABASE_KEY"
supabase = create_client(url, key)

# Usuario y clave actual
usuario = "admin"
clave_plana = "1234"

# Generar hash bcrypt
hashed = bcrypt.hashpw(clave_plana.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Actualizar en Supabase
supabase.table("usuarios").update({"clave": hashed}).eq("usuario", usuario).execute()

print("✅ Contraseña actualizada correctamente.")
