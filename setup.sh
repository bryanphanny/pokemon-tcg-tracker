#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip3 install -r requirements.txt

echo "=== Installing systemd service ==="
sudo cp pokemon-bot.service /etc/systemd/system/
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
