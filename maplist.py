import requests
import time
import os
import sys
import json
import tkinter as tk
from tkinter import filedialog

# =======================
# App info & config
# =======================

APP_NAME = "maplist_generator"
CONFIG_DIR = os.path.join(os.getenv("APPDATA"), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# =======================
# Steam API
# =======================

STEAM_COLLECTION_API = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
STEAM_DETAILS_API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
BATCH_SIZE = 50


def get_collection_item_ids(collection_id):
    data = {
        "collectioncount": "1",
        "publishedfileids[0]": collection_id
    }
    r = requests.post(STEAM_COLLECTION_API, data=data, timeout=30)
    r.raise_for_status()
    j = r.json()
    return [c["publishedfileid"] for c in j["response"]["collectiondetails"][0]["children"]]


def get_published_file_details(ids):
    result = []
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        data = {"itemcount": str(len(batch))}
        for idx, fid in enumerate(batch):
            data[f"publishedfileids[{idx}]"] = fid

        r = requests.post(STEAM_DETAILS_API, data=data, timeout=30)
        r.raise_for_status()
        result.extend(r.json()["response"]["publishedfiledetails"])
        time.sleep(0.8)

    return result


def generate_maplist(collection_id, output_dir):
    ids = get_collection_item_ids(collection_id)
    items = get_published_file_details(ids)

    lines = sorted(
        f"{item['title'].strip()}:{item['publishedfileid']}"
        for item in items if item.get("title")
    )

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "maplist.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


# =======================
# Config helpers
# =======================

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(collection_id, output_path):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "collection_id": collection_id,
                "output_path": output_path
            },
            f,
            indent=2,
            ensure_ascii=False
        )


# =======================
# Discord-like GUI
# =======================

BG = "#2b2d31"
PANEL = "#313338"
ENTRY_BG = "#1e1f22"
TEXT = "#dcddde"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
SUCCESS = "#3ba55d"
ERROR = "#ed4245"


def run():
    root = tk.Tk()
    root.title("Maplist Generator")
    root.geometry("580x330")
    root.configure(bg=BG)
    root.resizable(False, False)

    cfg = load_config()

    def make_button(parent, text, command):
        btn = tk.Label(
            parent,
            text=text,
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=7,
            cursor="hand2"
        )
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=ACCENT))
        return btn

    # Title
    tk.Label(
        root,
        text="Maplist Generator",
        font=("Segoe UI", 14, "bold"),
        bg=BG,
        fg="white"
    ).pack(pady=(15, 10))

    panel = tk.Frame(root, bg=PANEL)
    panel.pack(fill="both", expand=True, padx=15, pady=10)

    # Collection ID
    tk.Label(panel, text="Steam Collection ID",
             bg=PANEL, fg=TEXT, anchor="w").pack(fill="x", padx=15, pady=(15, 3))

    id_frame = tk.Frame(panel, bg=PANEL)
    id_frame.pack(fill="x", padx=15)

    collection_var = tk.StringVar(value=cfg.get("collection_id", ""))
    tk.Entry(
        id_frame,
        textvariable=collection_var,
        bg=ENTRY_BG,
        fg="white",
        insertbackground="white",
        relief="flat"
    ).pack(side="left", fill="x", expand=True, ipady=7)

    def paste_collection_id():
        try:
            text = root.clipboard_get()
            digits = "".join(c for c in text if c.isdigit())
            collection_var.set(digits)
        except tk.TclError:
            pass

    make_button(id_frame, "Paste", paste_collection_id).pack(side="left", padx=(8, 0))

    # Output path
    tk.Label(panel, text="Output Folder",
             bg=PANEL, fg=TEXT, anchor="w").pack(fill="x", padx=15, pady=(12, 3))

    path_frame = tk.Frame(panel, bg=PANEL)
    path_frame.pack(fill="x", padx=15)

    path_var = tk.StringVar(value=cfg.get("output_path", ""))
    tk.Entry(
        path_frame,
        textvariable=path_var,
        bg=ENTRY_BG,
        fg="white",
        insertbackground="white",
        relief="flat"
    ).pack(side="left", fill="x", expand=True, ipady=7)

    def browse():
        path = filedialog.askdirectory()
        if path:
            path_var.set(path)

    make_button(path_frame, "Browse", browse).pack(side="left", padx=(8, 0))

    # Status
    status_var = tk.StringVar(value="Ready")
    status = tk.Label(
        panel,
        textvariable=status_var,
        bg=PANEL,
        fg=TEXT,
        anchor="w",
        justify="left",
        wraplength=520
    )
    status.pack(fill="x", padx=15, pady=(15, 5))

    # Generate
    def generate():
        if not collection_var.get():
            status_var.set("❌ Collection ID is required (use Paste)")
            status.config(fg=ERROR)
            return

        try:
            status_var.set("⏳ Working...")
            status.config(fg=TEXT)
            root.update_idletasks()

            out = path_var.get() or os.path.dirname(sys.argv[0])
            result = generate_maplist(collection_var.get(), out)

            save_config(collection_var.get(), path_var.get())

            status_var.set(f"✔ Done. Saved to: {result}")
            status.config(fg=SUCCESS)
        except Exception as e:
            status_var.set(f"❌ Error:\n{e}")
            status.config(fg=ERROR)

    make_button(panel, "Generate maplist.txt", generate).pack(pady=15)

    root.mainloop()


if __name__ == "__main__":
    run()
