#!/usr/bin/env python3
import os
import subprocess
import shutil
import re
import sys
import datetime
from pathlib import Path

# --- Configuration ---
COOLDOWN_DAYS = int(os.environ.get("SEVENDAYS_COOLDOWN", "7"))
MIN_NPM_VERSION = (11, 10, 0)
MIN_PNPM_VERSION = (10, 16, 0)
MIN_YARN_VERSION = (4, 10, 0)
MIN_BUN_VERSION = (1, 3, 0)
MIN_DENO_VERSION = (2, 0, 0)
MIN_PIP_VERSION = (26, 0, 0)
MIN_PIPX_VERSION = (1, 7, 0)
MIN_CONDA_VERSION = (26, 3, 0)
MIN_CARGO_VERSION = (1, 94, 0)

# Colors for terminal output
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

UPDATE_TEMPLATES = {
    "npm": "{path} install -g npm@latest",
    "pnpm": "{path} install -g pnpm@latest",
    "yarn": "{path} set version stable",
    "bun": "{path} upgrade",
    "deno": "{path} upgrade",
    "pip": "{python_path} -m pip install --upgrade pip",
    "pipx": "{python_path} -m pip install --upgrade pipx",
    "uv": "{path} self-update",
    "conda": "{path} update -n base -c defaults conda",
    "composer": "{path} self-update --preview",
    "cargo": "rustup update"
}

BREW_FORMULAS = {
    "npm": "node",
    "pnpm": "pnpm",
    "yarn": "yarn",
    "bun": "bun",
    "deno": "deno",
    "pip": "python",
    "pipx": "pipx",
    "uv": "uv",
    "cargo": "rust"
}

def log(msg, color=BLUE): print(f"{color}[*] {msg}{RESET}", flush=True)
def success(msg): print(f"{GREEN}[+] {msg}{RESET}", flush=True)
def info(msg): print(f"    {RESET}- {msg}", flush=True)
def warn(msg): print(f"{YELLOW}[!] {msg}{RESET}", flush=True)
def error(msg): print(f"{RED}[-] {msg}{RESET}", flush=True)

def parse_version(version_str):
    if not version_str: return (0, 0, 0)
    # Strip suffixes like -dev, -RC1 etc for comparison
    clean_v = version_str.split('-')[0]
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', clean_v)
    if match:
        return tuple(map(int, match.groups()))
    # Handle 2.10 (missing patch)
    match = re.search(r'(\d+)\.(\d+)', clean_v)
    if match:
        return (int(match.group(1)), int(match.group(2)), 0)
    return (0, 0, 0)

def find_binaries(name):
    paths = []
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        try:
            p = Path(path_dir) / name
            if p.exists() and os.access(p, os.X_OK):
                paths.append(str(p.absolute()))
        except: pass
    return sorted(list(set(paths)))

def get_brew_prefix():
    try:
        return subprocess.check_output(["brew", "--prefix"], stderr=subprocess.DEVNULL, text=True).strip()
    except: return None

def is_homebrew_managed(path, name=None):
    try:
        p = Path(path)
        resolved = str(p.resolve())
        # Check known path patterns for Homebrew/Linuxbrew installations
        if any(x in resolved for x in ["/Cellar/", "/opt/homebrew/", "/Caskroom/", "/.linuxbrew/"]):
            return True
        # Check against dynamic brew prefix, but be more specific to avoid false positives in /usr/local
        prefix = get_brew_prefix()
        if prefix:
            prefix_p = Path(prefix)
            if any(resolved.startswith(str(prefix_p / x) + "/") for x in ["Cellar", "Caskroom", "opt"]):
                return True
        # For npm, check if the node it uses is brew managed
        if name == "npm":
            node_path = shutil.which("node")
            if node_path and is_homebrew_managed(node_path):
                return True
    except: pass
    return False

