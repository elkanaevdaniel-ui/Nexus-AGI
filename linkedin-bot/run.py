
#!/usr/bin/env python3
"""LinkedIn AI & Cybersecurity Post Bot"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import run_bot

if __name__ == '__main__':
    print("Starting LinkedIn AI Bot...")
    run_bot()
