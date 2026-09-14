"""Minimal Tkinter UI for the reusable LumoLiftClient API."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from datetime import datetime
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .client import DeviceSnapshot, LumoEvent, LumoLiftClient, VALID_FEEDBACK_DELAYS
from .monitoring import PostureThresholds, classify_posture


class AsyncRunner:
    def __init__(self, messages: queue.Queue):
        self.messages = messages
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine, on_success=None, on_error=None) -> Future:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)

        def complete(done: Future) -> None:
            try:
                result = done.result()
                self.messages.put(("success", on_success, result))
            except Exception as error:
                self.messages.put(("error", on_error, error))

        future.add_done_callback(complete)
        return future

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


class LumoLiftApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lumo Lift")
        self.root.minsize(660, 590)
        self.messages: queue.Queue = queue.Queue()
        self.runner = AsyncRunner(self.messages)
        self.client = LumoLiftClient()
        self.client.add_event_handler(
            lambda event: self.messages.put(("device_event", None, event))
        )
        self.thresholds = PostureThresholds()
        self._busy = False
        self._build()
        self.root.after(100, self._poll_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        connection = ttk.LabelFrame(outer, text="Connection", padding=10)
        connection.grid(row=0, column=0, sticky="ew")
        connection.columnconfigure(1, weight=1)
        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(connection, textvariable=self.status_var).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.connect_button = ttk.Button(
            connection, text="Scan & connect", command=self._connect
        )
        self.connect_button.grid(row=0, column=2, padx=(8, 0))
        self.disconnect_button = ttk.Button(
            connection, text="Disconnect", command=self._disconnect, state="disabled"
        )
        self.disconnect_button.grid(row=0, column=3, padx=(8, 0))

        device = ttk.LabelFrame(outer, text="Device", padding=10)
        device.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for column in range(4):
            device.columnconfigure(column, weight=1)
        self.name_var = tk.StringVar(value="—")
        self.firmware_var = tk.StringVar(value="—")
        self.battery_var = tk.StringVar(value="—")
        self.manufacturer_var = tk.StringVar(value="—")
        self._value(device, 0, 0, "Name", self.name_var)
        self._value(device, 0, 1, "Firmware", self.firmware_var)
        self._value(device, 0, 2, "Battery", self.battery_var)
        self._value(device, 0, 3, "Manufacturer", self.manufacturer_var)

        config = ttk.LabelFrame(outer, text="Device configuration", padding=10)
        config.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        config.columnconfigure(1, weight=1)
        self.coaching_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config, text="Coaching vibrations", variable=self.coaching_var).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(config, text="Apply", command=self._apply_coaching).grid(
            row=0, column=2, sticky="e"
        )

        ttk.Label(config, text="Feedback delay").grid(row=1, column=0, sticky="w", pady=6)
        self.delay_var = tk.StringVar(value="15")
        self.delay_combo = ttk.Combobox(
            config,
            textvariable=self.delay_var,
            values=[str(value) for value in VALID_FEEDBACK_DELAYS],
            state="readonly",
            width=8,
        )
        self.delay_combo.grid(row=1, column=1, sticky="w")
        ttk.Label(config, text="seconds").grid(row=1, column=1, padx=(70, 0), sticky="w")
        ttk.Button(config, text="Apply", command=self._apply_delay).grid(
            row=1, column=2, sticky="e"
        )

        self.feedback_var = tk.StringVar(value="Feedback session: —")
        ttk.Label(config, textvariable=self.feedback_var).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        session_buttons = ttk.Frame(config)
        session_buttons.grid(row=2, column=2, sticky="e")
        ttk.Button(session_buttons, text="Start", command=lambda: self._set_session(True)).pack(
            side="left"
        )
        ttk.Button(session_buttons, text="Stop", command=lambda: self._set_session(False)).pack(
            side="left", padx=(6, 0)
        )

        ttk.Button(config, text="Test vibration", command=self._buzz).grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            config,
            text="Target posture: set with the physical sensor button (no verified software command).",
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0))

        monitor = ttk.LabelFrame(outer, text="Monitoring", padding=10)
        monitor.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        for column in range(4):
            monitor.columnconfigure(column, weight=1)
        self.activity_var = tk.StringVar(value="—")
        self.angle_var = tk.StringVar(value="—")
        self.posture_var = tk.StringVar(value="—")
        self.steps_var = tk.StringVar(value="—")
        self._value(monitor, 0, 0, "Activity", self.activity_var)
        self._value(monitor, 0, 1, "Angle", self.angle_var)
        self._value(monitor, 0, 2, "Posture", self.posture_var)
        self._value(monitor, 0, 3, "Steps", self.steps_var)

        threshold_row = ttk.Frame(monitor)
        threshold_row.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Label(threshold_row, text="Local display thresholds:").pack(side="left")
        self.forward_var = tk.StringVar(value="85")
        self.back_var = tk.StringVar(value="95")
        ttk.Label(threshold_row, text="forward below").pack(side="left", padx=(10, 4))
        ttk.Entry(threshold_row, textvariable=self.forward_var, width=6).pack(side="left")
        ttk.Label(threshold_row, text="back above").pack(side="left", padx=(10, 4))
        ttk.Entry(threshold_row, textvariable=self.back_var, width=6).pack(side="left")
        ttk.Button(threshold_row, text="Apply locally", command=self._apply_thresholds).pack(
            side="left", padx=(10, 0)
        )

        monitor_buttons = ttk.Frame(monitor)
        monitor_buttons.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.monitor_button = ttk.Button(
            monitor_buttons, text="Start monitoring", command=self._start_monitoring
        )
        self.monitor_button.pack(side="left")
        ttk.Button(monitor_buttons, text="Stop", command=self._stop_monitoring).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(monitor_buttons, text="Refresh all", command=self._refresh).pack(
            side="left", padx=(6, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="Events", padding=8)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        outer.rowconfigure(4, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    @staticmethod
    def _value(parent, row: int, column: int, title: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="w", padx=(0, 12))
        ttk.Label(frame, text=title).pack(anchor="w")
        ttk.Label(frame, textvariable=variable, font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w"
        )

    def _run(self, coroutine, success=None, action="Working") -> None:
        if self._busy:
            return
        self._busy = True
        self.status_var.set(f"{action}…")

        def done(result):
            self._busy = False
            if success:
                success(result)

        def failed(error):
            self._busy = False
            self.status_var.set("Error")
            self._append_log(f"ERROR: {error}")
            messagebox.showerror("Lumo Lift", str(error))

        self.runner.submit(coroutine, done, failed)

    def _connect(self) -> None:
        self._run(self.client.connect(), self._connected, "Scanning and connecting")

    def _connected(self, snapshot: DeviceSnapshot) -> None:
        self.status_var.set("Connected")
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self._show_snapshot(snapshot)
        self._append_log("Connected; upload disabled, plugin and active communication enabled.")

    def _disconnect(self) -> None:
        self._run(self.client.disconnect(), self._disconnected, "Disconnecting")

    def _disconnected(self, _result=None) -> None:
        self.status_var.set("Disconnected")
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self._append_log("Disconnected; original communication flags restored.")

    def _refresh(self) -> None:
        self._run(self.client.refresh(), self._refreshed, "Refreshing")

    def _refreshed(self, snapshot: DeviceSnapshot) -> None:
        self.status_var.set("Connected")
        self._show_snapshot(snapshot)
        self._append_log("Device state refreshed.")

    def _show_snapshot(self, snapshot: DeviceSnapshot) -> None:
        self.name_var.set(snapshot.name)
        self.manufacturer_var.set(snapshot.manufacturer)
        self.firmware_var.set(
            f"{snapshot.version.major}.{snapshot.version.minor} r{snapshot.version.revision}"
        )
        self.battery_var.set(
            f"{snapshot.battery.reported_charge * 100:.0f}% · {snapshot.battery.voltage:.2f} V"
        )
        self.coaching_var.set(snapshot.coaching_enabled)
        self.delay_var.set(str(snapshot.feedback_delay_seconds))
        self._show_feedback(snapshot.feedback_session)

    def _show_feedback(self, feedback) -> None:
        state = "active" if feedback.active else "stopped"
        self.feedback_var.set(
            f"Feedback session: {state} · {feedback.remaining_seconds}s left · "
            f"{feedback.good_posture_seconds}s good"
        )

    def _apply_coaching(self) -> None:
        requested = self.coaching_var.get()
        self._run(
            self.client.set_coaching_enabled(requested),
            lambda actual: self._setting_done(f"Coaching {'on' if actual else 'off'}"),
            "Applying coaching",
        )

    def _apply_delay(self) -> None:
        seconds = int(self.delay_var.get())
        self._run(
            self.client.set_feedback_delay(seconds),
            lambda actual: self._setting_done(f"Feedback delay {actual}s"),
            "Applying delay",
        )

    def _set_session(self, enabled: bool) -> None:
        verb = "start" if enabled else "stop"
        if not messagebox.askyesno(
            "Feedback session",
            f"{verb.title()} the posture-feedback session on the device?",
        ):
            return
        self._run(
            self.client.set_feedback_session_enabled(enabled),
            self._session_done,
            f"{verb.title()}ing feedback",
        )

    def _session_done(self, feedback) -> None:
        self.status_var.set("Connected")
        self._show_feedback(feedback)
        self._append_log("Feedback session state updated.")

    def _buzz(self) -> None:
        self._run(
            self.client.buzz(),
            lambda _result: self._setting_done("Test vibration requested"),
            "Requesting vibration",
        )

    def _setting_done(self, message: str) -> None:
        self.status_var.set("Connected")
        self._append_log(message)

    def _start_monitoring(self) -> None:
        self._run(
            self.client.start_monitoring(),
            lambda _result: self._monitoring_started(),
            "Starting monitoring",
        )

    def _monitoring_started(self) -> None:
        self.status_var.set("Connected · monitoring")
        self._append_log("Live monitoring started.")

    def _stop_monitoring(self) -> None:
        self._run(
            self.client.stop_monitoring(),
            lambda _result: self._setting_done("Live monitoring stopped."),
            "Stopping monitoring",
        )

    def _apply_thresholds(self) -> None:
        try:
            self.thresholds = PostureThresholds(
                float(self.forward_var.get()), float(self.back_var.get())
            )
            self._append_log("Local display thresholds updated; device unchanged.")
        except ValueError as error:
            messagebox.showerror("Local thresholds", str(error))

    def _handle_event(self, event: LumoEvent) -> None:
        values = event.values
        if event.kind == "REC":
            activity = str(values.get("act1", "—"))
            angle_value = values.get("angle")
            try:
                angle = float(angle_value)
            except (TypeError, ValueError):
                angle = None
            self.activity_var.set(activity)
            self.angle_var.set("—" if angle is None else f"{angle:.1f}°")
            self.posture_var.set(classify_posture(activity, angle, self.thresholds))
        elif event.kind in ("STEPS", "STEPSH"):
            self.steps_var.set(str(values.get("val", "—")))
        self._append_log(f"{event.kind}: {values}")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll_messages(self) -> None:
        try:
            while True:
                kind, callback, value = self.messages.get_nowait()
                if kind == "success" and callback:
                    callback(value)
                elif kind == "error":
                    if callback:
                        callback(value)
                    else:
                        self._append_log(f"ERROR: {value}")
                elif kind == "device_event":
                    self._handle_event(value)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)

    def _close(self) -> None:
        if self.client.is_connected:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.client.disconnect(), self.runner.loop
                ).result(timeout=8)
            except Exception:
                pass
        self.runner.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    LumoLiftApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
