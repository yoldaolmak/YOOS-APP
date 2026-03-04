#!/bin/sh
umask 007
export PYTHONUNBUFFERED=1
exec /home/ai/venv/bin/python /home/ai/clawdbot/clawdbot.py "$@"