def get_tool_version(path, name):
    # Mapping of tool names to their version output patterns
    patterns = {
        "npm": r'^(\d+\.\d+\.\d+)',
        "pnpm": r'^(\d+\.\d+\.\d+)',
        "yarn": r'^(\d+\.\d+\.\d+)',
        "bun": r'^(\d+\.\d+\.\d+)',
        "deno": r'deno\s+([\d.]+)',
        "pip": r'pip\s+([\d.]+)',
        "pipx": r'pipx\s+([\d.]+)',
        "uv": r'uv\s+([\d.]+)',
        "conda": r'conda\s+([\d.]+)',
        "composer": r'Composer\s+version\s+([^\s,]+)',
        "cargo": r'cargo\s+([\d.]+)'
    }
    
    # Try common version flags
    for flag in ["--version", "-V", "-v"]:
        try:
            res = subprocess.run([path, flag], capture_output=True, text=True, timeout=5)
            output = (res.stdout + res.stderr).strip()
            if not output: continue
            
            # Try specific pattern if available
            if name in patterns:
                match = re.search(patterns[name], output, re.IGNORECASE | re.MULTILINE)
                if match: return match.group(1).lstrip('v')
            
            # Generic fallback: look for something that looks like a version at the start of a line
            match = re.search(r'^v?(\d+\.\d+\.\d+(?:-[^\s,]+)?)', output, re.MULTILINE)
            if match: return match.group(1)
            
        except: continue
    return None

def version_too_low(name, v, min_v, path):
    min_str = ".".join(map(str, min_v))
    warn(f"{name}: Version v{v} at {path} is below the minimum requirement (v{min_str}+).")
    print(f"    {RED}ACTION REQUIRED:{RESET} Update {name} and run this script again.")
    
    cmd = None
    is_brew = is_homebrew_managed(path, name)
    resolved = str(Path(path).resolve())
    
    # If it's in a cellar but not the 'pipx' formula, it's likely a pip install in brew python
    if name == "pipx" and is_brew and "/Cellar/pipx/" not in resolved and "/opt/homebrew/opt/pipx/" not in resolved:
        is_brew = False

    if is_brew:
        formula = BREW_FORMULAS.get(name, name)
        if name == "pip":
            match = re.search(r'python@([\d.]+)', resolved)
            formula = f"python@{match.group(1)}" if match else "python"
        print(f"    {RESET}Note: {name} appears to be managed by Homebrew.")
        cmd = f"brew upgrade {formula}"
    elif name in ["pip", "pipx"]:
        tool_path = Path(path)
        python_path = None
        
        # 1. Try shebang first as it's the most definitive for scripts
        try:
            with open(tool_path, 'rb') as f:
                line = f.readline()
                if line.startswith(b'#!'):
                    parts = line[2:].strip().decode().split()
                    if parts:
                        p_cand = parts[0]
                        if "env" in p_cand and len(parts) > 1: p_cand = parts[1]
                        if os.path.exists(p_cand): python_path = p_cand
        except: pass

        # 2. Fallback to looking in the same directory
        if not python_path:
            for possible in [tool_path.name.replace(name, "python"), "python3", "python"]:
                p_check = tool_path.parent / possible
                if p_check.exists():
                    python_path = str(p_check.absolute())
                    break
        
        cmd = UPDATE_TEMPLATES[name].format(python_path=python_path or "python3")
    elif name == "cargo":
        rustup = shutil.which("rustup")
        cmd = f"{rustup} update" if rustup else "rustup update"
    else:
        cmd = UPDATE_TEMPLATES.get(name, "").format(path=path)

    if cmd:
        print(f"    {RESET}Suggestion: {BLUE}{cmd}{RESET}")
    
    if name == "npm":
        print(f"    {RESET}Troubleshooting: If version stays the same, run '{BLUE}hash -r{RESET}' (bash) or '{BLUE}rehash{RESET}' (zsh).")

