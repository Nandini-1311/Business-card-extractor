import os
from dotenv import find_dotenv, dotenv_values

print("cwd:", os.getcwd())
path = find_dotenv(usecwd=True)
print(".env found at:", path or "NONE")

vals = dotenv_values(path) if path else {}
for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"]:
    print(f"{k}: file={vals.get(k)!r} | windows_env={os.environ.get(k)!r}")

fp = vals.get("DB_PASSWORD") or ""
ep = os.environ.get("DB_PASSWORD")
print("DB_PASSWORD length in .env file:", len(fp))
print("DB_PASSWORD set in Windows env:", ep is not None, "| length:", len(ep) if ep else None)
