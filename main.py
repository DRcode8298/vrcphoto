import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from converter import convert_png_with_metadata
from vrchat_log_parser import extract_players_with_ids
import re
import time
import json
from playsound3 import playsound
from datetime import datetime
from tkinter.scrolledtext import ScrolledText  # ← これが必要
import sys
import threading
import pystray
from PIL import Image, ImageDraw

CONFIG_FILE = "items/config.json"

watcher_thread = None
observer_instance = None

# === ウィンドウ非表示関数の追加 ===
def create_tray_icon(app):
    def create_image():
        img = Image.open("items/icon.ico")
        return img

    def on_show(icon, item):
        app.root.after(0, app.root.deiconify)

    def on_exit(icon, item):
        icon.stop()
        app.root.quit()

    icon = pystray.Icon("vrc_photo")
    icon.icon = create_image()
    icon.menu = pystray.Menu(
        pystray.MenuItem('表示', on_show),
        pystray.MenuItem('終了', on_exit)
    )
    icon.run()

def get_latest_log_file(log_dir):
    txt_files = [f for f in os.listdir(log_dir) if f.endswith('.txt')]
    if not txt_files:
        return None
    txt_files.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
    return os.path.join(log_dir, txt_files[0])

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "delete_png": False,
        "compress_png": False,
        "log_dir": os.path.expanduser("~/AppData/LocalLow/VRChat/VRChat"),
        "output_dir": os.path.abspath("output")
    }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

class ConsoleRedirect:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.after(0, self.text_widget.insert, tk.END, message)
        self.text_widget.after(0, self.text_widget.see, tk.END)

    def flush(self):
        pass

class VRChatExifGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat Camera Exif Tool")
        self.config_data = load_config()

        self.tab_control = ttk.Notebook(root)
        self.tab_realtime = ttk.Frame(self.tab_control)
        self.tab_batch = ttk.Frame(self.tab_control)
        self.tab_options = ttk.Frame(self.tab_control)

        self.tab_control.add(self.tab_realtime, text='リアルタイム監視')
        self.tab_control.add(self.tab_batch, text='過去画像変換')
        self.tab_control.add(self.tab_options, text='オプション')
        self.tab_control.pack(expand=1, fill='both')

        self.setup_realtime_tab()
        self.setup_batch_tab()
        self.setup_options_tab()
        self.watching = False #初期化
        self.start_realtime_watch()
        self.watching = True
        self.watch_btn.config(text="監視停止")

        # ログ表示セクション追加
        self.log_frame = ttk.Frame(root)
        self.log_frame.pack(fill='both', expand=False)

        self.log_toggle_btn = ttk.Button(self.log_frame, text="ログ表示", command=self.toggle_log)
        self.log_toggle_btn.pack(anchor='w')

        self.log_widget = ScrolledText(self.log_frame, height=10)
        self.log_widget.pack(fill='both', expand=True)
        self.log_widget.pack_forget()  # 初期は非表示
        
        sys.stdout = ConsoleRedirect(self.log_widget)
        sys.stderr = ConsoleRedirect(self.log_widget)

    def setup_realtime_tab(self):
        ttk.Label(self.tab_realtime, text="ログフォルダ").pack()
        self.realtime_log_dir = tk.Entry(self.tab_realtime, width=60)
        self.realtime_log_dir.insert(0, self.config_data["log_dir"])
        self.realtime_log_dir.pack()
        ttk.Button(self.tab_realtime, text="選択", command=self.select_log_folder).pack()

        ttk.Label(self.tab_realtime, text="出力フォルダ").pack()
        self.realtime_out = tk.Entry(self.tab_realtime, width=60)
        self.realtime_out.insert(0, self.config_data["output_dir"])
        self.realtime_out.pack()
        ttk.Button(self.tab_realtime, text="選択", command=self.select_output_dir).pack()

        self.watch_btn = ttk.Button(self.tab_realtime, text="監視開始", command=self.toggle_watch)
        self.watch_btn.pack()

    def setup_batch_tab(self):
        ttk.Label(self.tab_batch, text="PNGフォルダ").pack()
        self.batch_input = tk.Entry(self.tab_batch, width=60)
        self.batch_input.insert(0, os.path.abspath("input"))
        self.batch_input.pack()
        ttk.Button(self.tab_batch, text="選択", command=self.select_input_dir).pack()

        ttk.Label(self.tab_batch, text="ログフォルダ").pack()
        self.batch_log_dir = tk.Entry(self.tab_batch, width=60)
        self.batch_log_dir.insert(0, self.config_data["log_dir"])
        self.batch_log_dir.pack()
        ttk.Button(self.tab_batch, text="選択", command=self.select_log_folder_batch).pack()

        ttk.Label(self.tab_batch, text="出力フォルダ").pack()
        self.batch_out = tk.Entry(self.tab_batch, width=60)
        self.batch_out.insert(0, self.config_data["output_dir"])
        self.batch_out.pack()
        ttk.Button(self.tab_batch, text="選択", command=self.select_output_dir_batch).pack()

        ttk.Button(self.tab_batch, text="一括変換", command=self.run_batch_convert).pack()

    def setup_options_tab(self):
        self.delete_png_var = tk.BooleanVar(value=self.config_data.get("delete_png", False))
        self.compress_png_var = tk.BooleanVar(value=self.config_data.get("compress_png", False))

        ttk.Checkbutton(self.tab_options, text="元PNGファイルを削除する", variable=self.delete_png_var).pack(anchor='w', pady=10, padx=10)
        ttk.Checkbutton(self.tab_options, text="保存時に圧縮する", variable=self.compress_png_var).pack(anchor='w', pady=10, padx=10)

        ttk.Label(self.tab_options, text="ログフォルダ:").pack(anchor='w', padx=10)
        self.opt_log_dir = tk.Entry(self.tab_options, width=60)
        self.opt_log_dir.insert(0, self.config_data.get("log_dir", ""))
        self.opt_log_dir.pack()
        ttk.Button(self.tab_options, text="選択", command=self.select_log_folder_options).pack()

        ttk.Label(self.tab_options, text="出力先フォルダ:").pack(anchor='w', padx=10)
        self.opt_output_dir = tk.Entry(self.tab_options, width=60)
        self.opt_output_dir.insert(0, self.config_data.get("output_dir", ""))
        self.opt_output_dir.pack()
        ttk.Button(self.tab_options, text="選択", command=self.select_output_dir_options).pack()

        ttk.Button(self.tab_options, text="設定を保存", command=self.save_options).pack(pady=10)

    def save_options(self):
        self.config_data["delete_png"] = self.delete_png_var.get()
        self.config_data["compress_png"] = self.compress_png_var.get()
        self.config_data["log_dir"] = self.opt_log_dir.get()
        self.config_data["output_dir"] = self.opt_output_dir.get()
        save_config(self.config_data)
        messagebox.showinfo("保存完了", "設定を保存しました。")

    def toggle_log(self):
        if self.log_widget.winfo_ismapped():
            self.log_widget.pack_forget()
            self.log_toggle_btn.config(text="ログ表示")
        else:
            self.log_widget.pack(fill='both', expand=True)
            self.log_toggle_btn.config(text="ログ非表示")

    # ========== 省略されてた選択ダイアログ ==========
    def select_log_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.realtime_log_dir.delete(0, tk.END)
            self.realtime_log_dir.insert(0, path)

    def select_log_folder_batch(self):
        path = filedialog.askdirectory()
        if path:
            self.batch_log_dir.delete(0, tk.END)
            self.batch_log_dir.insert(0, path)

    def select_log_folder_options(self):
        path = filedialog.askdirectory()
        if path:
            self.opt_log_dir.delete(0, tk.END)
            self.opt_log_dir.insert(0, path)

    def select_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.realtime_out.delete(0, tk.END)
            self.realtime_out.insert(0, path)

    def select_output_dir_batch(self):
        path = filedialog.askdirectory()
        if path:
            self.batch_out.delete(0, tk.END)
            self.batch_out.insert(0, path)

    def select_output_dir_options(self):
        path = filedialog.askdirectory()
        if path:
            self.opt_output_dir.delete(0, tk.END)
            self.opt_output_dir.insert(0, path)

    def select_input_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.batch_input.delete(0, tk.END)
            self.batch_input.insert(0, path)
    # ========== 選択ダイアログここまで ==========

    def toggle_watch(self):
        global observer_instance, watcher_thread
        if self.watching:
            if observer_instance:
                observer_instance.stop()
                observer_instance.join()
                observer_instance = None
            self.watching = False
            self.watch_btn.config(text="監視開始")
            messagebox.showinfo("停止", "監視を停止しました。")
        else:
            self.start_realtime_watch()
            self.watching = True
            self.watch_btn.config(text="監視停止")
            messagebox.showinfo("監視中", "ログフォルダの監視を開始しました。")

    def start_realtime_watch(self):
        global observer_instance
        log_dir = self.realtime_log_dir.get()
        base_output_dir = self.realtime_out.get()

        class FolderWatcher(FileSystemEventHandler):
            def __init__(self, log_dir):
                self.log_dir = log_dir
                self.current_log = get_latest_log_file(log_dir)
                self.last_size = os.path.getsize(self.current_log) if self.current_log else 0

            def on_modified(self, event):
                latest = get_latest_log_file(self.log_dir)
                if latest != self.current_log:
                    self.current_log = latest
                    self.last_size = os.path.getsize(latest)

                if os.path.normpath(event.src_path) == os.path.normpath(self.current_log):
                    with open(self.current_log, encoding='utf-8') as f:
                        f.seek(self.last_size)
                        new_lines = f.readlines()
                        self.last_size = f.tell()
                        for line in new_lines:
                            if "[VRC Camera] Took screenshot to:" in line:
                                match = re.search(r'screenshot to: (.+\\VRChat.*?\\VRChat_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.*?\.png)', line)
                                if match:
                                    path = match.group(1).strip()
                                    if os.path.exists(path):
                                        time.sleep(3)
                                        config = load_config()
                                        log_data = extract_players_with_ids(self.current_log)
                                        convert_png_with_metadata(
                                            png_path=path,
                                            base_output_dir=base_output_dir,
                                            log_data=log_data.get(os.path.basename(path), None),
                                            delete_png=config.get("delete_png", False),
                                            save_as_avif=config.get("compress_png", False)
                                        )
                                        playsound("items/success.mp3")

        observer_instance = Observer()
        handler = FolderWatcher(log_dir)
        observer_instance.schedule(handler, path=log_dir, recursive=False)
        observer_instance.start()
        watcher_thread = threading.Thread(target=observer_instance.join)
        watcher_thread.start()

    def run_batch_convert(self):
        input_dir = self.batch_input.get()
        log_dir = self.batch_log_dir.get()
        base_output_dir = self.batch_out.get()
        log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.txt')]

        log_cache = {}

        for file in os.listdir(input_dir):
            if file.lower().endswith(".png"):
                png_path = os.path.join(input_dir, file)

                # 出力ファイルが既に存在し、更新日時が近ければスキップ
                out_base = os.path.splitext(file)[0]
                out_ext = ".avif" if load_config().get("compress_png", False) else ".png"
                out_path = os.path.join(base_output_dir, out_base + out_ext)

                if os.path.exists(out_path):
                    continue

                matched_log = None
                for log_file in log_files:
                    with open(log_file, encoding='utf-8') as f:
                        if file in f.read():
                            matched_log = log_file
                            break

                config = load_config()
                if matched_log:
                    if matched_log not in log_cache:
                        log_cache[matched_log] = extract_players_with_ids(matched_log)
                    log_dict = log_cache[matched_log]
                    filename_key = os.path.basename(png_path)
                    log_data = log_dict.get(filename_key, None)
                    convert_png_with_metadata(png_path, base_output_dir, log_data,
                                              delete_png=config.get("delete_png", False),
                                              save_as_avif=config.get("compress_png", False))
                else:
                    convert_png_with_metadata(png_path, base_output_dir, log_data=None,
                                              delete_png=config.get("delete_png", False),
                                              save_as_avif=config.get("compress_png", False))

        messagebox.showinfo("一括変換", "作業が完了しました。")
        playsound("items/success.mp3")

if __name__ == '__main__':
    root = tk.Tk()
    app = VRChatExifGUI(root)

    def hide_window():
        root.withdraw()

    root.protocol("WM_DELETE_WINDOW", hide_window)

    # トレイスレッド開始
    threading.Thread(target=create_tray_icon, args=(app,), daemon=True).start()

    root.mainloop()
