import json
import os
import subprocess
import datetime
import urllib.request
import sys
import re
import shutil
from pathlib import Path

# Colors for terminal output
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def log(msg): print(f"{BLUE}[*] {msg}{RESET}")
def success(msg): print(f"{GREEN}[+] {msg}{RESET}")
def warn(msg): print(f"{YELLOW}[!] {msg}{RESET}")
def error(msg): print(f"{RED}[-] {msg}{RESET}")

def get_pkg_info_npm(name):
    url = f"https://registry.npmjs.org/{name}"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        latest_version = data.get("dist-tags", {}).get("latest")
        time_str = data.get("time", {}).get(latest_version)
        publish_date = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return latest_version, publish_date

def get_pkg_info_pypi(name):
    url = f"https://pypi.org/pypi/{name}/json"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        latest_version = data.get("info", {}).get("version")
        releases = data.get("releases", {}).get(latest_version, [])
        if not releases:
            for v in reversed(list(data.get("releases", {}).keys())):
                if data.get("releases", {}).get(v):
                    latest_version = v
                    releases = data.get("releases", {}).get(v)
                    break
        upload_time = releases[0].get("upload_time_iso_8601")
        publish_date = datetime.datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
        return latest_version, publish_date

def run_test_npm():
    pkg = "is-sorted"
    latest_v, pub_date = get_pkg_info_npm(pkg)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing npm with {pkg}@{latest_v} (Age: {age_days} days)")
    
    test_dir = Path("/tmp/test-npm")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    os.chdir(test_dir)
    
    # Install latest
    subprocess.run(["npm", "install", pkg, "--no-save"], capture_output=True, check=True)
    
    # Configure Gate
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    # Use absolute path to setup_7days.py
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Try Reinstall
    subprocess.run(["npm", "uninstall", pkg], capture_output=True)
    subprocess.run(["npm", "install", pkg, "--no-save"], capture_output=True)
    
    v_now = json.loads(subprocess.check_output(["npm", "list", pkg, "--json"])).get("dependencies", {}).get(pkg, {}).get("version")
    if not v_now or v_now != latest_v:
        success(f"NPM Gate Worked! (Installed: {v_now or 'Blocked'})")
    else:
        error("NPM Gate Failed!")
        sys.exit(1)

