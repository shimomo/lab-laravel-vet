#!/bin/sh
# (Re)creates everything that depends on where this directory lives: the local test CA and the
# server certificate for 127.0.0.1, the PHP setting that trusts them, and env.sh.
# Run it again after moving the directory, or once the certificate expires (365 days).
set -e
S="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$S/ca" "$S/php-ini" "$S/logs" "$S/prompts"
cd "$S/ca"

openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem -days 365 \
    -subj "/CN=vetlab local test CA" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2> /dev/null
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr -subj "/CN=127.0.0.1" 2> /dev/null
printf 'subjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n' > server.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out server.pem -days 365 -extfile server.ext 2> /dev/null
chmod 600 ca.key server.key

# Composer and vet must still reach Packagist and GitHub, so the test CA is added to the system bundle.
cat /etc/ssl/certs/ca-certificates.crt ca.pem > bundle.pem
printf 'openssl.cafile=%s\ncurl.cainfo=%s\n' "$S/ca/bundle.pem" "$S/ca/bundle.pem" > "$S/php-ini/zz-vetlab.ini"

cat > "$S/env.sh" << EOF
export S="$S"
export COMPOSER_HOME="\$S/.composer-home"
export COMPOSER_CACHE_DIR="\$S/.composer-cache"
export VET_CACHE_DIR="\$S/.vet-cache"
export PHP_INI_SCAN_DIR=":\$S/php-ini"
export SSL_CERT_FILE="\$S/ca/bundle.pem"
EOF

echo "vetlab is set up at [$S]; the certificate is valid until $(openssl x509 -in server.pem -noout -enddate | cut -d= -f2)."
