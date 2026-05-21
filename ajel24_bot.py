name: Run Ajel24 Bot

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install playwright requests -q
          playwright install chromium
          playwright install-deps chromium

      - name: Run bot
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python ajel24_bot.py --once

      - name: Commit and push
        run: |
          git config --global user.name "github-actions"
          git config --global user.email "[email protected]"
          git add posters/ ajel24_history.json
          git diff --cached --quiet || git commit -m "تحديث الأخبار"
          git push --force origin main
