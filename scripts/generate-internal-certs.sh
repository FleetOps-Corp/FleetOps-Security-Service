#!/usr/bin/env bash
# generate-internal-certs.sh
# --------------------------------------------------------------------------
# Genera una CA interna autofirmada y certificados TLS por microservicio
# para cifrar las comunicaciones internas (Gateway -> AuthService,
# Gateway -> RoleService) descritas en el SAD de la célula de Seguridad.
#
# Uso:
#   ./generate-internal-certs.sh
#
# Salida:
#   ./certs/ca.crt              -> CA raíz interna (repartir a todos los servicios)
#   ./certs/<service>.crt/.key  -> certificado + llave privada por servicio
#
# NOTA: Estos certificados son para tráfico INTERNO entre contenedores en la
# misma red Docker/EC2. El acceso externo del cliente sigue pasando por el
# API Gateway con su propio certificado público (Let's Encrypt / ACM), como
# ya define el SAD en la Vista Física.
# --------------------------------------------------------------------------
set -euo pipefail

OUT_DIR="./certs"
DAYS_CA=3650
DAYS_LEAF=825   # límite práctico aceptado por la mayoría de clientes TLS
SERVICES=("api-gateway" "auth-service" "role-service")

mkdir -p "${OUT_DIR}"
cd "${OUT_DIR}"

echo "==> 1. Generando CA interna (fleetops-internal-ca)"
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days "${DAYS_CA}" \
  -subj "/O=FleetCorp/OU=FleetOps-Security-Cell/CN=fleetops-internal-ca" \
  -out ca.crt

for svc in "${SERVICES[@]}"; do
  echo "==> Generando certificado para ${svc}"

  openssl genrsa -out "${svc}.key" 2048

  openssl req -new -key "${svc}.key" \
    -subj "/O=FleetCorp/OU=FleetOps-Security-Cell/CN=${svc}" \
    -out "${svc}.csr"

  cat > "${svc}.ext" <<EOF
subjectAltName = DNS:${svc}, DNS:${svc}.fleetops.internal, DNS:localhost
extendedKeyUsage = serverAuth, clientAuth
EOF

  openssl x509 -req -in "${svc}.csr" \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "${svc}.crt" -days "${DAYS_LEAF}" -sha256 \
    -extfile "${svc}.ext"

  rm "${svc}.csr" "${svc}.ext"
  chmod 600 "${svc}.key"
done

rm -f ca.srl
echo "==> Listo. Certificados generados en ${OUT_DIR}/"
echo "    Distribuye ca.crt a todos los servicios (trust store interno)."
echo "    IMPORTANTE: nunca commitear ./certs al repositorio (ver .gitignore)."