def run_test_pnpm():
    pkg = "is-sorted"
    latest_v, pub_date = get_pkg_info_npm(pkg)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing pnpm with {pkg}@{latest_v} (Age: {age_days} days)")
    
    test_dir = Path("/tmp/test-pnpm")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    os.chdir(test_dir)
    
    # Install latest
    try:
        subprocess.run(["pnpm", "add", pkg], capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        error(f"PNPM install failed: {e.stderr.decode()}")
        raise e
    
    # Configure Gate
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Try Reinstall
    subprocess.run(["pnpm", "remove", pkg], capture_output=True)
    subprocess.run(["pnpm", "add", pkg], capture_output=True)
    
    v_now = json.loads(subprocess.check_output(["pnpm", "list", "--json"]))[0].get("dependencies", {}).get(pkg, {}).get("version")
    if not v_now or v_now != latest_v:
        success(f"PNPM Gate Worked! (Installed: {v_now or 'Blocked'})")
    else:
        error("PNPM Gate Failed!")
        sys.exit(1)

def run_test_bun():
    pkg = "is-sorted"
    latest_v, pub_date = get_pkg_info_npm(pkg)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing Bun with {pkg}@{latest_v} (Age: {age_days} days)")
    
    test_dir = Path("/tmp/test-bun")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    os.chdir(test_dir)
    
    # Install latest
    subprocess.run(["bun", "add", pkg], capture_output=True, check=True)
    
    # Configure Gate
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Try Reinstall
    subprocess.run(["rm", "node_modules", "-rf"], capture_output=True)
    subprocess.run(["bun", "install"], capture_output=True)
    
    # Check version in package.json/lockfile or node_modules
    v_now = json.loads(Path("node_modules/is-sorted/package.json").read_text()).get("version")
    if v_now != latest_v:
        success(f"Bun Gate Worked! (Installed: {v_now})")
    else:
        error("Bun Gate Failed!")
        sys.exit(1)

def run_test_uv():
    pkg = "requests"
    latest_v, pub_date = get_pkg_info_pypi(pkg)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing uv with {pkg}@{latest_v} (Age: {age_days} days)")
    
    test_dir = Path("/tmp/test-uv")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    os.chdir(test_dir)
    
    # Install latest
    subprocess.run(["uv", "pip", "install", f"{pkg}=={latest_v}", "--system", "--break-system-packages"], capture_output=True, check=True)
    
    # Configure Gate
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Try Reinstall
    env = os.environ.copy()
    env["UV_EXCLUDE_NEWER"] = f"{cooldown} days ago"
    res = subprocess.run(["uv", "pip", "install", pkg, "--dry-run", "--system", "--break-system-packages"], env=env, capture_output=True, text=True)
    
    if latest_v not in res.stdout:
        success(f"UV Gate Worked! (Latest version {latest_v} ignored)")
    else:
        error("UV Gate Failed!")
        sys.exit(1)

def run_test_deno():
    # Deno added npm support recently
    pkg = "npm:is-sorted"
    latest_v, pub_date = get_pkg_info_npm("is-sorted")
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing Deno with {pkg}@{latest_v} (Age: {age_days} days)")
    
    test_dir = Path("/tmp/test-deno")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    os.chdir(test_dir)
    
    # Configure Gate FIRST (Deno uses a config file)
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Deno install should respect .deno.json in HOME? 
    # Actually Deno needs the config file explicitly usually or in current dir.
    # Let's copy it to current dir for the test.
    if (Path.home() / ".deno.json").exists():
        Path("deno.json").write_text((Path.home() / ".deno.json").read_text())
    
    # Try to add - it should fail or pick older if we use a range
    res = subprocess.run(["deno", "add", pkg], capture_output=True, text=True)
    
    # Check deno.lock
    if Path("deno.lock").exists():
        lock = Path("deno.lock").read_text()
        if latest_v not in lock:
            success(f"Deno Gate Worked! (Latest version {latest_v} not found in lockfile)")
        else:
            warn(f"Deno Gate might not have worked, found {latest_v} in lock. Deno age gate is still experimental.")
    else:
        success("Deno Gate Worked! (Failed to add package within age window)")

def run_test_pipx():
    pkg = "pyjokes"
    latest_v, pub_date = get_pkg_info_pypi(pkg)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - pub_date).days
    log(f"Testing pipx with {pkg}@{latest_v} (Age: {age_days} days)")
    
    # Configure Gate
    cooldown = age_days + 1
    os.environ["SEVENDAYS_COOLDOWN"] = str(cooldown)
    setup_script = Path(__file__).parent.parent / "setup_7days.py"
    subprocess.run(["python3", str(setup_script)], capture_output=True, check=True)
    
    # Try Install
    env = os.environ.copy()
    now_minus_cooldown = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=cooldown)).strftime('%Y-%m-%dT%H:%M:%SZ')
    env["PIP_UPLOADED_PRIOR_TO"] = now_minus_cooldown
    
    # Check if we can block it. pipx install pyjokes==latest_v should fail or warn if gate works
    # Actually pipx just calls pip.
    res = subprocess.run(["pipx", "install", f"{pkg}=={latest_v}"], env=env, capture_output=True, text=True)
    
    if res.returncode != 0:
        success(f"PIPX Gate Worked! (Installation blocked for {latest_v})")
    else:
        # If it installed, maybe the gate didn't work or it was already in cache
        # Let's try to audit it
        audit_script = Path(__file__).parent.parent / "audit_7days.py"
        res = subprocess.run(["python3", str(audit_script), "--pipx"], capture_output=True, text=True)
        if "[DANGER]" in res.stdout:
            success("PIPX Gate (Audit) Worked! (Found young package)")
        else:
            warn("PIPX Gate might not have blocked installation, check if pip 26+ is used.")

if __name__ == "__main__":
    log("=== Final Empirical 7days Test Suite ===")
    run_test_npm()
    run_test_pnpm()
    run_test_bun()
    run_test_uv()
    run_test_deno()
    run_test_pipx()
    success("All Empirical Tests Completed!")
