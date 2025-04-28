from PIL import Image, TiffImagePlugin
import numpy as np
import os
import json
from utils import sanitize_ascii_name, parse_datetime_from_filename
from datetime import datetime

def create_image_description_ascii(world_name, world_id, players):
    safe_world = sanitize_ascii_name(world_name or 'Unknown')
    desc = f"World: {safe_world}\nURL: https://vrchat.com/home/world/{world_id}\n\nPlayers:\n"
    for p in players:
        try:
            clean_name = sanitize_ascii_name(p["name"])
            uid = p["id"]
            desc += f"- {clean_name}\n  https://vrchat.com/home/user/usr_{uid}\n"
        except:
            continue
    return desc.strip()

def create_utf8_metadata(world_name, world_id, players):
    data = {
        "world_name": world_name,
        "world_url": f"https://vrchat.com/home/world/{world_id}",
        "players": players
    }
    return data

def get_monthly_output_path(base_output_dir, original_png_path):
    # 例: original_png_path = .../VRChat/2025-04/VRChat_2025-04-17_21-00-00.png
    parent = os.path.basename(os.path.dirname(original_png_path))  # "2025-04"
    return os.path.join(base_output_dir, parent)

def convert_png_to_tiff_with_metadata(png_path, base_output_dir, log_data=None, delete_png=False):
    dt = parse_datetime_from_filename(os.path.basename(png_path))
    filename_base = os.path.splitext(os.path.basename(png_path))[0]
    flug ='2048x1440'

    if flug in filename_base : delete_png = False

    monthly_output_dir = get_monthly_output_path(base_output_dir, png_path)
    os.makedirs(monthly_output_dir, exist_ok=True)

    tiff_path = os.path.join(monthly_output_dir, filename_base + ".tiff")
    img = Image.open(png_path).convert("RGB")

    meta = TiffImagePlugin.ImageFileDirectory_v2()
    meta[306] = dt.strftime("%Y:%m:%d %H:%M:%S")

    if log_data:
        world_id = log_data["world_instance"].split(":")[0] if log_data["world_instance"] else "unknown"
        metadata = create_utf8_metadata(log_data["world_name"], world_id, log_data["players"])
        metadata["datetime"] = dt.strftime("%Y-%m-%dT%H:%M:%S")

        json_dir = os.path.join(monthly_output_dir, "meta")
        os.makedirs(json_dir, exist_ok=True)
        json_path = os.path.join(json_dir, filename_base + ".json")

        meta[270] = json_path

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    img.save(tiff_path, format="TIFF", tiffinfo=meta)

    if delete_png:
        os.remove(png_path)

    print(f"✓ {filename_base}.tiff に変換完了" + ("（+ meta JSON）" if log_data else "（ログなし・日時のみ）"))
