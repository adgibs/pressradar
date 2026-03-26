#!/bin/bash
# PressRadar quick push script
# Run from anywhere on your Mac: bash ~/path/to/pressradar/push.sh

cd "$(dirname "$0")" || exit 1

echo "📡 PressRadar — Push to GitHub"
echo "================================"
echo "Branch: $(git branch --show-current)"
echo ""

# Show what will be pushed
UNPUSHED=$(git log --oneline origin/main..HEAD 2>/dev/null)
if [ -z "$UNPUSHED" ]; then
  echo "✅ Nothing to push — already up to date."
  exit 0
fi

echo "Commits to push:"
echo "$UNPUSHED"
echo ""

# Pull first to avoid conflicts with auto-update bot
echo "⬇️  Pulling latest..."
git stash --quiet 2>/dev/null
git pull --rebase --quiet 2>&1
PULL_EXIT=$?
git stash pop --quiet 2>/dev/null

if [ $PULL_EXIT -ne 0 ]; then
  echo "❌ Pull failed — resolve conflicts manually."
  exit 1
fi

# Push
echo "⬆️  Pushing..."
git push 2>&1

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Pushed successfully!"
  echo "🌐 Site will update at: https://adgibs.github.io/pressradar"
else
  echo ""
  echo "❌ Push failed. Check output above."
  exit 1
fi
