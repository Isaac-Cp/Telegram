#!/usr/bin/env python3
import subprocess
import os

os.chdir(r'c:\Users\owner\Desktop\Telegram')

# Stage all changes
subprocess.run(['git', 'add', '-A'], check=True)

# Commit with message
commit_msg = """Fix database initialization blocking and improve dashboard UI

- Made PowerUpgradesService initialization lazy to not block startup
- Added background task for persona initialization
- Improved dashboard with gradient styling, icons, and animations
- Enhanced CSS with better color scheme and animations
- Better error handling when database unavailable

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""

subprocess.run(['git', 'commit', '-m', commit_msg], check=True)

# Push to remote
subprocess.run(['git', 'push', 'origin', 'main'], check=True)

print("✅ Changes committed and pushed successfully!")
