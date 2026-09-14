"""Construct and close the Tk UI without starting a Bluetooth operation."""

import tkinter as tk

from lumolift.gui import LumoLiftApp


root = tk.Tk()
root.withdraw()
app = LumoLiftApp(root)
root.update_idletasks()
print(f"title={root.title()!r} geometry={root.winfo_reqwidth()}x{root.winfo_reqheight()}")
app._close()
print("gui_smoke=ok")
