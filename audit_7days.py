#!/usr/bin/env python3
import json
import os
import sys
import argparse
import datetime
import urllib.request
import concurrent.futures
import re
import subprocess
from pathlib import Path

# --- Configuration ---
COOLDOWN_DAYS = 7
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def log(msg, color=BLUE): print(f"{color}[*] {msg}{RESET}")
def success(msg): print(f"{GREEN}[+] {msg}{RESET}")
def warn(msg): print(f"{YELLOW}[!] {msg}{RESET}")
def error(msg): print(f"{RED}[-] {msg}{RESET}")

def get_pkg_age_npm(name, version):
    try:
        url = f"https://registry.npmjs.org/{name}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            time_str = data.get("time", {}).get(version)
            if time_str:
                return datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except: return None
    return None

def get_pkg_age_pypi(name, version):
    try:
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            urls = data.get("urls", [])
            if urls:
                upload_time = urls[0].get("upload_time_iso_8601")
                if upload_time:
                    return datetime.datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
    except: return None
    return None

def get_pkg_age_packagist(name, version):
    try:
        url = f"https://repo.packagist.org/p2/{name}.json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            for pkg_data in data.get("packages", {}).get(name, []):
                if pkg_data.get("version") == version:
                    time_str = pkg_data.get("time")
                    if time_str:
                        return datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except: return None
    return None

def get_pkg_age_crates(name, version):
    try:
        url = f"https://crates.io/api/v1/crates/{name}/{version}"
        headers = {"User-Agent": "7days-auditor (https://github.com/7days)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            time_str = data.get("version", {}).get("created_at")
            if time_str:
                return datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except: return None
    return None

def check_package(pkg_type, name, version, now):
    if pkg_type == "npm": pub_date = get_pkg_age_npm(name, version)
    elif pkg_type == "pypi": pub_date = get_pkg_age_pypi(name, version)
    elif pkg_type == "composer": pub_date = get_pkg_age_packagist(name, version)
    elif pkg_type == "cargo": pub_date = get_pkg_age_crates(name, version)
    else: return None
    
    if not pub_date:
        return f"{YELLOW}[?] {name}@{version}: Could not determine age.{RESET}"
    
    age_delta = now - pub_date
    if age_delta.days < COOLDOWN_DAYS:
        return f"{RED}[DANGER] {name}@{version}: Released {age_delta.days} days ago ({pub_date.strftime('%Y-%m-%d')}){RESET}"
    return None

def audit_npm():
    found_any = False
    now = datetime.datetime.now(datetime.timezone.utc)
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        if Path("package-lock.json").exists():
            found_any = True
            log("Auditing package-lock.json...")
            data = json.loads(Path("package-lock.json").read_text())
            for pkg_path, details in data.get("packages", {}).items():
                if not pkg_path: continue
                name = pkg_path.split("node_modules/")[-1]
                version = details.get("version")
                if name and version and not details.get("link"):
                    tasks.append(executor.submit(check_package, "npm", name, version, now))
        if Path("pnpm-lock.yaml").exists():
            found_any = True
            log("Auditing pnpm-lock.yaml...")
            content = Path("pnpm-lock.yaml").read_text()
            matches = re.findall(r'/(.*?)@(\d+\.\d+\.\d+.*?):', content)
            for name, version in matches:
                if "/" in name: name = name.split("/")[-1]
                tasks.append(executor.submit(check_package, "npm", name, version, now))
        
        if not found_any: return
        found_danger = False
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res and "[DANGER]" in res:
                print(res)
                found_danger = True
        if not found_danger: success("No 'young' JS packages found.")

def audit_python():
    found_any = False
    now = datetime.datetime.now(datetime.timezone.utc)
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        if Path("poetry.lock").exists():
            found_any = True
            log("Auditing poetry.lock...")
            content = Path("poetry.lock").read_text()
            matches = re.findall(r'\[\[package\]\]\s+name = "(.*?)"\s+version = "(.*?)"', content, re.DOTALL)
            for name, version in matches:
                tasks.append(executor.submit(check_package, "pypi", name, version, now))
        if Path("requirements.txt").exists():
            found_any = True
            log("Auditing requirements.txt...")
            content = Path("requirements.txt").read_text()
            matches = re.findall(r'^([^#\s][^=<>!]*)[=<>!]+([^#\s]+)', content, re.MULTILINE)
            for name, version in matches:
                tasks.append(executor.submit(check_package, "pypi", name.strip(), version.strip(), now))
        
        if not found_any: return
        found_danger = False
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res and "[DANGER]" in res:
                print(res)
                found_danger = True
        if not found_danger: success("No 'young' Python packages found.")

def audit_pipx():
    log("Auditing pipx installed packages...")
    try:
        res = subprocess.run(["pipx", "list", "--json"], capture_output=True, text=True)
        if res.returncode != 0:
            warn("pipx list --json failed. Is pipx installed?")
            return
        data = json.loads(res.stdout)
        now = datetime.datetime.now(datetime.timezone.utc)
        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for venv_name, venv_info in data.get("venvs", {}).items():
                metadata = venv_info.get("metadata", {})
                main_pkg = metadata.get("main_package", {})
                name = main_pkg.get("package")
                version = main_pkg.get("package_version")
                if name and version:
                    tasks.append(executor.submit(check_package, "pypi", name, version, now))
        
        found_danger = False
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res and "[DANGER]" in res:
                print(res)
                found_danger = True
        if not found_danger: success("No 'young' pipx packages found.")
    except Exception as e:
        warn(f"Failed to audit pipx: {e}")

def audit_composer():
    if not Path("composer.lock").exists(): return
    log("Auditing composer.lock...")
    data = json.loads(Path("composer.lock").read_text())
    now = datetime.datetime.now(datetime.timezone.utc)
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for pkg in data.get("packages", []) + data.get("packages-dev", []):
            name, version = pkg.get("name"), pkg.get("version")
            if name and version:
                clean_version = version[1:] if version.startswith('v') else version
                tasks.append(executor.submit(check_package, "composer", name, clean_version, now))
        found_danger = False
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res and "[DANGER]" in res:
                print(res)
                found_danger = True
        if not found_danger: success("No 'young' Composer packages found.")

def audit_cargo():
    if not Path("Cargo.lock").exists(): return
    log("Auditing Cargo.lock...")
    content = Path("Cargo.lock").read_text()
    now = datetime.datetime.now(datetime.timezone.utc)
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        matches = re.findall(r'\[\[package\]\]\s+name = "(.*?)"\s+version = "(.*?)"', content, re.DOTALL)
        for name, version in matches:
            tasks.append(executor.submit(check_package, "cargo", name, version, now))
        found_danger = False
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res and "[DANGER]" in res:
                print(res)
                found_danger = True
        if not found_danger: success("No 'young' Cargo packages found.")

def main():
    parser = argparse.ArgumentParser(description="7days Audit: Scan lockfiles for 'young' dependencies.")
    parser.add_argument("--npm", action="store_true")
    parser.add_argument("--pip", action="store_true")
    parser.add_argument("--pipx", action="store_true")
    parser.add_argument("--composer", action="store_true")
    parser.add_argument("--cargo", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not any([args.npm, args.pip, args.pipx, args.composer, args.cargo, args.all]):
        parser.print_help(); sys.exit(1)
    if args.npm or args.all: audit_npm()
    if args.pip or args.all: audit_python()
    if args.pipx or args.all: audit_pipx()
    if args.composer or args.all: audit_composer()
    if args.cargo or args.all: audit_cargo()

if __name__ == "__main__": main()
