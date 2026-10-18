import tkinter as tk
from datetime import datetime

# Reuse the logic you already wrote in alarm.py
from alarm import next_occurrence


class AlarmApp:
    def __init__(self, root):
        self.root = root
        root.title("Alarm Clock")
        root.resizable(False, False)

        self.target = None      # datetime the alarm will fire, or None if no alarm is set
        self.ringing = False
        self.flash_on = False

        # Live clock
        self.clock_label = tk.Label(root, font=("Helvetica", 36), padx=30, pady=10)
        self.clock_label.pack()

        # Hour / minute pickers (24-hour)
        picker = tk.Frame(root)
        picker.pack(pady=5)
        spin_font = ("Helvetica", 20)
        self.hour = tk.Spinbox(
            picker, from_=0, to=23, width=3, wrap=True, format="%02.0f", font=spin_font
        )
        self.minute = tk.Spinbox(
            picker, from_=0, to=59, width=3, wrap=True, format="%02.0f", font=spin_font
        )
        self.hour.pack(side="left")
        tk.Label(picker, text=":", font=spin_font).pack(side="left")
        self.minute.pack(side="left")

        # Buttons
        buttons = tk.Frame(root)
        buttons.pack(pady=8)
        self.set_button = tk.Button(buttons, text="Set Alarm", command=self.set_alarm)
        self.cancel_button = tk.Button(
            buttons, text="Cancel Alarm", command=self.cancel_alarm, state="disabled"
        )
        self.set_button.pack(side="left", padx=5)
        self.cancel_button.pack(side="left", padx=5)

        # Status line
        self.status = tk.Label(root, text="No alarm set", font=("Helvetica", 14), pady=10)
        self.status.pack(fill="x")
        self.default_bg = self.status.cget("bg")

        # Shown only while the alarm is ringing
        self.off_button = tk.Button(
            root,
            text="TURN OFF",
            command=self.turn_off,
            bg="red",
            fg="white",
            font=("Helvetica", 18, "bold"),
            padx=20,
            pady=10,
        )

        self.tick()

    # --- Setting / cancelling ---

    def set_alarm(self):
        try:
            hour = int(self.hour.get())
            minute = int(self.minute.get())
            alarm_time = datetime.now().replace(hour=hour, minute=minute).time()
        except ValueError:
            self.status.config(text="Enter a valid time (HH:MM)")
            return

        self.target = next_occurrence(alarm_time)
        self.status.config(text=f"Alarm set for {self.target:%A %H:%M}")
        self.set_button.config(state="disabled")
        self.cancel_button.config(state="normal")

    def cancel_alarm(self):
        self.target = None
        self.status.config(text="No alarm set")
        self.set_button.config(state="normal")
        self.cancel_button.config(state="disabled")

    # --- Ringing / turning off ---

    def start_ringing(self):
        self.ringing = True
        self.cancel_button.config(state="disabled")
        self.off_button.pack(pady=(0, 15))

    def turn_off(self):
        """The GUI version of wait_for_turn_off: the alarm stops when this runs."""
        self.ringing = False
        self.target = None
        self.off_button.pack_forget()
        self.status.config(text="Alarm turned off.", bg=self.default_bg)
        self.set_button.config(state="normal")
        self.cancel_button.config(state="disabled")

    # --- Runs once per second ---

    def tick(self):
        now = datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M:%S"))

        if self.target and not self.ringing and now >= self.target:
            self.start_ringing()

        if self.ringing:
            self.flash_on = not self.flash_on
            self.status.config(
                text="Your alarm is going off",
                bg="red" if self.flash_on else self.default_bg,
            )
            self.root.bell()  # system beep

        self.root.after(1000, self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    AlarmApp(root)
    root.mainloop()
