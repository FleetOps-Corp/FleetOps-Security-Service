import os, uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8443,
        ssl_certfile=os.environ["TLS_CERT_PATH"],
        ssl_keyfile=os.environ["TLS_KEY_PATH"],
    )
