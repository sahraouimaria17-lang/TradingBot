import os, io, re, json, time, asyncio, logging, threading, functools
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests, ccxt, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackQueryHandler)

def _e(k, d=""): return (os.getenv(k, d) or d).strip()
def _int(k, d=0):
    try: return int(_e(k, str(d)))
    except Exception: return d
def _chat(v):
    v = (v or "").strip()
    if not v: return None
    return int(v) if re.fullmatch(r"-?\d+", v) else v

BOT_TOKEN = _e("BOT_TOKEN")
CHANNEL_ID = _chat(_e("CHANNEL_ID"))
VIP_CHANNEL_ID = _chat(_e("VIP_CHANNEL_ID"))
ADMIN_ID = _int("ADMIN_ID", 7002618091)
GIST_ID = _e("GIST_ID")
GITHUB_TOKEN = _e("GITHUB_TOKEN")
CONTACT_LINK = _e("CONTACT_LINK", "@rym_rima1")
VIP_LINK = _e("VIP_LINK", "")
PAYMENT_INFO = _e("PAYMENT_INFO", "Binance Pay: 905142395")
PROTECT = _e("PROTECT_CONTENT", "1") == "1"
