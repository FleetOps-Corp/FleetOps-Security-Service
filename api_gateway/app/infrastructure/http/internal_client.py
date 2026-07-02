import os
import httpx

CA_BUNDLE_PATH = os.environ["CA_BUNDLE_PATH"]

auth_service_client = httpx.Client(
    base_url=f"https://auth-service:{os.environ['AUTH_SERVICE_PORT']}",
    verify=CA_BUNDLE_PATH,
)

role_service_client = httpx.Client(
    base_url=f"https://role-service:{os.environ['ROLE_SERVICE_PORT']}",
    verify=CA_BUNDLE_PATH,
)
