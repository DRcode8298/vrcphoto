import unicodedata
import re
from datetime import datetime

def sanitize_ascii_name(name: str) -> str:
    """日本語などの非ASCII文字を除去し、半角化したASCII文字列に整形"""
    normalized = unicodedata.normalize('NFKC', name)
    ascii_only = ''.join(c for c in normalized if c.isascii())
    cleaned = re.sub(r'[^A-Za-z0-9 _\-]', '', ascii_only)
    return cleaned

def parse_datetime_from_filename(filename: str) -> datetime:
    """ファイル名から 'YYYY-MM-DD_HH-MM-SS' 形式の日時を抽出"""
    match = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})', filename)
    if match:
        dt_str = match.group(1) + ' ' + match.group(2).replace('-', ':')
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.now()
    return datetime.now()

def is_png_file(filename):
    return filename.lower().endswith(".png")
