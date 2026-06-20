#!/usr/bin/env bash
# InsureVerify — one-time setup script (Linux / macOS)
set -e

echo "=================================================="
echo " InsureVerify — Setup (Linux/macOS)"
echo "=================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "[1/4] Setting up backend Python virtual environment..."
cd "$ROOT_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt
echo "Backend dependencies installed."

echo ""
echo "[2/4] Checking for Ollama..."
if command -v ollama &> /dev/null; then
    echo "Ollama found. Pulling required models (llava, llama3) if not already present..."
    ollama pull llava || echo "Could not pull llava automatically — run 'ollama pull llava' manually."
    ollama pull llama3 || echo "Could not pull llama3 automatically — run 'ollama pull llama3' manually."
else
    echo "Ollama not found on this machine."
    echo "InsureVerify will still run using classical computer-vision fallbacks,"
    echo "but for full VLM/LLM-powered analysis, install Ollama from https://ollama.com"
    echo "then run: ollama pull llava && ollama pull llama3"
fi

echo ""
echo "[3/4] Installing frontend dependencies..."
cd "$ROOT_DIR/frontend"
npm install

echo ""
echo "[4/4] Setup complete."
echo "=================================================="
echo "To run the platform, open two terminals:"
echo "  Terminal 1: ./run_backend.sh"
echo "  Terminal 2: ./run_frontend.sh"
echo "Then open http://localhost:5173 in your browser."
echo "=================================================="
