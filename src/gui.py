import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, messagebox

from config import AUDIO1, AUDIO2, CUTS_JSON, OUTPUT, VIDEO, VIDEO2
from pipeline import process_project


class PodPyApp:
    def __init__(self, root):
        self.root = root
        root.title("PodPy — Podcast Video Editor")
        root.minsize(720, 560)

        self.mode = tk.StringVar(value="separate_audio")
        self.fields = {}
        self._build_form()
        self._update_audio_fields()

    def _build_form(self):
        container = tk.Frame(self.root, padx=18, pady=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)

        tk.Label(
            container,
            text="Choose two camera videos and how to provide audio.",
            font=("TkDefaultFont", 12, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        tk.Radiobutton(
            container,
            text="Use two separate audio tracks",
            variable=self.mode,
            value="separate_audio",
            command=self._update_audio_fields,
        ).grid(row=1, column=0, columnspan=3, sticky="w")
        tk.Radiobutton(
            container,
            text="Videos only (use audio embedded in each video)",
            variable=self.mode,
            value="videos_only",
            command=self._update_audio_fields,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))

        rows = [
            ("Video 1 (sync reference)", "video1", VIDEO, "file"),
            ("Video 2", "video2", VIDEO2, "file"),
            ("Audio track 1", "audio1", AUDIO1, "file"),
            ("Audio track 2", "audio2", AUDIO2, "file"),
            ("Output video", "output", OUTPUT, "save_video"),
            ("Cut-list JSON", "cuts", CUTS_JSON, "save_json"),
            ("Final Cut XML (optional)", "final_cut_xml", "podpy_fcpxml.xml", "save_xml"),
        ]
        self.audio_widgets = []
        for row, (label, key, initial, picker) in enumerate(rows, start=3):
            label_widget = tk.Label(container, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
            value = tk.StringVar(value=initial)
            self.fields[key] = value
            entry = tk.Entry(container, textvariable=value)
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            button = tk.Button(
                container,
                text="Browse…",
                command=lambda field=key, kind=picker: self._browse(field, kind),
            )
            button.grid(row=row, column=2, padx=(8, 0), pady=5)
            if key in ("audio1", "audio2"):
                self.audio_widgets.extend((label_widget, entry, button))

        self.process_button = tk.Button(
            container, text="Process video", command=self._start_processing
        )
        self.process_button.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 10))
        tk.Label(container, text="Progress").grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(4, 4)
        )
        self.status = tk.StringVar(value="Ready")
        tk.Label(container, textvariable=self.status, anchor="w").grid(
            row=12, column=0, columnspan=3, sticky="ew", pady=(0, 8)
        )
        self.log = tk.Text(container, height=8, wrap="word", state="disabled")
        self.log.grid(row=13, column=0, columnspan=3, sticky="nsew")
        container.rowconfigure(13, weight=1)

    def _update_audio_fields(self):
        state = "normal" if self.mode.get() == "separate_audio" else "disabled"
        for widget in self.audio_widgets:
            widget.configure(state=state)

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
        else:
            options = {
                "save_video": ("Save rendered video as", ".mp4", "Synced_video.mp4", "MP4 video", "*.mp4"),
                "save_json": ("Save camera cut list as", ".json", "camera_cuts.json", "JSON files", "*.json"),
                "save_xml": ("Save Final Cut XML as", ".xml", "podpy_fcpxml.xml", "XML files", "*.xml"),
            }
            title, extension, default_name, filetype, pattern = options[kind]
            selected = filedialog.asksaveasfilename(
                title=title,
                initialdir=initial_dir,
                initialfile=Path(current).name if current else default_name,
                defaultextension=extension,
                filetypes=[(filetype, pattern)],
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
        required = ("video1", "video2", "output", "cuts")
        missing = [key for key in required if not values[key]]
        if self.mode.get() == "separate_audio":
            missing.extend(key for key in ("audio1", "audio2") if not values[key])
        if missing:
            messagebox.showerror(
                "Missing file or destination",
                "Please select both videos and all required audio/output paths.",
            )
            return

        self.process_button.configure(state="disabled")
        self._append_log("Starting PodPy…")

        def report(message):
            self.root.after(0, self._append_log, message)

        def worker():
            try:
                videos_only = self.mode.get() == "videos_only"
                process_project(
                    video1=values["video1"],
                    video2=values["video2"],
                    audio1=None if videos_only else values["audio1"],
                    audio2=None if videos_only else values["audio2"],
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
