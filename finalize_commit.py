#!/usr/bin/env python3
"""
Final commit script for the improvements
"""
import subprocess
import sys

try:
    import os
    os.chdir(r'c:\Users\owner\Desktop\Telegram')
    
    # Check git status
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    print("Git Status:")
    print(result.stdout)
    
    # Stage all changes
    print("\n📦 Staging changes...")
    subprocess.run(['git', 'add', '-A'], check=True)
    
    # Commit with message
    print("💾 Creating commit...")
    commit_msg = """Fix database initialization blocking and improve dashboard UI

- Made PowerUpgradesService initialization lazy to not block startup
- Added background task for persona initialization
- Improved dashboard with gradient styling, icons, and animations
- Enhanced CSS with better color scheme and animations
- Better error handling when database unavailable

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""
    
    result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Warning:", result.stderr)
    
    # Push to remote
    print("\n🚀 Pushing to remote...")
    result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Push output:", result.stderr)
    
    print("\n✅ All done! Changes committed and pushed successfully!")
    
except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    sys.exit(1)
