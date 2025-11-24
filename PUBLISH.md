# Panduan Publish Package ngen ke PyPI

Dokumen ini menjelaskan langkah-langkah untuk membangun dan mempublish package `ngen` ke PyPI (Python Package Index).

## Prerequisites

Sebelum mempublish, pastikan Anda memiliki:

1. **Akun PyPI**
   - Daftar di https://pypi.org/account/register/
   - Verifikasi email Anda

2. **API Token PyPI** (Direkomendasikan)
   - Buat API token di https://pypi.org/manage/account/token/
   - Pilih scope: "Entire account" atau "Specific project: ngen"
   - Simpan token dengan aman

3. **Test PyPI Account** (Opsional, untuk testing)
   - Daftar di https://test.pypi.org/account/register/
   - Buat API token juga di Test PyPI

4. **Tools yang Diperlukan**
   ```bash
   pip install --upgrade build twine
   ```

## Konfigurasi Credentials

### Metode 1: Menggunakan API Token (Direkomendasikan)

**Untuk Akun Baru:**

1. Buat file `~/.pypirc` dengan konten berikut:

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

[testpypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Penting:** 
- Ganti `xxxxxxxx...` dengan API token Anda dari https://pypi.org/manage/account/token/
- Token PyPI dimulai dengan `pypi-`
- Test PyPI juga menggunakan format yang sama
- Script akan otomatis menggunakan credentials ini saat publish

**File Location:** `~/.pypirc` atau `/home/username/.pypirc`

**Verifikasi:**
```bash
cat ~/.pypirc
# Script akan otomatis check file ini sebelum publish
```

### Metode 2: Menggunakan Username/Password

Tambahkan di `~/.pypirc`:

```ini
[pypi]
username = your_username
password = your_password

[testpypi]
username = your_test_username
password = your_test_password
```

**Note:** Password harus berupa API token, bukan password akun biasa jika menggunakan two-factor authentication.

## Langkah-langkah Publish

### Untuk Akun Baru dan Project Baru

Jika Anda menggunakan akun PyPI baru dan project belum pernah di-publish:

1. **Pastikan `~/.pypirc` sudah dikonfigurasi** dengan API token Anda
2. **Script akan otomatis detect** bahwa project belum ada
3. **PyPI akan otomatis create project** saat first upload
4. **Anda akan menjadi owner** project tersebut

**Catatan:**
- Pastikan package name tersedia (belum digunakan user lain)
- Script akan check apakah project sudah ada sebelum upload
- Jika project sudah ada dan dimiliki user lain, akan muncul 403 Forbidden

### Opsi 1: Menggunakan Script Otomatis (Direkomendasikan)

Script `publish.sh` akan:
- ✅ Otomatis menggunakan credentials dari `~/.pypirc`
- ✅ Validasi credentials sebelum publish
- ✅ Check apakah project sudah ada di PyPI
- ✅ Otomatis create project jika belum ada (PyPI akan create project saat first upload)
- ✅ Validasi semua requirements sebelum publish
- ✅ Extract package name otomatis dari `pyproject.toml`

```bash
# 1. Build package
./publish.sh

# 2. Test di Test PyPI (opsional tapi direkomendasikan)
./publish.sh --test

# 3. Install dari Test PyPI untuk verifikasi
pip install -i https://test.pypi.org/simple/ ngen

# 4. Publish ke PyPI production
./publish.sh --publish
```

**Note:** Script akan otomatis detect jika project belum ada dan akan membuat project baru saat first upload ke PyPI.

### Opsi 2: Manual

```bash
# 1. Clean previous builds
rm -rf dist/ build/ *.egg-info

# 2. Build package
python3 -m build

# 3. Check distribution
python3 -m twine check dist/*

# 4. Upload ke Test PyPI (opsional)
python3 -m twine upload --repository testpypi dist/*

# 5. Upload ke PyPI production
python3 -m twine upload --repository pypi dist/*
```

## Proses Build dan Publish

Script `publish.sh` akan melakukan:

1. **Check Requirements** - Memastikan Python, build, twine, dan requests terinstall
2. **Check PyPI Credentials** - Memverifikasi `~/.pypirc` ada dan valid
3. **Check Package** - Memverifikasi file-file penting ada
4. **Check Project Existence** - Cek apakah project sudah ada di PyPI/Test PyPI
5. **Clean Build** - Menghapus build sebelumnya
6. **Build Package** - Membuat wheel dan source distribution
7. **Check Distribution** - Memverifikasi package menggunakan twine check
8. **Upload** - Upload menggunakan credentials dari `~/.pypirc`
9. **Auto Create Project** - Jika project belum ada, PyPI akan otomatis create saat first upload

## Struktur Package yang Akan Di-publish

```
dist/
├── ngen-0.1.0-py3-none-any.whl  # Wheel distribution
└── ngen-0.1.0.tar.gz            # Source distribution
```

## Checklist Sebelum Publish

- [ ] Version number di `pyproject.toml` dan `__init__.py` sudah diupdate
- [ ] README.md sudah lengkap dan benar
- [ ] Semua file di `MANIFEST.in` sudah tercakup
- [ ] Package sudah di-test secara lokal
- [ ] Script sudah di-build dan di-check dengan twine
- [ ] Jika versi baru, sudah di-test di Test PyPI

## Update Version

Sebelum publish versi baru:

1. Update version di `pyproject.toml`:
   ```toml
   version = "0.1.1"  # Increment version
   ```

2. Update version di `ngen/__init__.py`:
   ```python
   __version__ = "0.1.1"
   ```

3. Commit perubahan:
   ```bash
   git add pyproject.toml ngen/__init__.py
   git commit -m "Bump version to 0.1.1"
   git tag v0.1.1
   git push origin main --tags
   ```

## Verifikasi setelah Publish

1. **Cek di PyPI:**
   - https://pypi.org/project/ngen/

2. **Test Install:**
   ```bash
   pip install ngen
   ```

3. **Test Command:**
   ```bash
   ngen --help
   ```

## Troubleshooting

### Error: "HTTPError: 400 Bad Request"

- Pastikan version number unik (tidak pernah di-publish sebelumnya)
- Pastikan nama package belum digunakan (jika baru)

### Error: "403 Forbidden" - "The user 'xxx' isn't allowed to upload to project 'ngen'"

Error ini terjadi ketika:
- Project dengan nama yang sama sudah ada di PyPI
- Project tersebut dimiliki oleh user lain
- Anda tidak memiliki permission untuk upload ke project tersebut

**Solusi:**

1. **Ganti Nama Package** (Direkomendasikan jika project lain sudah aktif)
   
   Update `pyproject.toml`:
   ```toml
   [project]
   name = "ngen-tools"  # atau python-ngen, ngen-wrapper, dll
   ```
   
   Update `setup.py`:
   ```python
   name="ngen-tools"
   ```
   
   Update `PACKAGE_NAME` di `publish.sh` jika perlu, atau extract dari pyproject.toml
   
   Cek nama yang tersedia di:
   - https://pypi.org/project/nama-package/

2. **Request Access dari Owner Project**
   
   - Kunjungi https://pypi.org/project/ngen/
   - Cari contact owner project
   - Request access atau ownership transfer
   - Hanya cocok jika project tersebut inactive atau Anda adalah maintainer resmi

3. **Gunakan Test PyPI untuk Testing**
   
   ```bash
   ./publish.sh --test
   ```
   
   Test PyPI tidak memiliki conflict dengan production PyPI

**Cara Cek Apakah Nama Tersedia:**

```bash
# Method 1: Using curl
curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/ngen/json
# Output 404 = nama tersedia
# Output 200 = nama sudah digunakan

# Method 2: Using Python
python3 -c "
import requests
r = requests.get('https://pypi.org/pypi/ngen/json')
if r.status_code == 200:
    print('❌ Nama sudah digunakan')
    print(f'Project URL: https://pypi.org/project/ngen/')
else:
    print('✅ Nama tersedia')
"

# Method 3: Using publish.sh (akan auto-check saat publish)
./publish.sh --publish
```

**Catatan Penting:**
- Script `publish.sh` akan otomatis extract package name dari `pyproject.toml`
- Jika Anda mengganti nama di `pyproject.toml`, script akan otomatis menggunakan nama baru
- Tidak perlu update `PACKAGE_NAME` di `publish.sh` secara manual

### Error: "Package not found"

- Pastikan package sudah ter-build dengan benar
- Cek file di `dist/` directory

### Build Error: "Absolute path"

- Pastikan `setup.py` tidak menggunakan absolute paths
- Gunakan relative paths dari setup.py directory

## Best Practices

1. **Selalu test di Test PyPI terlebih dahulu**
   ```bash
   ./publish.sh --test
   pip install -i https://test.pypi.org/simple/ ngen
   ```

2. **Gunakan semantic versioning**
   - MAJOR.MINOR.PATCH (contoh: 1.0.0, 1.0.1, 1.1.0, 2.0.0)

3. **Jangan publish versi yang sama dua kali**
   - PyPI tidak mengizinkan overwrite versi yang sudah ada

4. **Gunakan API token, bukan password**
   - Lebih aman dan bisa di-revoke jika diperlukan

5. **Tag git release**
   ```bash
   git tag v0.1.0
   git push origin --tags
   ```

## File yang Di-include

Package akan include:
- `ngen/` - Package source code
- `ngen/scripts/` - Script-script wrapper (ngen-*)
- `README.md` - Documentation
- `MANIFEST.in` - File manifest untuk non-Python files

## Komando Cepat

```bash
# Build only
./publish.sh --build-only

# Test PyPI
./publish.sh --test

# Production PyPI
./publish.sh --publish

# Help
./publish.sh --help
```

## Keamanan

⚠️ **PENTING:**
- Jangan commit `~/.pypirc` ke git
- Jangan commit API token ke repository
- Gunakan `.gitignore` untuk exclude file sensitif
- Rotate API token secara berkala

## Referensi

- [PyPI Documentation](https://packaging.python.org/guides/distributing-packages-using-setuptools/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Python Packaging Guide](https://packaging.python.org/)

