# 7days: Dependency Release Age Enforcement

`7days` is a utility for enforcing a 7-day minimum release age on system package managers. It is designed to mitigate supply chain risks by ensuring dependencies have been available in public registries for a sufficient period to allow for community audit or automated retraction.

## Functional Specification
The utility enforces a delay between the timestamp of a package release and its availability for local installation. This period allows for the detection and removal of malicious or broken releases before they are ingested into a development or production environment.

## Supported Package Managers

| Manager | Configuration Key | Minimum Version | Configuration Path/Method |
| :--- | :--- | :--- | :--- |
| **npm** | `min-release-age` | v11.10.0+ | `~/.npmrc` |
| **pnpm** | `minimum-release-age` | v10.16.0+ | `pnpm config` (minutes) |
| **Yarn** | `npmMinimalAgeGate` | v4.10.0+ | `.yarnrc.yml` |
| **Bun** | `minimumReleaseAge` | v1.3.0+ | `bunfig.toml` (seconds) |
| **Deno** | `minimumDependencyAge`| v2.0.0+ | `.deno.json` |
| **pip** | `uploaded-prior-to` | v26.0.0+ | `pip.conf` & Environment Variable |
| **pipx** | N/A | v1.7.0+ | Inherits pip/uv environment |
| **uv** | `--exclude-newer` | v0.5.0+ | `UV_EXCLUDE_NEWER` |
| **Conda** | `cooldown` | v26.3.0+ | `conda config` |
| **Cargo** | native | v1.94.0+ | crates.io quarantine status |
| **Composer** | audit-only | N/A | `audit_7days.py` scan |
| **Ruby** | mirror | N/A | `source "https://beta.gem.coop"` |

## Intended Usage
This utility is intended for deployment on development and personal workstations. For production environments or corporate infrastructure, the use of managed internal artifact repositories (e.g., Artifactory, Nexus) with established auditing and promotion workflows is recommended.

## Components

### Configuration Script (`setup_7days.py`)
Automates the configuration of local package managers. For tools requiring absolute timestamps (e.g., `pip`), it injects dynamic date calculations into shell profiles (`.bashrc`, `.zshrc`) to maintain a rolling enforcement window.
```bash
python3 setup_7days.py
```

### Audit Tool (`audit_7days.py`)
Scans project lockfiles and queries registry APIs to identify dependencies released within the enforcement window.
```bash
# Ecosystem-specific scan
python3 audit_7days.py --npm --pip --pipx --cargo --composer

# Comprehensive scan
python3 audit_7days.py --all
```
**Supported Lockfiles:** `package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `requirements.txt`, `composer.lock`, `Cargo.lock`. (Note: `pipx` uses system list).

## Verification Suite
The project includes a Docker-based environment for verifying enforcement logic across supported ecosystems.

### Automated Suite
A single script is provided to build the environment and run all tests (Unittest, Integration, and Empirical).
```bash
bash tests/run_tests.sh
```

### Manual Execution
*   **Environment Setup**
    ```bash
    docker build -t 7days-test -f tests/Dockerfile .
    ```
*   **Unit Tests:** Verifies internal logic using mocked dependencies.
    ```bash
    docker run --rm 7days-test python3 tests/test_setup_7days.py
    ```
*   **Structural Integration:** Verifies correct configuration file generation and placement.
    ```bash
    docker run --rm 7days-test python3 tests/test_7days_docker.py
    ```
*   **Empirical Verification:** Verifies end-to-end enforcement by attempting to install packages with specific release ages and confirming the expected block or version downgrade behavior.
    ```bash
    docker run --rm 7days-test python3 tests/empirical_test.py
    ```

## Known Limitations

The following package managers do not currently support native release age enforcement:

*   **Composer:** Not natively supported. The community has requested this feature, but it has not yet been implemented. See [Composer Issue #12633](https://github.com/composer/composer/issues/12633) (Status: Not supported as of 2026-04-05). Use `audit_7days.py` for post-install verification.
*   **Homebrew:** Support is not planned by the maintainers. See [Homebrew Issue #21129](https://github.com/Homebrew/brew/issues/21129). It is recommended to use `brew audit` or periodic manual reviews.

## Manual Overrides
To bypass enforcement for specific operations (e.g., urgent security patching):
*   **npm/Bun:** `--min-release-age 0`
*   **pip:** `--uploaded-prior-to ""`
*   **uv:** `--exclude-newer ""`
*   **Yarn:** `--ignore-age-gate`

## Credits

Developed by kronicd & swarley

## Contributions

Contributions are welcome, if you are adding a new package manager then please ensure that your pull request includes tests as well.