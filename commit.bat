@echo off
cd /d c:\Users\owner\Desktop\Telegram
git add -A
git commit -m "Fix database initialization blocking and improve dashboard UI

- Made PowerUpgradesService initialization lazy to not block startup
- Added background task for persona initialization
- Improved dashboard with gradient styling, icons, and animations
- Enhanced CSS with better color scheme and animations
- Better error handling when database unavailable

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
