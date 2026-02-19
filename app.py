import threading
from pathlib import Path
import customtkinter as ctk
from core import HarProcessor

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

import sys

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("HAR2MP4")
        self.geometry("420x240")
        self.resizable(False, False)

        self.processor = HarProcessor(
            ROOT,
            progress_callback=self.update_progress,
            log_callback=self.log
        )

        self.label = ctk.CTkLabel(self, text="HAR → MP4 Converter",
                                  font=ctk.CTkFont(size=18, weight="bold"))
        self.label.pack(pady=(20, 10))

        self.progress = ctk.CTkProgressBar(self, width=350)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.status = ctk.CTkLabel(self, text="Waiting for .har file...",
                                   text_color="gray")
        self.status.pack(pady=10)

        self.button = ctk.CTkButton(self, text="Start",
                                    command=self.start_process)
        self.button.pack(pady=10)

    def log(self, msg):
        self.status.configure(text=msg)

    def update_progress(self, value):
        self.progress.set(value)

    def start_process(self):
        self.button.configure(state="disabled")
        threading.Thread(target=self.run).start()

    def run(self):
        try:
            har_files = list(ROOT.glob("*.har"))

            if not har_files:
                self.log("No .har file found")
                self.button.configure(state="normal")
                return

            har = har_files[0]

            self.log(f"Processing {har.name}...")
            final = self.processor.process(har)

            self.progress.set(1)
            self.log(f"Done → {final.name}")

        except Exception as e:
            self.log(f"Error: {str(e)}")

        self.button.configure(state="normal")


if __name__ == "__main__":
    app = App()
    app.mainloop()
