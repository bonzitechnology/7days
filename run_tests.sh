#!/bin/bash
set -e

echo "[*] Building Docker test environment..."
docker build -t 7days-test -f tests/Dockerfile .

echo "[*] Running Integration Tests (Unittest)..."
docker run --rm 7days-test python3 tests/test_7days_docker.py
docker run --rm 7days-test python3 tests/test_brew_detection.py
docker run --rm 7days-test python3 tests/test_homebrew_logic.py

echo "[*] Running Empirical Tests (Live)..."
docker run --rm 7days-test python3 tests/empirical_test.py
