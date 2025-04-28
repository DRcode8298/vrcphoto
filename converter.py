from PIL import Image, PngImagePlugin
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
    parent = os.path.basename(os.path.dirname(original_png_path))  # "2025-04"
    return os.path.join(base_output_dir, parent)

def convert_png_with_metadata(png_path, base_output_dir, log_data=None, delete_png=False, save_as_avif=False):
    dt = parse_datetime_from_filename(os.path.basename(png_path))
    filename_base = os.path.splitext(os.path.basename(png_path))[0]
    flug = '2048x1440'

    if flug in filename_base:
        delete_png = False

    monthly_output_dir = get_monthly_output_path(base_output_dir, png_path)
    os.makedirs(monthly_output_dir, exist_ok=True)

    output_ext = ".avif" if save_as_avif else ".png"
    output_path = os.path.join(monthly_output_dir, filename_base + output_ext)

    img = Image.open(png_path).convert("RGB")

    # メタ情報設定（PNG用）
    meta = PngImagePlugin.PngInfo()
    meta.add_text("DateTimeOriginal", dt.strftime("%Y:%m:%d %H:%M:%S"))

    if log_data:
        world_id = log_data["world_instance"].split(":")[0] if log_data["world_instance"] else "unknown"
        metadata = create_utf8_metadata(log_data["world_name"], world_id, log_data["players"])
        metadata["datetime"] = dt.strftime("%Y-%m-%dT%H:%M:%S")

        # 保存するJSONパス
        json_dir = os.path.join(monthly_output_dir, "meta")
        os.makedirs(json_dir, exist_ok=True)
        json_path = os.path.join(json_dir, filename_base + ".json")

        # メタ情報にも軽く埋め込む
        meta.add_text("WorldName", log_data["world_name"] or "Unknown")
        meta.add_text("MetaJsonPath", json_path)

        # JSONファイルとして保存
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 保存処理
    if save_as_avif:
        img.save(output_path, format="AVIF")
    else:
        img.save(output_path, format="PNG", pnginfo=meta)

    if delete_png:
        os.remove(png_path)

    print(f"✓ {filename_base + output_ext} に変換完了" + ("（+ meta JSON）" if log_data else "（ログなし・日時のみ）"))
