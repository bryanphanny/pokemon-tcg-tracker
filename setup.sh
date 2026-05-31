#!/bin/bash
set -e

echo "=== Installing system dependencies ==="
sudo apt install -y python3.11-venv

echo "=== Creating Python virtual environment ==="
python3 -m venv venv

echo "=== Installing Python dependencies ==="
venv/bin/pip install -r requirements.txt

echo "=== Installing systemd service ==="
# Resolve the actual install directory and inject it into the service file
INSTALL_DIR="$(pwd)"
sed "s|/root/pokemon-tcg-tracker|$INSTALL_DIR|g" pokemon-bot.service \
    | sudo tee /etc/systemd/system/pokemon-bot.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable pokemon-bot

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next: create your config.yaml with your Discord webhook URL:"
echo "  nano config.yaml"
echo ""
echo "Then start the bot:"
echo "  sudo systemctl start pokemon-bot"
echo ""
echo "Watch live logs:"
echo "  journalctl -u pokemon-bot -f"
