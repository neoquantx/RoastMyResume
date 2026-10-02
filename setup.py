"""
setup.py — One-command setup for RoastMyResume
Run: python setup.py
"""

import subprocess
import sys
import os
import platform


def run(cmd, desc=""):
    print(f"\n{'─'*50}")
    print(f"▶ {desc or cmd}")
    print(f"{'─'*50}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def check_ollama():
    result = subprocess.run("ollama --version", shell=True, capture_output=True)
    return result.returncode == 0


def main():
    print("""
╔══════════════════════════════════════════════╗
║        🔥 RoastMyResume Setup               ║
║   Open-Source AI Resume Coach               ║
║   100% Local · Free · Private               ║
╚══════════════════════════════════════════════╝
    """)

    # 1. Install Python deps
    ok = run(f"{sys.executable} -m pip install -r requirements.txt", "Installing Python dependencies...")
    if not ok:
        print("❌ Pip install failed. Try: pip install -r requirements.txt manually")
        sys.exit(1)

    # 2. Check / install Ollama
    print("\n" + "─"*50)
    print("▶ Checking Ollama...")
    if check_ollama():
        print("✅ Ollama already installed!")
    else:
        print("⚠️  Ollama not found. Installing...")
        system = platform.system().lower()
        if system == "darwin":
            run("brew install ollama", "Installing Ollama via Homebrew...")
        elif system == "linux":
            run("curl -fsSL https://ollama.com/install.sh | sh", "Installing Ollama via script...")
        else:
            print("⚠️  Please install Ollama manually from https://ollama.com/download")
            print("   Then run: ollama pull llama3.2")

    # 3. Pull Llama 3.2 model
    print("\n" + "─"*50)
    print("▶ Pulling Llama 3.2 model (this runs locally, ~2GB download)...")
    print("  You can also use: mistral, gemma2, phi3 — all open-source!")
    run("ollama pull llama3.2", "Downloading Llama 3.2...")

    print("""
╔══════════════════════════════════════════════╗
║              ✅ Setup Complete!             ║
╠══════════════════════════════════════════════╣
║                                              ║
║  1. Start Ollama:  ollama serve              ║
║  2. Run the app:   streamlit run app.py      ║
║                                              ║
║  WHY OPEN-SOURCE?                            ║
║  ✅ Runs offline — no internet needed        ║
║  ✅ Resume never leaves your laptop          ║
║  ✅ Swap models: llama3.2, mistral, gemma2   ║
║  ✅ Free forever — no API bills              ║
║                                              ║
╚══════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
