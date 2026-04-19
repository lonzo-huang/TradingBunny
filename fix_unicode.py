#!/usr/bin/env python3
"""Fix Unicode emoji characters in Python files for Windows compatibility."""

import os
import re

# Map of emoji to ASCII replacements
EMOJI_MAP = {
    '🚀': '[START]',
    '💾': '[PERSIST]',
    '⚠️': '[WARN]',
    '✅': '[OK]',
    '❌': '[ERROR]',
    '📊': '[STATS]',
    '📅': '[SCHED]',
    '🔁': '[RETRY]',
    '🔄': '[REFRESH]',
    '💰': '[PNL]',
    '⏰': '[TIMER]',
    '⏱️': '[TIME]',
    '📡': '[SERVER]',
    '🛑': '[STOP]',
    '✓': '[OK]',
    '🎯': '[TARGET]',
    '🐳': '[PDE]',
    '💡': '[HINT]',
    '👋': '[BYE]',
    '⚙️': '[CONFIG]',
    '📈': '[UP]',
    '📉': '[DOWN]',
    '🔴': '[RED]',
    '🟢': '[GREEN]',
    '🟡': '[YELLOW]',
}

def fix_file(filepath):
    """Replace emojis in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for emoji, replacement in EMOJI_MAP.items():
        content = content.replace(emoji, replacement)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    return False

def main():
    strategies_dir = "strategies/pde"
    files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')]
    
    fixed_count = 0
    for filename in files:
        filepath = os.path.join(strategies_dir, filename)
        if fix_file(filepath):
            fixed_count += 1
    
    # Also fix utils files that might have emoji
    utils_files = [
        "utils/live_stream_server.py",
        "utils/grafana_live_pusher.py",
        "utils/composite_pusher.py",
    ]
    
    for filepath in utils_files:
        if os.path.exists(filepath):
            if fix_file(filepath):
                fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()
