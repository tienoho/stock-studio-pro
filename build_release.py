"""
Build & Packaging Script for AutoStock Studio.
Automates testing, PyInstaller binary compilation, distribution assembly, and ZIP packaging.
Can be run locally or within CI/CD pipelines (GitHub Actions).
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
import argparse


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = PROJECT_ROOT / "release_autostock_studio"
SPEC_FILE = PROJECT_ROOT / "AutoStockStudio.spec" if (PROJECT_ROOT / "AutoStockStudio.spec").exists() else PROJECT_ROOT / "AutoStockStudio.spec"


def run_command(cmd, cwd=PROJECT_ROOT, env=None):
    """Executes a command and streams output, raising an exception on failure."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    
    print(f"--> Executing: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), env=merged_env)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(str(c) for c in cmd)}")


def run_tests():
    """Runs automated unit test suite with offscreen Qt."""
    print("\n" + "=" * 60)
    print("  STAGE 1: RUNNING AUTOMATED UNIT TESTS")
    print("=" * 60)
    test_env = {"QT_QPA_PLATFORM": "offscreen"}
    run_command([sys.executable, "run_tests.py"], env=test_env)


def clean_previous_builds():
    """Removes previous build artifacts to ensure a fresh, reproducible build."""
    print("\n" + "=" * 60)
    print("  STAGE 2: CLEANING PREVIOUS BUILD ARTIFACTS")
    print("=" * 60)
    
    for target in [BUILD_DIR, RELEASE_DIR, DIST_DIR / "AutoStockStudio"]:
        if target.exists():
            print(f"Cleaning: {target}")
            shutil.rmtree(target, ignore_errors=True)
            
    # Also remove any leftover zip archives in dist
    if DIST_DIR.exists():
        for zip_file in DIST_DIR.glob("*.zip"):
            try:
                zip_file.unlink()
                print(f"Removed previous zip: {zip_file.name}")
            except Exception:
                pass


def compile_pyinstaller():
    """Invokes PyInstaller using spec file."""
    print("\n" + "=" * 60)
    print("  STAGE 3: COMPILING WITH PYINSTALLER")
    print("=" * 60)
    
    if not SPEC_FILE.exists():
        raise FileNotFoundError(f"Spec file not found: {SPEC_FILE}")
        
    run_command([sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--noconfirm"])
    
    exe_candidates = [
        DIST_DIR / "AutoStockStudio" / "AutoStockStudio.exe",
    ]
    exe_path = next((p for p in exe_candidates if p.exists()), None)
    if not exe_path:
        raise RuntimeError(f"Build failed: executable was not created in {DIST_DIR}.")
    print(f"Compiled executable verified: {exe_path}")
    return exe_path.parent


def assemble_distribution(bundle_dir: Path):
    """Assembles the final standalone distribution directory."""
    print("\n" + "=" * 60)
    print("  STAGE 4: ASSEMBLING RELEASE PACKAGE")
    print("=" * 60)
    
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Copy compiled bundle folder
    dest_bundle = RELEASE_DIR / bundle_dir.name
    print(f"Copying {bundle_dir} -> {dest_bundle} ...")
    shutil.copytree(bundle_dir, dest_bundle, dirs_exist_ok=True)
    
    # 2. Copy launcher scripts
    if (PROJECT_ROOT / "run_exe.bat").exists():
        shutil.copy2(PROJECT_ROOT / "run_exe.bat", RELEASE_DIR / "run_exe.bat")
        print("Copied launcher: run_exe.bat")
        
    if (PROJECT_ROOT / "run.bat").exists():
        shutil.copy2(PROJECT_ROOT / "run.bat", RELEASE_DIR / "run_source.bat")
        print("Copied launcher: run_source.bat")

    # 3. Create Release README
    readme_text = """============================================================
  AUTOSTOCK STUDIO - RELEASE BUNDLE
============================================================

CÁCH KHỞI ĐỘNG ỨNG DỤNG:
1. Nhấp đúp vào file 'run_exe.bat' để mở ứng dụng ngay (bản EXE độc lập).
2. Hoặc mở thư mục bundle và chạy AutoStockStudio.exe.
3. Nếu máy có cài sẵn Python, bạn cũng có thể chạy 'run_source.bat'.

YÊU CẦU HỆ THỐNG:
- Hệ điều hành: Windows 10 / Windows 11 (64-bit)
- Kết nối Internet để tìm kiếm và tải stock media.

DỮ LIỆU & CÀI ĐẶT:
- Dữ liệu cài đặt và lịch sử được lưu trữ tự động trong cơ sở dữ liệu nội bộ (SQLite).
- Thư mục lưu media mặc định có thể tùy chỉnh trong menu Cài Đặt.
"""
    (RELEASE_DIR / "README.txt").write_text(readme_text, encoding="utf-8")
    print("Created README.txt in release directory.")



def create_zip_package():
    """Compresses the release directory into a standalone zip file."""
    print("\n" + "=" * 60)
    print("  STAGE 5: CREATING ZIP DISTRIBUTION ARCHIVE")
    print("=" * 60)
    
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / "AutoStockStudio-windows-x64.zip"
    
    print(f"Compressing {RELEASE_DIR} -> {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(RELEASE_DIR):
            for file in files:
                file_path = Path(root) / file
                archive_name = Path("AutoStockStudio_Release") / file_path.relative_to(RELEASE_DIR)
                zf.write(file_path, str(archive_name))
                
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Created archive: {zip_path.name} ({size_mb:.2f} MB)")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build and package AutoStock Studio.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running the automated test suite.")
    parser.add_argument("--no-zip", action="store_true", help="Do not create a zip archive.")
    args = parser.parse_args()

    try:
        if not args.skip_tests:
            run_tests()
        else:
            print("Skipping automated tests as requested.")

        clean_previous_builds()
        bundle_dir = compile_pyinstaller()
        assemble_distribution(bundle_dir)
        
        zip_path = None
        if not args.no_zip:
            zip_path = create_zip_package()

        print("\n" + "=" * 60)
        print("  BUILD COMPLETE SUCCESSFULLY!")
        print("=" * 60)
        print(f"Release directory: {RELEASE_DIR}")
        if zip_path:
            print(f"Release ZIP:       {zip_path}")
        print("=" * 60 + "\n")
        
    except Exception as exc:
        print(f"\n[ERROR] Build aborted: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
