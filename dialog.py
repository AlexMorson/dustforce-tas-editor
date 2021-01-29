import tkinter as tk


class Dialog(tk.Toplevel):
    def __init__(self, parent, label_text, button_text):
        super().__init__(parent)

        label = tk.Label(self, text=label_text)
        entry = tk.Entry(self)
        button = tk.Button(self, text=button_text, command=self._ok)

        label.pack(side=tk.LEFT)
        entry.pack(side=tk.LEFT)
        button.pack(side=tk.LEFT)

        entry.bind("<Return>", lambda e: self._ok())
        entry.focus_set()
        self.entry = entry

        self.attributes('-type', 'dialog')
        self.grab_set()

    def _ok(self):
        if self.ok(self.entry.get()):
            self.destroy()

    def ok(self, text):
        raise NotImplementedError
