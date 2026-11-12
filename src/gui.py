import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, messagebox, ttk

from config import AUDIO1, AUDIO2, CUTS_JSON, OUTPUT, VIDEO, VIDEO2
from pipeline import process_project


class PodPyApp:
    def __init__(self, root):
        self.root = root
        root.title("PodPy — Podcast Video Editor")
        root.minsize(680, 520)

        self.fields = {}
        self._build_form()

    def _build_form(self):
        container = ttk.Frame(self.root, padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)

        ttk.Label(
            container,
            text="Choose your two videos and two separate audio tracks.",
            font=("TkDefaultFont", 12, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        rows = [
            ("Video 1 (sync reference)", "video1", VIDEO, "file"),
            ("Video 2", "video2", VIDEO2, "file"),
            ("Audio track 1", "audio1", AUDIO1, "file"),
            ("Audio track 2", "audio2", AUDIO2, "file"),
            ("Output video", "output", OUTPUT, "save_video"),
            ("Cut-list JSON", "cuts", CUTS_JSON, "save_json"),
            ("Final Cut XML", "final_cut_xml", "podpy_fcpxml.xml", "save_xml"),
        ]

        for row, (label, key, initial, picker) in enumerate(rows, start=1):
            ttk.Label(container, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=5
            )
            value = tk.StringVar(value=initial)
            self.fields[key] = value
            ttk.Entry(container, textvariable=value).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            ttk.Button(
                container,
                text="Browse…",
                command=lambda field=key, kind=picker: self._browse(field, kind),
            ).grid(row=row, column=2, padx=(8, 0), pady=5)

        self.process_button = ttk.Button(
            container, text="Process video", command=self._start_processing
        )
        self.process_button.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(16, 10))

        ttk.Label(container, text="Progress").grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(4, 4)
        )
        self.status = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        self.log = tk.Text(container, height=8, wrap="word", state="disabled")
        self.log.grid(row=11, column=0, columnspan=3, sticky="nsew")
        container.rowconfigure(11, weight=1)

    def _browse(self, field, kind):
        current = self.fields[field].get()
        initial_dir = str(Path(current).expanduser().parent) if current else str(Path.home())

        if kind == "file":
            selected = filedialog.askopenfilename(
                title="Select media file",
                initialdir=initial_dir,
                filetypes=[
                    ("Media files", "*.mp4 *.mov *.mkv *.avi *.mp3 *.wav *.m4a *.aac *.flac"),
                    ("All files", "*.*"),
                ],
            )
        elif kind == "save_video":
            selected = filedialog.asksaveasfilename(
                title="Save rendered video as",
                initialdir=initial_dir,
                initialfile=Path(current).name if current else "Synced_video.mp4",
                defaultextension=".mp4",
                filetypes=[("MP4 video", "*.mp4")],
            )
        elif kind == "save_json":
            selected = filedialog.asksaveasfilename(
                title="Save camera cut list as",
                initialdir=initial_dir,
                initialfile=Path(current).name if current else "camera_cuts.json",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
            )
        else:
            selected = filedialog.asksaveasfilename(
                title="Save Final Cut XML as",
                initialdir=initial_dir,
                initialfile=Path(current).name if current else "podpy_fcpxml.xml",
                defaultextension=".xml",
                filetypes=[("XML files", "*.xml")],
            )

        if selected:
            self.fields[field].set(selected)

    def _append_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.status.set(message)

    def _start_processing(self):
        values = {key: value.get().strip() for key, value in self.fields.items()}
        required = ("video1", "video2", "audio1", "audio2", "output", "cuts")
        missing = [key for key in required if not values[key]]
        if missing:
            messagebox.showerror(
                "Missing file or destination",
                "Please select both videos, both audio tracks, and output destinations.",
            )
            return

        self.process_button.configure(state="disabled")
        self._append_log("Starting PodPy…")

        def report(message):
            self.root.after(0, self._append_log, message)

        def worker():
            try:
                process_project(
                    video1=values["video1"],
                    video2=values["video2"],
                    audio1=values["audio1"],
                    audio2=values["audio2"],
                    output=values["output"],
                    cuts_json=values["cuts"],
                    final_cut_xml=values.get("final_cut_xml") or None,
                    on_progress=report,
                )
            except Exception as exc:
                report(f"Error: {exc}")
                self.root.after(
                    0, lambda error=exc: messagebox.showerror("Processing failed", str(error))
                )
            finally:
                self.root.after(0, lambda: self.process_button.configure(state="normal"))

        Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    PodPyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
