#!/bin/bash
# Run pookiespetcare locally.
# Port 5000 is blocked on macOS by AirPlay Receiver — using 5100 instead.
# To disable AirPlay: System Settings > General > AirDrop & Handoff > AirPlay Receiver (off)
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
PORT=5100 python app.py
