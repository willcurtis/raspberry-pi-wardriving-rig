#!/usr/bin/env python3
"""Cross-platform desktop controller for a Raspberry Pi wardriving rig."""

from __future__ import annotations

import threading
from typing import Callable

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError as exc:
    raise SystemExit(
        "Tkinter is required. Install the official Python distribution from "
        "https://www.python.org/downloads/ and run this utility again."
    ) from exc

try:
    from .branding import COLORS, LOGO_PATH
    from .client import WardriverClient, format_size, format_time
    from .version import APP_NAME, APP_VERSION, COPYRIGHT_NOTICE, PROJECT_URL
except ImportError:
    from branding import COLORS, LOGO_PATH
    from client import WardriverClient, format_size, format_time
    from version import APP_NAME, APP_VERSION, COPYRIGHT_NOTICE, PROJECT_URL

DEFAULT_URL = "http://wardriver.local:8080"
SERVICE_LABELS = {
    "wardrive-kismet.service": "Kismet collector",
    "wardrive-upload.service": "WiGLE uploader",
    "wardrive-web.service": "Control API",
    "gpsd.service": "GPS daemon",
    "gpsd.socket": "GPS socket",
    "avahi-daemon.service": "mDNS discovery",
}


class WardriverApp(tk.Tk):
    POLL_INTERVAL_MS = 5000

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} · v{APP_VERSION}")
        self.geometry("1120x780")
        self.minsize(880, 620)
        self.configure(background=COLORS["navy"])
        self.client: WardriverClient | None = None
        self.job_running = False
        self.closing = False
        self.poll_after_id: str | None = None
        self.action_buttons: list[ttk.Button] = []

        self.url_var = tk.StringVar(value=DEFAULT_URL)
        self.username_var = tk.StringVar(value="wardrive")
        self.password_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="●  Not connected")
        self.message_var = tk.StringVar(value="Enter the dashboard credentials to connect.")
        self.gps_vars = {
            key: tk.StringVar(value="—")
            for key in ("connection", "fix", "coordinates", "altitude", "speed")
        }
        self.capture_vars = {
            key: tk.StringVar(value="—")
            for key in ("files", "pending", "newest")
        }

        self._configure_style()
        self.logo_source, self.logo_image = self._load_logo()
        if self.logo_image is not None:
            self.iconphoto(True, self.logo_image)
        self._build_menu()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        if self.tk.call("tk", "windowingsystem") == "aqua":
            family = "SF Pro Display"
        elif self.tk.call("tk", "windowingsystem") == "win32":
            family = "Segoe UI"
        else:
            family = "Helvetica"
        self.ui_font = family

        style.configure(
            ".",
            background=COLORS["navy"],
            foreground=COLORS["text"],
            font=(family, 10),
        )
        style.configure("App.TFrame", background=COLORS["navy"])
        style.configure("Header.TFrame", background=COLORS["navy"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure(
            "BrandTitle.TLabel",
            background=COLORS["navy"],
            foreground=COLORS["text"],
            font=(family, 26, "bold"),
        )
        style.configure(
            "BrandSubtitle.TLabel",
            background=COLORS["navy"],
            foreground=COLORS["muted"],
            font=(family, 11),
        )
        style.configure(
            "Version.TLabel",
            background=COLORS["teal"],
            foreground=COLORS["navy"],
            font=(family, 10, "bold"),
            padding=(12, 6),
        )
        style.configure(
            "Heading.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=(family, 13, "bold"),
        )
        style.configure(
            "Metric.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["cyan"],
            font=(family, 11, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["navy"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Card.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
        )
        style.configure(
            "Good.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["teal"],
            font=(family, 12, "bold"),
        )
        style.configure(
            "Bad.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["danger"],
            font=(family, 12, "bold"),
        )
        style.configure(
            "ConnectionGood.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["teal"],
        )
        style.configure(
            "ConnectionBad.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["danger"],
        )
        style.configure(
            "Card.TLabelframe",
            background=COLORS["surface"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["cyan"],
            font=(family, 11, "bold"),
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["navy_alt"],
            foreground=COLORS["text"],
            insertcolor=COLORS["cyan"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=8,
        )
        style.map("TEntry", bordercolor=[("focus", COLORS["cyan"])])
        style.configure(
            "TButton",
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["surface_alt"],
            darkcolor=COLORS["surface_alt"],
            padding=(14, 9),
            font=(family, 10, "bold"),
        )
        style.map(
            "TButton",
            background=[("active", COLORS["border"]), ("disabled", COLORS["navy_alt"])],
            foreground=[("disabled", COLORS["muted"])],
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["teal"],
            foreground=COLORS["navy"],
            bordercolor=COLORS["teal"],
            lightcolor=COLORS["teal"],
            darkcolor=COLORS["teal"],
        )
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["cyan"]), ("disabled", COLORS["border"])],
            foreground=[("disabled", COLORS["muted"])],
        )
        style.configure(
            "Danger.TButton",
            background=COLORS["danger_dark"],
            foreground=COLORS["text"],
            bordercolor=COLORS["danger"],
            lightcolor=COLORS["danger_dark"],
            darkcolor=COLORS["danger_dark"],
        )
        style.map("Danger.TButton", background=[("active", COLORS["danger"])])
        style.configure("TNotebook", background=COLORS["navy"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLORS["navy_alt"],
            foreground=COLORS["muted"],
            padding=(18, 10),
            font=(family, 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["surface"]), ("active", COLORS["surface_alt"])],
            foreground=[("selected", COLORS["cyan"]), ("active", COLORS["text"])],
        )
        style.configure(
            "Treeview",
            background=COLORS["navy_alt"],
            fieldbackground=COLORS["navy_alt"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            rowheight=32,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["cyan_dark"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["surface_alt"],
            foreground=COLORS["cyan"],
            bordercolor=COLORS["border"],
            padding=8,
            font=(family, 10, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", COLORS["border"])])
        style.configure("TSeparator", background=COLORS["border"])

    def _load_logo(self) -> tuple[tk.PhotoImage | None, tk.PhotoImage | None]:
        try:
            source = tk.PhotoImage(file=str(LOGO_PATH))
            factor = max(1, (source.width() + 111) // 112)
            return source, source.subsample(factor, factor)
        except tk.TclError:
            return None, None

    def _build_menu(self) -> None:
        menu = tk.Menu(
            self,
            background=COLORS["surface"],
            foreground=COLORS["text"],
            activebackground=COLORS["cyan_dark"],
            activeforeground=COLORS["text"],
        )
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label=f"About {APP_NAME}", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _show_about(self) -> None:
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME}\nVersion {APP_VERSION}\n\n"
            "Control and telemetry for the Raspberry Pi wardriving rig.\n\n"
            f"{COPYRIGHT_NOTICE}\n{PROJECT_URL}",
            parent=self,
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=(24, 20, 24, 14), style="App.TFrame")
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 18))
        if self.logo_image is not None:
            tk.Label(
                header,
                image=self.logo_image,
                background=COLORS["navy"],
                borderwidth=0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 18))
        brand = ttk.Frame(header, style="Header.TFrame")
        brand.pack(side="left", fill="y", expand=True)
        ttk.Label(brand, text=APP_NAME, style="BrandTitle.TLabel").pack(
            anchor="w", pady=(12, 2)
        )
        ttk.Label(
            brand,
            text="Professional control and telemetry for your Raspberry Pi wardriving rig",
            style="BrandSubtitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(header, text=f"VERSION {APP_VERSION}", style="Version.TLabel").pack(
            side="right", anchor="n", pady=(14, 0)
        )

        connection = ttk.LabelFrame(
            outer, text="RIG CONNECTION", padding=(14, 12), style="Card.TLabelframe"
        )
        connection.pack(fill="x", pady=(0, 16))
        connection.columnconfigure(1, weight=3)
        connection.columnconfigure(3, weight=1)
        connection.columnconfigure(5, weight=1)
        ttk.Label(connection, text="Address", style="Card.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(connection, textvariable=self.url_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 12)
        )
        ttk.Label(connection, text="Username", style="Card.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        ttk.Entry(connection, textvariable=self.username_var, width=15).grid(
            row=0, column=3, sticky="ew", padx=(6, 12)
        )
        ttk.Label(connection, text="Password", style="Card.TLabel").grid(
            row=0, column=4, sticky="w"
        )
        password = ttk.Entry(connection, textvariable=self.password_var, show="*", width=18)
        password.grid(row=0, column=5, sticky="ew", padx=(6, 12))
        password.bind("<Return>", lambda _event: self.connect())
        self.connect_button = ttk.Button(
            connection, text="Connect to rig", command=self.connect, style="Accent.TButton"
        )
        self.connect_button.grid(row=0, column=6)
        self.connection_label = ttk.Label(
            connection,
            textvariable=self.connection_var,
            style="ConnectionBad.TLabel",
        )
        self.connection_label.grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        overview = ttk.Frame(notebook, padding=16, style="Card.TFrame")
        services = ttk.Frame(notebook, padding=16, style="Card.TFrame")
        files = ttk.Frame(notebook, padding=16, style="Card.TFrame")
        notebook.add(overview, text="Overview")
        notebook.add(services, text="Services")
        notebook.add(files, text="Capture files")
        self._build_overview(overview)
        self._build_services(services)
        self._build_files(files)

        ttk.Separator(outer).pack(fill="x", pady=(14, 10))
        footer = ttk.Frame(outer, style="App.TFrame")
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.message_var, style="Muted.TLabel").pack(
            side="left", anchor="w"
        )
        ttk.Label(
            footer,
            text=f"{COPYRIGHT_NOTICE}  ·  v{APP_VERSION}",
            style="Muted.TLabel",
        ).pack(side="right", anchor="e")

    def _build_overview(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        collector = ttk.LabelFrame(
            parent,
            text="KISMET COLLECTION",
            padding=14,
            style="Card.TLabelframe",
        )
        collector.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        collector.columnconfigure(0, weight=1)
        self.kismet_overview = ttk.Label(
            collector, text="Unknown", style="Heading.TLabel"
        )
        self.kismet_overview.grid(row=0, column=0, sticky="w")
        buttons = ttk.Frame(collector, style="Card.TFrame")
        buttons.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self._action_button(buttons, "Start", "/api/kismet/start").pack(
            side="left", padx=(0, 6)
        )
        self._action_button(buttons, "Stop", "/api/kismet/stop").pack(
            side="left", padx=6
        )
        self._action_button(buttons, "Restart", "/api/kismet/restart").pack(
            side="left", padx=6
        )
        self._action_button(
            buttons,
            "Force stop",
            "/api/kismet/force-stop",
            confirmation=(
                "Force stop Kismet?",
                "This immediately kills Kismet and may leave the current capture incomplete.",
            ),
        ).pack(side="left", padx=6)

        gps = ttk.LabelFrame(
            parent, text="GPS TELEMETRY", padding=14, style="Card.TLabelframe"
        )
        gps.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        for row, (key, label) in enumerate(
            (
                ("connection", "GPSD"),
                ("fix", "Fix"),
                ("coordinates", "Coordinates"),
                ("altitude", "Altitude"),
                ("speed", "Speed"),
            )
        ):
            ttk.Label(gps, text=label, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=4
            )
            ttk.Label(gps, textvariable=self.gps_vars[key], style="Metric.TLabel").grid(
                row=row, column=1, sticky="e", padx=(20, 0), pady=3
            )
        gps.columnconfigure(1, weight=1)

        captures = ttk.LabelFrame(
            parent, text="CAPTURE STORAGE", padding=14, style="Card.TLabelframe"
        )
        captures.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        for row, (key, label) in enumerate(
            (("files", "WiGLE CSV files"), ("pending", "Pending upload"), ("newest", "Newest"))
        ):
            ttk.Label(captures, text=label, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=4
            )
            ttk.Label(
                captures, textvariable=self.capture_vars[key], style="Metric.TLabel"
            ).grid(
                row=row, column=1, sticky="e", padx=(20, 0), pady=3
            )
        captures.columnconfigure(1, weight=1)
        self._action_button(captures, "Upload pending files to WiGLE", "/api/upload").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0)
        )

    def _build_services(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.services_tree = ttk.Treeview(
            parent,
            columns=("service", "state", "substate"),
            show="headings",
            height=9,
        )
        self.services_tree.heading("service", text="Service")
        self.services_tree.heading("state", text="State")
        self.services_tree.heading("substate", text="Detail")
        self.services_tree.column("service", width=260)
        self.services_tree.column("state", width=100, anchor="center")
        self.services_tree.column("substate", width=130, anchor="center")
        self.services_tree.tag_configure("active", foreground=COLORS["teal"])
        self.services_tree.tag_configure("inactive", foreground=COLORS["muted"])
        self.services_tree.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(parent, style="Card.TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for column in range(4):
            controls.columnconfigure(column, weight=1)
        self._service_group(
            controls,
            0,
            "Kismet",
            (
                ("Start", "/api/kismet/start", None),
                ("Stop", "/api/kismet/stop", None),
                ("Restart", "/api/kismet/restart", None),
                (
                    "Force stop",
                    "/api/kismet/force-stop",
                    (
                        "Force stop Kismet?",
                        "This immediately kills Kismet and may leave the current capture incomplete.",
                    ),
                ),
            ),
        )
        self._service_group(
            controls,
            1,
            "GPS",
            (
                ("Start", "/api/gpsd/start", None),
                ("Stop", "/api/gpsd/stop", None),
                ("Restart", "/api/gpsd/restart", None),
            ),
        )
        self._service_group(
            controls,
            2,
            "mDNS",
            (
                ("Start", "/api/avahi/start", None),
                (
                    "Stop",
                    "/api/avahi/stop",
                    (
                        "Stop mDNS discovery?",
                        "wardriver.local will stop resolving until mDNS is started again. "
                        "Use the Pi's IP address to reconnect.",
                    ),
                ),
                ("Restart", "/api/avahi/restart", None),
            ),
        )
        upload = ttk.LabelFrame(
            controls, text="WiGLE", padding=8, style="Card.TLabelframe"
        )
        upload.grid(row=0, column=3, sticky="nsew", padx=(6, 0))
        self._action_button(upload, "Run upload", "/api/upload").pack(fill="x")

    def _service_group(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        actions: tuple[tuple[str, str, tuple[str, str] | None], ...],
    ) -> None:
        frame = ttk.LabelFrame(
            parent, text=title, padding=8, style="Card.TLabelframe"
        )
        frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 6, 0),
        )
        for label, path, confirmation in actions:
            self._action_button(frame, label, path, confirmation).pack(
                fill="x", pady=(0, 5)
            )

    def _build_files(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(parent, style="Card.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            toolbar,
            text="Files stored in /var/lib/wardrive/captures",
            style="Heading.TLabel",
        ).pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="right")

        table = ttk.Frame(parent, style="Card.TFrame")
        table.grid(row=1, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.files_tree = ttk.Treeview(
            table,
            columns=("name", "type", "size", "modified", "uploaded"),
            show="headings",
        )
        for key, title in (
            ("name", "Name"),
            ("type", "Type"),
            ("size", "Size"),
            ("modified", "Modified"),
            ("uploaded", "WiGLE uploaded"),
        ):
            self.files_tree.heading(key, text=title)
        self.files_tree.column("name", width=310)
        self.files_tree.column("type", width=80, anchor="center")
        self.files_tree.column("size", width=90, anchor="e")
        self.files_tree.column("modified", width=165, anchor="center")
        self.files_tree.column("uploaded", width=110, anchor="center")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _action_button(
        self,
        parent: ttk.Frame,
        label: str,
        path: str,
        confirmation: tuple[str, str] | None = None,
    ) -> ttk.Button:
        if "force-stop" in path or label == "Stop":
            button_style = "Danger.TButton"
        elif path.endswith("/start") or path == "/api/upload":
            button_style = "Accent.TButton"
        else:
            button_style = "TButton"
        button = ttk.Button(
            parent,
            text=label,
            command=lambda: self.run_action(path, confirmation),
            state="disabled",
            style=button_style,
        )
        self.action_buttons.append(button)
        return button

    def _set_controls(self, enabled: bool) -> None:
        state = "normal" if enabled and self.client and not self.job_running else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)
        self.connect_button.configure(state="disabled" if self.job_running else "normal")

    def _run_job(
        self,
        task: Callable[[], object],
        success: Callable[[object], None],
        *,
        error_dialog: bool = True,
        always: Callable[[], None] | None = None,
    ) -> None:
        if self.job_running or self.closing:
            return
        self.job_running = True
        self._set_controls(False)

        def worker() -> None:
            try:
                result = task()
            except Exception as exc:  # Keep network failures out of Tk's event loop.
                self.after(0, lambda error=exc: finished(error, None))
            else:
                self.after(0, lambda value=result: finished(None, value))

        def finished(error: Exception | None, result: object) -> None:
            self.job_running = False
            if error:
                self.connection_var.set("●  Connection error")
                self.connection_label.configure(style="ConnectionBad.TLabel")
                self.message_var.set(str(error))
                if error_dialog:
                    messagebox.showerror("Wardriver", str(error), parent=self)
            else:
                success(result)
            if always and not self.closing:
                always()
            self._set_controls(error is None or self.client is not None)

        threading.Thread(target=worker, daemon=True).start()

    def connect(self) -> None:
        self.message_var.set("Connecting…")
        try:
            candidate = WardriverClient(
                self.url_var.get(), self.username_var.get(), self.password_var.get()
            )
        except Exception as exc:
            self.message_var.set(str(exc))
            messagebox.showerror("Wardriver", str(exc), parent=self)
            return

        def connected(result: object) -> None:
            status, files = result
            self.client = candidate
            self.connection_var.set(f"●  Connected to {candidate.base_url}")
            self.connection_label.configure(style="ConnectionGood.TLabel")
            self.message_var.set("Connected. Status refreshes every five seconds.")
            self._update_status(status)
            self._update_files(files)
            self._set_controls(True)
            self._schedule_poll()

        self._run_job(candidate.connect, connected)

    def refresh(self) -> None:
        if not self.client:
            self.message_var.set("Connect to the Raspberry Pi first.")
            return
        client = self.client
        self.message_var.set("Refreshing…")

        def refreshed(result: object) -> None:
            status, files = result
            self._update_status(status)
            self._update_files(files)
            self.message_var.set("Status refreshed.")

        self._run_job(lambda: (client.status(), client.files()), refreshed)

    def _poll(self) -> None:
        self.poll_after_id = None
        if self.closing or not self.client:
            return
        if self.job_running:
            self._schedule_poll()
            return
        client = self.client

        def refreshed(result: object) -> None:
            status, files = result
            self._update_status(status)
            self._update_files(files)
            self.connection_var.set(f"●  Connected to {client.base_url}")
            self.connection_label.configure(style="ConnectionGood.TLabel")

        self._run_job(
            lambda: (client.status(), client.files()),
            refreshed,
            error_dialog=False,
            always=self._schedule_poll,
        )

    def _schedule_poll(self) -> None:
        if self.poll_after_id is not None:
            self.after_cancel(self.poll_after_id)
        self.poll_after_id = self.after(self.POLL_INTERVAL_MS, self._poll)

    def run_action(
        self, path: str, confirmation: tuple[str, str] | None = None
    ) -> None:
        if not self.client:
            return
        if confirmation and not messagebox.askyesno(
            confirmation[0], confirmation[1], parent=self
        ):
            return
        client = self.client
        self.message_var.set("Sending command…")

        def completed(result: object) -> None:
            self.message_var.set(str(result))
            self.after(600, self.refresh)

        self._run_job(lambda: client.action(path), completed)

    def _update_status(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        services = payload.get("services", {})
        if isinstance(services, dict):
            self.services_tree.delete(*self.services_tree.get_children())
            for unit in SERVICE_LABELS:
                value = services.get(unit, {})
                if not isinstance(value, dict):
                    value = {}
                row_tag = "active" if value.get("active") else "inactive"
                self.services_tree.insert(
                    "",
                    "end",
                    values=(
                        SERVICE_LABELS[unit],
                        value.get("state", "unknown"),
                        value.get("substate", "unknown"),
                    ),
                    tags=(row_tag,),
                )
            kismet = services.get("wardrive-kismet.service", {})
            if isinstance(kismet, dict):
                active = bool(kismet.get("active"))
                self.kismet_overview.configure(
                    text="Running" if active else f"Stopped ({kismet.get('state', 'unknown')})",
                    style="Good.TLabel" if active else "Bad.TLabel",
                )

        gps = payload.get("gps", {})
        if isinstance(gps, dict):
            connected = bool(gps.get("connected"))
            fixed = bool(gps.get("fix"))
            self.gps_vars["connection"].set("Connected" if connected else "Offline")
            self.gps_vars["fix"].set(
                f"{gps.get('mode', 0)}D fix" if fixed else "No fix"
            )
            lat, lon = gps.get("lat"), gps.get("lon")
            self.gps_vars["coordinates"].set(
                f"{float(lat):.6f}, {float(lon):.6f}"
                if lat is not None and lon is not None
                else "—"
            )
            altitude = gps.get("alt")
            speed = gps.get("speed")
            self.gps_vars["altitude"].set(
                f"{float(altitude):.1f} m" if altitude is not None else "—"
            )
            self.gps_vars["speed"].set(
                f"{float(speed) * 3.6:.1f} km/h" if speed is not None else "—"
            )

        captures = payload.get("captures", {})
        if isinstance(captures, dict):
            self.capture_vars["files"].set(str(captures.get("wigle_files", "—")))
            self.capture_vars["pending"].set(str(captures.get("pending_uploads", "—")))
            self.capture_vars["newest"].set(str(captures.get("newest") or "—"))

    def _update_files(self, files: object) -> None:
        if not isinstance(files, list):
            return
        self.files_tree.delete(*self.files_tree.get_children())
        for item in files:
            if not isinstance(item, dict):
                continue
            uploaded = item.get("uploaded")
            uploaded_text = "Yes" if uploaded is True else "No" if uploaded is False else "—"
            self.files_tree.insert(
                "",
                "end",
                values=(
                    item.get("name", "—"),
                    item.get("type", "—"),
                    format_size(int(item.get("size", 0))),
                    format_time(str(item.get("modified", ""))),
                    uploaded_text,
                ),
            )

    def _on_close(self) -> None:
        self.closing = True
        if self.poll_after_id is not None:
            self.after_cancel(self.poll_after_id)
        self.destroy()


def main() -> None:
    WardriverApp().mainloop()


if __name__ == "__main__":
    main()
