#!/bin/zsh
cd /Users/kohei/Documents/41_Program2/203_lifeplannApp_8203_no_CSS
git add .
if ! git diff --cached --quiet; then
  git commit -m "Auto commit: $(date '+%Y-%m-%d %H:%M:%S')"
  git push
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto push executed" >> ~/auto_git_push.log 