def update_ini_file(path, section, key, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    section_header = f"[{section}]"
    new_lines = []
    current_section = None
    key_found = False
    changed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped
        
        if current_section == section_header:
            # Match "key=value" or "key = value" or "key: value"
            match = re.match(rf"^({re.escape(key)})\s*[:=]\s*(.*)$", stripped)
            if match:
                key_found = True
                current_val = match.group(2)
                if current_val != str(value):
                    new_lines.append(f"{key} = {value}")
                    changed = True
                    continue
        new_lines.append(line)

    if not key_found:
        section_idx = -1
        for i, line in enumerate(new_lines):
            if line.strip() == section_header:
                section_idx = i
                break
        
        if section_idx != -1:
            new_lines.insert(section_idx + 1, f"{key} = {value}")
        else:
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append("")
            new_lines.append(section_header)
            new_lines.append(f"{key} = {value}")
        changed = True

    if changed:
        path.write_text("\n".join(new_lines) + "\n")
    return changed

def update_file_idempotent(path, line, comment=None):
    path = Path(path)
    content = path.read_text() if path.exists() else ""
    key = line.split('=')[0].strip() if '=' in line else line.split(':')[0].strip()
    if key in content: return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        if comment: f.write(f"\n# {comment}\n")
        f.write(line + "\n")
    return True

def configure_npm_ecosystem():
    log("Checking Node.js/JS ecosystem...")
    for name, min_v, file, line in [
        ("npm", MIN_NPM_VERSION, Path.home() / ".npmrc", f"min-release-age={COOLDOWN_DAYS}"),
        ("pnpm", MIN_PNPM_VERSION, Path.home() / ".config" / "pnpm" / "rc", f"minimum-release-age={COOLDOWN_DAYS * 1440}"),
        ("yarn", MIN_YARN_VERSION, Path.home() / ".yarnrc.yml", f"npmMinimalAgeGate: \"{COOLDOWN_DAYS}d\"")
    ]:
        bins = find_binaries(name)
        if not bins: info(f"{name}: Binary not found in PATH."); continue
        for path in bins:
            v = get_tool_version(path, name)
            if v:
                if parse_version(v) >= min_v:
                    if update_file_idempotent(file, line, "7days"):
                        success(f"Configured {name} at {path} (v{v})")
                    else: info(f"{name}: Already configured at {file}")
                else: version_too_low(name, v, min_v, path)
            else: info(f"{name}: Could not verify version at {path}")

    for name, min_v in [("bun", MIN_BUN_VERSION), ("deno", MIN_DENO_VERSION)]:
        bins = find_binaries(name)
        if not bins: info(f"{name}: Binary not found in PATH."); continue
        for path in bins:
            v = get_tool_version(path, name)
            if v:
                if parse_version(v) >= min_v:
                    if name == "bun":
                        bunfig = Path.home() / ".bunfig.toml"
                        content = bunfig.read_text() if bunfig.exists() else ""
                        if "minimumReleaseAge" not in content:
                            if not bunfig.exists():
                                bunfig.write_text("[install]\n")
                                content = "[install]\n"
                            
                            with open(bunfig, "a") as f:
                                if "[install]" not in content:
                                    f.write("\n[install]\n")
                                f.write(f"minimumReleaseAge = {COOLDOWN_DAYS * 86400}\n")
                            success(f"Configured Bun at {path} (v{v})")
                        else: info(f"Bun: Already configured at {bunfig}")
                    else:
                        deno_json = Path.home() / ".deno.json"
                        if not deno_json.exists():
                            deno_json.write_text(f'{{\n  "minimumDependencyAge": "P{COOLDOWN_DAYS}D"\n}}\n')
                            success(f"Configured Deno at {path} (v{v})")
                        else: info(f"Deno: Already configured at {deno_json}")
                else: version_too_low(name, v, min_v, path)
            else: info(f"{name}: Could not verify version at {path}")

def configure_python_ecosystem():
    log("Checking Python ecosystem...")
    search_names = ["pip", "pip3"] + [f"pip3.{i}" for i in range(10, 16)]
    all_pips = []
    for name in search_names: all_pips.extend(find_binaries(name))
    if not all_pips: info("pip: No binaries found in PATH.")
    else:
        for path in sorted(list(set(all_pips))):
            v = get_tool_version(path, "pip")
            if v:
                if parse_version(v) >= MIN_PIP_VERSION:
                    now_minus_cooldown = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=COOLDOWN_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
                    if update_ini_file(Path.home() / ".config" / "pip" / "pip.conf", "global", "uploaded-prior-to", now_minus_cooldown):
                        success(f"Configured pip at {path} (with static gate {now_minus_cooldown})")
                    else: info(f"pip: Already configured in pip.conf for {path}")
                else: version_too_low("pip", v, MIN_PIP_VERSION, path)
            else: info(f"pip: Could not verify version at {path}")
    
    pipx_bins = find_binaries("pipx")
    if pipx_bins:
        for path in pipx_bins:
            v = get_tool_version(path, "pipx")
            if v:
                if parse_version(v) >= MIN_PIPX_VERSION:
                    success(f"Verified pipx at {path} (v{v})")
                else: version_too_low("pipx", v, MIN_PIPX_VERSION, path)
            else: info(f"pipx: Could not verify version at {path}")
    else: info("pipx: Not found in PATH.")

    uv_bins = find_binaries("uv")
    if uv_bins:
        for path in uv_bins: success(f"Found uv at {path}. Env vars applied.")
    else: info("uv: Not found in PATH.")

    conda_bins = find_binaries("conda")
    if conda_bins:
        for path in conda_bins:
            v = get_tool_version(path, "conda")
            if v:
                if parse_version(v) >= MIN_CONDA_VERSION:
                    subprocess.run([path, "config", "--set", "cooldown", f"{COOLDOWN_DAYS}d"], check=True, capture_output=True)
                    success(f"Configured Conda at {path}")
                else: version_too_low("conda", v, MIN_CONDA_VERSION, path)
            else: info(f"Conda: Could not verify version at {path}")
    else: info("Conda: Binary not found in PATH.")

    pip_dynamic = 'PIP_UPLOADED_PRIOR_TO=$(python3 -c "import datetime; print((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=' + str(COOLDOWN_DAYS) + ')).strftime(\'%Y-%m-%dT%H:%M:%SZ\'))")'
    uv_env = f'UV_EXCLUDE_NEWER="{COOLDOWN_DAYS} days ago"'
    pip_dynamic_line = f'export {pip_dynamic}'
    uv_env_line = f'export {uv_env}'
    profiles = [p for p in [Path.home() / ".zshrc", Path.home() / ".bashrc", Path.home() / ".bash_profile"] if p.exists()]
    
    for p in profiles:
        content = p.read_text()
        new_content = content
        added = False
        
        # Aggressively replace static/invalid PIP_UPLOADED_PRIOR_TO
        if "PIP_UPLOADED_PRIOR_TO" in content:
            # Replace lines like 'export PIP_UPLOADED_PRIOR_TO=P7D' or similar
            new_content = re.sub(r'^#? ?export PIP_UPLOADED_PRIOR_TO=.*$', pip_dynamic_line, new_content, flags=re.MULTILINE)
            if new_content != content:
                added = True
        else:
            new_content += f"\n# 7days\n{pip_dynamic_line}\n"
            added = True
            
        if "UV_EXCLUDE_NEWER" not in new_content:
            if "# 7days" not in new_content:
                new_content += f"\n# 7days\n{uv_env_line}\n"
            else:
                new_content = new_content.replace("# 7days", f"# 7days\n{uv_env_line}")
            added = True

        if added:
            p.write_text(new_content)
            success(f"Configured rolling gate variables in {p.name}")
        else:
            info(f"Shell Profiles: {p.name} already configured")

def configure_others():
    log("Checking other package managers...")
    for name, min_v in [("cargo", MIN_CARGO_VERSION)]:
        bins = find_binaries(name)
        if not bins: info(f"{name}: Binary not found in PATH."); continue
        for path in bins:
            v = get_tool_version(path, name)
            if v:
                if parse_version(v) >= min_v:
                    success(f"Verified Cargo at {path} (v{v}): Natively protected via crates.io quarantine.")
                else: version_too_low(name, v, min_v, path)
            else: info(f"{name}: Could not verify version at {path}")

    if find_binaries("composer"): warn("Composer: Does not natively support age gates. Use 'audit_7days.py --composer' to scan.")
    if find_binaries("bundle"): warn("Bundler: Requires manual mirror: https://beta.gem.coop")
    else: info("Bundler: Binary not found in PATH.")
    if find_binaries("brew"): warn("Homebrew: Recommended to run 'brew update && brew audit' periodically. See https://github.com/Homebrew/brew/issues/21129 for detail on why cool down is not supported by Homebrew")
    else: info("Homebrew: Binary not found in PATH.")

def main():
    print(f"\n{BLUE}=== 7days: Dependency Release Age Gate Setup ==={RESET}\n", flush=True)
    configure_npm_ecosystem()
    configure_python_ecosystem()
    configure_others()
    print(f"\n{GREEN}Configuration complete. Please restart your shell to apply changes.{RESET}")
    print(f"{YELLOW}If any items were skipped due to version requirements, please update them and run this script again.{RESET}\n", flush=True)

if __name__ == "__main__": main()
