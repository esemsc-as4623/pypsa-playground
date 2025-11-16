import sys
import yaml
import argparse
import subprocess

# Set up argument parser
parser = argparse.ArgumentParser(description='Install pip dependencies from environment.yaml file')
parser.add_argument('-f', '--file', default='environment.yaml', 
                   help='Path to environment.yaml file (default: environment.yaml)')
parser.add_argument('--continue-on-error', action='store_true',
                   help='Continue installation even if some packages fail')

# Parse argumentss
args = parser.parse_args()

# Use the specified file or default
with open(args.file) as file_handle:
    environment_data = yaml.safe_load(file_handle)

print("Installing dependencies with uv pip install...")

failed_packages = []
successful_packages = []

def install_package(package_name, package_type="conda"):
    """Install a package and return True if successful, False otherwise"""
    try:
        print(f"Installing {package_type} package: {package_name}")
        result = subprocess.run(
            ["uv", "pip", "install", package_name], 
            capture_output=True, 
            text=True, 
            check=True
        )
        successful_packages.append(package_name)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e.stderr.strip()}")
        failed_packages.append(package_name)
        return False

for dependency in environment_data["dependencies"]:
    if isinstance(dependency, dict):
        # Handle pip dependencies
        if 'pip' in dependency:
            for lib in dependency['pip']:
                success = install_package(lib, "pip")
                if not success and not args.continue_on_error:
                    print(f"Installation failed for {lib}. Use --continue-on-error to continue anyway.")
                    sys.exit(1)
    elif isinstance(dependency, str):
        # Handle conda dependencies - install them with uv pip instead
        # Skip python version specification and pip itself
        if not dependency.startswith('python') and dependency != 'pip':
            success = install_package(dependency, "conda")
            if not success and not args.continue_on_error:
                print(f"Installation failed for {dependency}. Use --continue-on-error to continue anyway.")
                sys.exit(1)

print("\nInstallation Summary:")
print(f"Successfully installed: {len(successful_packages)} packages")
print(f"Failed installations: {len(failed_packages)} packages")

if failed_packages:
    print("\nFailed packages:")
    for pkg in failed_packages:
        print(f"  - {pkg}")
    
if failed_packages and not args.continue_on_error:
    sys.exit(1)
else:
    print("Installation complete!")