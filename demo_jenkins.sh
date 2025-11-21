#!/bin/bash
# Demo script untuk menggunakan ngen-j dengan Jenkins server http://193.1.1.3:8080/

echo "=== Demo ngen-j dengan Jenkins ==="
echo

# Cara 1: Set environment variables secara manual
echo "Cara 1: Set environment variables secara manual"
echo "================================================"
export JENKINS_URL="http://193.1.1.3:8080"

# Untuk username dan password, kita akan menggunakan base64 encoding
# Ganti 'admin' dan 'password' dengan credentials yang benar
JENKINS_USER="admin"
JENKINS_PASS="password"

# Encode ke base64
JENKINS_AUTH=$(echo -n "${JENKINS_USER}:${JENKINS_PASS}" | base64)
export JENKINS_AUTH="$JENKINS_AUTH"

echo "JENKINS_URL: $JENKINS_URL"
echo "JENKINS_AUTH: $JENKINS_AUTH"
echo

# Cara 2: Menggunakan perintah login (recommended)
echo "Cara 2: Menggunakan perintah login (recommended)"
echo "=============================================="
echo "Untuk menggunakan perintah login secara interaktif:"
echo "ngen-j login"
echo
echo "Perintah login akan:"
echo "- Meminta Jenkins URL"
echo "- Memilih metode autentikasi"
echo "- Menyimpan credentials ke ~/.ngen-j/.env"
echo "- Test koneksi"
echo

echo "Environment variables yang diset:"
echo "JENKINS_URL: $JENKINS_URL"
echo "JENKINS_USER: $JENKINS_USER"
echo "JENKINS_AUTH: [ENCODED]"
echo

# Install ngen-j jika belum terinstall
echo "Memastikan ngen-j terinstall..."
pip install -e . >/dev/null 2>&1
echo

# Test versi
echo "=== Test Versi ==="
ngen-j --version
echo

# Test koneksi Jenkins
echo "=== Test Koneksi Jenkins ==="
ngen-j check
echo

# Test help
echo "=== Help ==="
ngen-j --help
echo

# Test list jobs (akan gagal jika credentials salah)
echo "=== Test List Jobs ==="
ngen-j jobs
echo

echo "=== Setelah Login ==="
echo "Setelah menjalankan 'ngen-j login', Anda bisa langsung menggunakan:"
echo "ngen-j check                    # Validasi koneksi"
echo "ngen-j jobs                     # List semua jobs"
echo "ngen-j job <nama-job>           # Detail job"
echo "ngen-j build <nama-job>         # Trigger build"
echo
echo "Tanpa perlu set environment variables setiap kali!"
echo

echo "=== Catatan ==="
echo "1. Gunakan 'ngen-j login' untuk setup credentials (recommended)"
echo "2. Gunakan 'ngen-j check' untuk validasi koneksi setelah login"
echo "3. Ganti JENKINS_USER dan JENKINS_PASS dengan credentials yang benar"
echo "4. Pastikan Jenkins server di http://193.1.1.3:8080/ dapat diakses"
echo "5. Jika menggunakan HTTPS, pastikan sertifikat valid atau gunakan HTTP"
echo "6. Untuk production, gunakan API token Jenkins alih-alih password"
echo "7. Credentials disimpan di ~/.ngen-j/.env dengan permission 600 (owner only)"
