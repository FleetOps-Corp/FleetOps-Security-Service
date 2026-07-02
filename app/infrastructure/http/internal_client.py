import httpx, os

client = httpx.Client(verify=os.environ["CA_BUNDLE_PATH"])
response = client.get("https://auth-service:8443/auth/validate")
