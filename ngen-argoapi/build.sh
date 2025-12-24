#!/bin/bash
# Script untuk build dan publish package ngen-argocd ke PyPI

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
# Extract package name from pyproject.toml automatically
if [ -f "pyproject.toml" ]; then
    PACKAGE_NAME=$(python3 -c "
import re
try:
    with open('pyproject.toml', 'r') as f:
        content = f.read()
        # Try to find name = \"package-name\" or name = 'package-name'
        match = re.search(r'^name\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
        if not match:
            match = re.search(r\"^name\s*=\s*'([^']+)'\", content, re.MULTILINE)
        if match:
            print(match.group(1))
        else:
            print('ngen-argocd')
except:
    print('ngen-argocd')
" 2>/dev/null || echo "ngen-argocd")
else
    PACKAGE_NAME="ngen-argocd"
fi

PYPI_REPO="pypi"

# Functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    print_info "Checking requirements..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found. Please install Python 3.7+"
        exit 1
    fi
    
    if ! python3 -m pip show build &> /dev/null; then
        print_warn "build package not found. Installing..."
        python3 -m pip install --upgrade build
    fi
    
    if ! python3 -m pip show twine &> /dev/null; then
        print_warn "twine package not found. Installing..."
        python3 -m pip install --upgrade twine
    fi
    
    # Check for httpx library
    if ! python3 -m pip show httpx &> /dev/null; then
        print_warn "httpx package not found. Installing..."
        python3 -m pip install --upgrade httpx
    fi
    
    print_info "Requirements check completed"
}

check_pypirc() {
    print_info "Checking PyPI credentials..."
    
    PYPI_RC="$HOME/.pypirc"
    
    if [ ! -f "$PYPI_RC" ]; then
        print_error ".pypirc not found at $PYPI_RC"
        print_error "Please create ~/.pypirc with your PyPI credentials"
        exit 1
    fi
    
    # Verify .pypirc has [pypi] section
    if ! grep -q "\[pypi\]" "$PYPI_RC"; then
        print_error ".pypirc found but missing [pypi] section"
        print_error "Please add [pypi] section with username and password"
        exit 1
    fi
    
    print_info "PyPI credentials found in ~/.pypirc"
}

increment_version() {
    print_info "Checking current version..."
    
    # Read current version from pyproject.toml
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found!"
        return 1
    fi
    
    current_version=$(python3 -c "
import re
try:
    with open('pyproject.toml', 'r') as f:
        content = f.read()
        match = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
        if match:
            print(match.group(1))
        else:
            print('0.1.0')
except Exception:
    print('0.1.0')
" 2>/dev/null || echo "0.1.0")
    
    if [ -z "$current_version" ]; then
        current_version="0.1.0"
    fi
    
    print_info "Current version: $current_version"
    
    # Parse version components (major.minor.patch)
    IFS='.' read -ra version_parts <<< "$current_version"
    major="${version_parts[0]:-0}"
    minor="${version_parts[1]:-1}"
    patch="${version_parts[2]:-0}"
    
    # Calculate new versions
    new_patch=$((patch + 1))
    new_minor=$((minor + 1))
    new_major=$((major + 1))
    
    patch_version="${major}.${minor}.${new_patch}"
    minor_version="${major}.${new_minor}.0"
    major_version="${new_major}.0.0"
    
    # Interactive prompts: Default is patch
    print_info ""
    print_info "Version increment options:"
    print_info "  1. Patch: $current_version → $patch_version (default)"
    print_info "  2. Minor: $current_version → $minor_version"
    print_info "  3. Major: $current_version → $major_version"
    print_info ""
    
    # First prompt: Patch (default Y)
    read -p "Increment patch version to $patch_version? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        # Second prompt: Minor
        print_info ""
        read -p "Increment minor version to $minor_version? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            # Third prompt: Major
            print_info ""
            read -p "Increment major version to $major_version? (Y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                print_error "Version increment cancelled by user"
                return 1
            else
                new_version="$major_version"
                print_info "✅ Incrementing major version to $new_version"
            fi
        else
            new_version="$minor_version"
            print_info "✅ Incrementing minor version to $new_version"
        fi
    else
        new_version="$patch_version"
        print_info "✅ Incrementing patch version to $new_version"
    fi
    
    # Update pyproject.toml
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/version = \"$current_version\"/version = \"$new_version\"/g" pyproject.toml
    else
        # Linux
        sed -i "s/version = \"$current_version\"/version = \"$new_version\"/g" pyproject.toml
    fi
    
    # Update ngen_argocd/__init__.py
    if [ -f "ngen_argocd/__init__.py" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/__version__ = \"$current_version\"/__version__ = \"$new_version\"/g" ngen_argocd/__init__.py
        else
            # Linux
            sed -i "s/__version__ = \"$current_version\"/__version__ = \"$new_version\"/g" ngen_argocd/__init__.py
        fi
    fi
    
    print_info "Version updated to $new_version"
    return 0
}

clean_build() {
    print_info "Cleaning previous builds..."
    rm -rf dist/
    rm -rf build/
    rm -rf *.egg-info
    rm -rf ${PACKAGE_NAME}.egg-info
    print_info "Clean completed"
}

check_package() {
    print_info "Checking package files..."
    
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found!"
        exit 1
    fi
    
    if [ ! -f "README.md" ]; then
        print_error "README.md not found!"
        exit 1
    fi
    
    if [ ! -d "ngen_argocd" ]; then
        print_error "ngen_argocd package directory not found!"
        exit 1
    fi
    
    print_info "Package files check completed"
}

build_package() {
    print_info "Building package..."
    python3 -m build
    
    if [ $? -eq 0 ]; then
        print_info "Build completed successfully"
        ls -lh dist/
    else
        print_error "Build failed!"
        exit 1
    fi
}

check_dist() {
    print_info "Checking distribution files..."
    python3 -m twine check dist/*
    
    if [ $? -eq 0 ]; then
        print_info "Distribution files check passed"
    else
        print_error "Distribution files check failed!"
        exit 1
    fi
}

test_package() {
    print_info "Running package tests..."
    local test_passed=0
    local test_failed=0
    
    # Test 1: Import package
    print_info "  Test 1: Import package..."
    if python3 -c "
import sys
sys.path.insert(0, '.')
# Test that package can be imported
import ngen_argocd
print('✅ Package directory (ngen_argocd) imported successfully')
" 2>/dev/null; then
        ((test_passed++))
    else
        print_error "  ❌ Failed to import package"
        ((test_failed++))
    fi

    # Test 2: Check package version
    print_info "  Test 2: Check package version..."
    if python3 -c "
import sys
sys.path.insert(0, '.')
import ngen_argocd
print(f'✅ Version: {ngen_argocd.__version__}')
" 2>/dev/null; then
        ((test_passed++))
    else
        print_error "  ❌ Failed to get package version"
        ((test_failed++))
    fi

    # Test 3: Check CLI entry point
    print_info "  Test 3: Check CLI entry point..."
    if python3 -c "
import sys
sys.path.insert(0, '.')
from ngen_argocd.cli import main
print('✅ CLI entry point found')
" 2>/dev/null; then
        ((test_passed++))
    else
        print_error "  ❌ CLI entry point not found"
        ((test_failed++))
    fi
    
    # Test 4: Test CLI help command
    print_info "  Test 4: Test CLI help command..."
    # Try different ways to invoke help
    help_output=$(python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from ngen_argocd.cli import main
    import sys
    sys.argv = ['ngen-argocd', '--help']
    main()
except SystemExit as e:
    if e.code == 0:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

    if echo "$help_output" | grep -q "Usage:"; then
        print_info "    ✅ CLI help command works"
        ((test_passed++))
    else
        print_error "  ❌ CLI help command failed"
        print_error "    Debug output: $help_output"
        ((test_failed++))
    fi
    
    # Test 6: Check wheel installation (if dist exists)
    if [ -d "dist" ] && ls dist/*.whl 1> /dev/null 2>&1; then
        print_info "  Test 6: Test wheel installation..."
        wheel_file=$(ls dist/*.whl | head -1)
        # Try to extract and check structure
        if python3 -c "
import zipfile
import sys
try:
    with zipfile.ZipFile('$wheel_file', 'r') as z:
        files = z.namelist()
        if any('ngen_argocd/__init__.py' in f for f in files):
            print('✅ Wheel contains package files')
            sys.exit(0)
        else:
            print('❌ Wheel missing package files')
            sys.exit(1)
except Exception as e:
    print(f'❌ Error checking wheel: {e}')
    sys.exit(1)
" 2>/dev/null; then
            ((test_passed++))
        else
            print_error "  ❌ Wheel structure check failed"
            ((test_failed++))
        fi
    else
        print_info "  Test 6: Skipped (no wheel file found)"
    fi
    
    # Summary
    echo
    print_info "Test Summary:"
    print_info "  ✅ Passed: $test_passed"
    if [ $test_failed -gt 0 ]; then
        print_error "  ❌ Failed: $test_failed"
        print_error "Please fix the failing tests before publishing"
        return 1
    else
        print_info "  ✅ All tests passed!"
        return 0
    fi
}

# Main script
main() {
    echo "======================================"
    echo "  ${PACKAGE_NAME} Package Publisher"
    echo "======================================"
    echo
    
    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "Please run this script from the package root directory"
        exit 1
    fi
    
    check_requirements
    check_pypirc
    check_package
    
    # Increment version before building
    increment_version
    if [ $? -ne 0 ]; then
        print_warn "Build cancelled due to version increment failure"
        exit 1
    fi
    
    clean_build
    build_package
    check_dist
    test_package || exit 1
    
    echo
    echo "======================================"
    echo "  Build completed successfully!"
    echo "======================================"
    echo
    echo "Next steps:"
    echo "1. Test locally: pip install dist/${PACKAGE_NAME}-*.whl"
    echo "2. Publish to PyPI: ./build.sh --release"
    echo
}

# Handle command line arguments
case "${1:-}" in
    --release)
    check_requirements
    check_pypirc
    check_package
    if [ ! -d "dist" ]; then
        print_warn "No dist directory found. You need to build first."
        print_warn "Run './build.sh' to build with version increment, then './build.sh --release' to publish"
        exit 1
    fi
    test_package || exit 1
    python3 -m twine upload --repository pypi dist/*
        ;;
    --build-only)
        check_requirements
        check_package
        
        # Increment version before building
        increment_version
        if [ $? -ne 0 ]; then
            print_warn "Build cancelled due to version increment failure"
            exit 1
        fi
        
        clean_build
        build_package
        check_dist
        test_package || exit 1
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo
        echo "Options:"
        echo "  (no option)    Build package and check distribution"
        echo "  --release      Build and publish to PyPI (production)"
        echo "  --build-only   Only build package, don't publish"
        echo "  --help, -h     Show this help message"
        echo
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
