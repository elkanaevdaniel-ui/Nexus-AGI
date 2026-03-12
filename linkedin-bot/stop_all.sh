#!/bin/bash
echo "Stopping all LinkedIn Bot processes..."
pkill -f 'python3 run.py' 2>/dev/null && echo "  Bot stopped"
pkill -f 'dashboard/app.py' 2>/dev/null && echo "  Dashboard stopped"
pkill -f 'watchdog.py' 2>/dev/null && echo "  Watchdog stopped"
pkill -f 'nokey@localhost.run' 2>/dev/null && echo "  Tunnel stopped"
echo "Done. Run 'bash launch_all.sh' to start again."
