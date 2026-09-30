import re


def load_api_key(version_name: str) -> str:
    """Read a key into memory through ADC; never write it to disk or logs."""
    if not re.fullmatch(r"projects/[^/]+/secrets/[^/]+/versions/[^/]+", version_name):
        raise ValueError("a Secret Manager version resource is required")
    from google.cloud import secretmanager

    with secretmanager.SecretManagerServiceClient() as client:
        response = client.access_secret_version(request={"name": version_name}, timeout=10)
    value = response.payload.data.decode("utf-8").strip()
    if not value:
        raise ValueError("empty API key")
    return value
