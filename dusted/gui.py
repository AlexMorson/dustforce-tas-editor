import os
import queue
import re
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox

from . import dustforce, utils
from .config import config
from .cursor import Cursor
from .dialog import Dialog, SimpleDialog
from .inputs import Inputs
from .inputs_view import InputsView
from .level import Level
from .level_view import LevelView
from .replay import Replay
from .undo_stack import UndoStack

LEVEL_PATTERN = r"START (.*)"
COORD_PATTERN = r"(\d*) (-?\d*) (-?\d*)"
CHARACTERS = ["dustman", "dustgirl", "dustkid", "dustworth"]


class LoadReplayDialog(SimpleDialog):
    def __init__(self, app):
        super().__init__(app, "Replay id:", "Load")
        self.app = app

    def ok(self, replay_id):
        replay = utils.load_replay_from_dustkid(replay_id)
        self.app.load_replay(replay)
        return True


class NewReplayDialog(Dialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        character_label = tk.Label(self, text="Character:")
        character_label.grid(row=0, column=0, sticky="e")
        self.character_var = tk.StringVar(self)
        character_choice = tk.OptionMenu(self, self.character_var, *CHARACTERS)
        character_choice.grid(row=0, column=1, sticky="ew")

        level_label = tk.Label(self, text="Level id:")
        level_label.grid(row=1, column=0, sticky="e")
        self.level_entry = tk.Entry(self)
        self.level_entry.grid(row=1, column=1, sticky="ew")

        button = tk.Button(self, text="Create", command=self.ok)
        button.grid(row=2, columnspan=2)

        self.character_var.set(CHARACTERS[app.character])

    def ok(self):
        level_id = self.level_entry.get()
        character = CHARACTERS.index(self.character_var.get())
        self.app.new_file(level_id, character)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.level = Level()
        self.character = 0
        self.inputs = Inputs()
        self.cursor = Cursor(self.inputs)
        self.undo_stack = UndoStack(self.inputs, self.cursor)
        self.undo_stack.subscribe(self.on_undo_stack_change)

        # Menu bar
        menubar = tk.Menu(self)

        filemenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", underline=0, menu=filemenu)

        newfilemenu = tk.Menu(filemenu, tearoff=0)
        filemenu.add_cascade(label="New", menu=newfilemenu)
        newfilemenu.add_command(label="Empty replay", command=lambda: NewReplayDialog(self))
        newfilemenu.add_command(label="From replay id", command=lambda: LoadReplayDialog(self))

        filemenu.add_command(label="Open", command=self.open_file)
        filemenu.add_command(label="Save", command=self.save_file)
        filemenu.add_command(label="Save As", command=lambda: self.save_file(True))

        self.editmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", underline=0, menu=self.editmenu)

        self.editmenu.add_command(label="Undo", command=self.undo_stack.undo, state=tk.DISABLED)
        self.editmenu.add_command(label="Redo", command=self.undo_stack.redo, state=tk.DISABLED)

        settingsmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", underline=0, menu=settingsmenu)

        settingsmenu.add_command(label="Set Dustforce directory", command=self.set_dustforce_directory)

        self.config(menu=menubar)

        # Widgets
        buttons = tk.Frame(self)
        button1 = tk.Button(buttons, text="Watch", command=self.watch)
        button2 = tk.Button(buttons, text="Load State and Watch", command=self.load_state_and_watch)
        canvas = LevelView(self, self.level, self.cursor)
        inputs = InputsView(self, self.inputs, self.cursor, self.undo_stack)

        # Layout
        button1.pack(side=tk.LEFT)
        button2.pack(side=tk.LEFT)
        buttons.pack(anchor=tk.W)
        canvas.pack(fill=tk.BOTH, expand=1)
        inputs.pack(fill=tk.X)

        # Hotkeys
        self.bind("<F5>", lambda e: self.watch())
        self.bind("<F6>", lambda e: self.load_state_and_watch())

        self.canvas = canvas
        self.file = None
        self.after_idle(self.handle_stdout)

        # Check if the Dustforce directory is valid
        if not os.path.isdir(config.dustforce_path):
            tk.messagebox.showwarning(message="Could not find the Dustforce directory. Please update it in Settings.")

    def handle_stdout(self):
        try:
            while 1:
                line = dustforce.stdout.get_nowait()
                if m := re.match(COORD_PATTERN, line):
                    frame, x, y = map(int, m.group(1, 2, 3))
                    self.canvas.add_coordinate(frame, x, y-48)
        except queue.Empty:
            self.after(16, self.handle_stdout)

    def watch(self):
        if self.save_file():
            dustforce.watch_replay(self.file)

    def load_state_and_watch(self):
        if self.save_file():
            dustforce.watch_replay_load_state(self.file)

    def save_file(self, save_as=False):
        if not self.file or save_as:
            self.file = tk.filedialog.asksaveasfilename(
                defaultextension=".dfreplay",
                filetypes=[("replay files", "*.dfreplay")],
                title="Save replay"
            )
            if not self.file:
                return False
        replay = Replay()
        replay.username = "TAS"
        replay.level = self.level.get()
        replay.characters = [self.character]
        replay.inputs = [self.inputs.get()]
        utils.write_replay_to_file(self.file, replay)
        return True

    def new_file(self, level_id, character):
        self.file = None
        self.level.set(level_id)
        self.character = character
        self.inputs.reset()
        self.undo_stack.clear()

    def open_file(self):
        filepath = tk.filedialog.askopenfilename(
            defaultextension=".dfreplay",
            filetypes=[("replay files", "*.dfreplay")],
            title="Load replay"
        )
        if filepath:
            replay = utils.load_replay_from_file(filepath)
            self.load_replay(replay, filepath)

    def load_replay(self, replay, filepath=None):
        self.file = filepath
        self.level.set(replay.level)
        self.character = replay.characters[0]
        self.inputs.set(replay.inputs[0])
        self.undo_stack.clear()

    def set_dustforce_directory(self):
        current_path = config.dustforce_path
        new_path = tk.filedialog.askdirectory(initialdir=current_path)
        if new_path:
            config.dustforce_path = new_path
        config.write()

    def on_undo_stack_change(self):
        undo_state = tk.NORMAL if self.undo_stack.can_undo else tk.DISABLED
        redo_state = tk.NORMAL if self.undo_stack.can_redo else tk.DISABLED

        undo_label = "Undo " + self.undo_stack.undo_text()
        redo_label = "Redo " + self.undo_stack.redo_text()

        self.editmenu.entryconfig(0, state=undo_state, label=undo_label)
        self.editmenu.entryconfig(1, state=redo_state, label=redo_label)