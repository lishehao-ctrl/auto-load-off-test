from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


def ask_open_file(
    *,
    title: str,
    initial_dir: Path,
    filetypes: list[tuple[str, str]],
) -> Path | None:
    fp = filedialog.askopenfilename(
        title=title,
        initialdir=str(initial_dir),
        filetypes=filetypes,
    )
    return Path(fp) if fp else None


def ask_save_file(
    *,
    title: str,
    initial_dir: Path,
    initial_name: str,
    filetypes: list[tuple[str, str]],
) -> Path | None:
    fp = filedialog.asksaveasfilename(
        title=title,
        initialdir=str(initial_dir),
        initialfile=initial_name,
        filetypes=filetypes,
    )
    return Path(fp) if fp else None


def show_warning(parent: tk.Misc, message: str) -> None:
    messagebox.showwarning("Warning", message, parent=parent)


def show_info(parent: tk.Misc, message: str) -> None:
    messagebox.showinfo("Info", message, parent=parent)
