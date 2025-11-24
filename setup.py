"""Setup configuration for ngenctl package."""

from setuptools import setup, find_packages
from setuptools.command.install import install
from pathlib import Path
import os
import stat

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""


class PostInstallCommand(install):
    """Post-installation for installation mode."""
    
    def run(self):
        """Run post-installation tasks."""
        install.run(self)
        # Install scripts to /usr/local/bin and make them executable
        # Find the installed package directory
        if self.install_lib:
            package_dir = Path(self.install_lib) / "ngenctl" / "scripts"
        else:
            # Fallback: try to find in installed packages
            try:
                import ngenctl
                package_dir = Path(ngenctl.__file__).parent / "scripts"
            except ImportError:
                # During build, use source directory
                package_dir = Path(__file__).parent / "ngenctl" / "scripts"
        
        if package_dir.exists():
            target_dir = Path("/usr/local/bin")
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                
                for script_file in package_dir.glob("ngenctl-*"):
                    if script_file.is_file():
                        target_script = target_dir / script_file.name
                        import shutil
                        try:
                            shutil.copy2(script_file, target_script)
                            # Make executable (rwxr-xr-x)
                            target_script.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                            print(f"Installed {target_script}")
                        except PermissionError:
                            print(f"Warning: Could not install {target_script} - permission denied (requires root)")
                        except Exception as e:
                            print(f"Warning: Could not install {target_script}: {e}")
            except PermissionError:
                print(f"Warning: Could not create {target_dir} - permission denied (requires root)")
                print("Note: Scripts are available in the package, but not installed to /usr/local/bin")
            except Exception as e:
                print(f"Warning: Could not install scripts to {target_dir}: {e}")


setup(
    packages=["ngenctl"],
    package_dir={"ngenctl": "ngenctl"},
    cmdclass={
        "install": PostInstallCommand,
    },
)

