"""Native desktop form-review window. Launch: python desktop.py.

Tk owns widgets and dialogs; one serial background thread owns domain commands.
There is no webview, browser, HTTP listener, account or network dependency.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import queue
import threading
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from branding import OWNERSHIP_NOTICE, PRODUCT_NAME
from desktop_model import DesktopSession, InputError, Cancelled
from server import ROOT, validate_values
from form_types import normalized_drag, percentage_region, validate_region


class DesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.session = DesktopSession()
        self.snapshot = self.session.snapshot()
        self.design_draft = None
        self.design_selected = None
        self.design_tool = None
        self.design_start = None
        self.design_drag_item = None
        self.display_size = None
        self._draft_after = None
        self._draft_unsent = False
        self._choices_error = False
        self.commands = queue.Queue(maxsize=1)
        self.events = queue.Queue()
        self.busy = False
        self.closing = False
        self._after_busy = None
        self._callback = None
        self._operation_id = 0
        self.selected_record = None
        self.selected_field = None
        self.page = 1
        self.photo = None
        self.zoom = 1.0
        self.fit_width = True
        self._resize_after = None
        self._rendering = False
        self.editor_dirty = False
        self.review_values = {}
        self.review_confirmed = set()
        self.mappings = {}
        self.mapping_dirty = False
        self.drag_field = None
        self._disabled_states = []
        self.status = tk.StringVar(value="Import your first PDF or image, then draw and name the fields you need.")
        self.value_var = tk.StringVar()
        self.confirm_var = tk.BooleanVar()
        self.reviewer_var = tk.StringVar()
        self.field_title = tk.StringVar(value="Select a field")
        self.field_detail = tk.StringVar(value="Confirm every answer against its source, including optional blanks.")
        self.record_title = tk.StringVar(value="Source document")
        self.record_context = tk.StringVar()
        self.mode_label = tk.StringVar(value="LOCAL DESKTOP\nCreate your own extraction type")
        self.type_name = tk.StringVar()
        self.design_name = tk.StringVar()
        self.design_label = tk.StringVar()
        self.design_kind = tk.StringVar(value="text")
        self.design_required = tk.BooleanVar()
        self.design_identifier = tk.BooleanVar()
        self.design_choices = tk.StringVar()
        self.design_help = tk.StringVar(value="Draw a field around its answer area. Select a field to rename or redraw it.")
        self.export_help = tk.StringVar(value="XLSX retains supported blank-template layout. CSV contains values only. Exports include approved records.")
        self.page_label = tk.StringVar(value="No document selected")
        self.queue_label = tk.StringVar(value="0 documents")
        self.mapping_label = tk.StringVar(value="No spreadsheet template")
        self.mapping_errors = tk.StringVar(value="Import a blank spreadsheet or use your categories as columns.")
        self.mapping_choice = tk.StringVar(value="Unassigned")
        self.example_value = tk.StringVar(value="")
        self.mapping_column = tk.StringVar(value="Select a destination column")
        self.source_issues = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.header_var = tk.StringVar(value="1")
        self._setup_style()
        self._build()
        self._build_menu()
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        if root.tk.call("tk", "windowingsystem") == "aqua":
            root.createcommand("::tk::mac::Quit", self.request_close)
        root.bind("<Command-o>" if os.name != "nt" else "<Control-o>", lambda e: self.open_project())
        root.bind("<Command-s>" if os.name != "nt" else "<Control-s>", lambda e: self.save_project())
        self.thread = threading.Thread(target=self._domain_loop, name="FormbridgeDomain", daemon=True)
        self.thread.start()
        root.after(60, self._poll)
        self._render(self.snapshot)

    def _setup_style(self):
        self.root.title(f"{PRODUCT_NAME} — Local form review")
        self.root.geometry("1320x850")
        self.root.minsize(1024, 700)
        self.root.configure(background="#f2f4f7")
        self.style = ttk.Style()
        font = "Segoe UI" if os.name == "nt" else "Helvetica Neue"
        self.root.option_add("*Font", (font, 12))
        self.style.configure("TFrame", background="#f2f4f7")
        self.style.configure("TLabel", background="#f2f4f7", foreground="#253448")
        self.style.configure("Title.TLabel", font=(font, 25, "bold"), foreground="#18314c")
        self.style.configure("Heading.TLabel", font=(font, 14, "bold"))
        self.style.configure("Small.TLabel", foreground="#617084", font=(font, 11))
        self.style.configure("Error.TLabel", foreground="#a13b22", font=(font, 11))
        self.style.configure("Treeview", rowheight=31, font=(font, 11))
        self.style.configure("StagingQueue.Treeview", rowheight=48)
        self.style.configure("Treeview.Heading", font=(font, 11, "bold"))
        self.style.configure("TButton", padding=(9, 5))
        self.style.configure("TNotebook.Tab", padding=(16, 8))

    @staticmethod
    def _tree(parent, columns, headings, widths, height=8):
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=height)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for name, title, width in zip(columns, headings, widths):
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=65, stretch=True)
        return frame, tree

    def _build(self):
        shell = ttk.Frame(self.root, padding=(20, 14, 20, 8))
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)
        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(1, weight=1)
        brand = ttk.Frame(header)
        brand.grid(row=0, column=0, sticky="w")
        ttk.Label(brand, text=PRODUCT_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(brand, text=OWNERSHIP_NOTICE, style="Small.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(header, textvariable=self.mode_label, style="Small.TLabel", width=1).grid(row=0, column=1, sticky="ew", padx=20)
        self.project_label = ttk.Label(header, text="Unsaved project", style="Small.TLabel")
        self.project_label.grid(row=0, column=3, sticky="e")
        top = ttk.Frame(shell)
        top.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(top, text="＋ Import forms…", command=self.import_forms).pack(side="left")
        ttk.Button(top, text="Open project…", command=self.open_project).pack(side="left", padx=6)
        ttk.Button(top, text="Save project", command=self.save_project).pack(side="left")
        ttk.Button(top, text="Design masks", command=self.start_design).pack(side="left", padx=(18, 6))
        ttk.Button(top, text="Load type…", command=self.load_form_type).pack(side="left")
        ttk.Button(top, text="Save type…", command=self.save_form_type).pack(side="left", padx=6)
        self.notebook = ttk.Notebook(shell)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        review_tab = ttk.Frame(self.notebook, padding=12)
        spreadsheet_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(review_tab, text="1   Design & review")
        self.notebook.add(spreadsheet_tab, text="2   Fields & spreadsheet")
        self._build_review(review_tab)
        self._build_spreadsheet(spreadsheet_tab)
        footer = ttk.Frame(shell)
        footer.grid(row=3, column=0, sticky="ew", pady=(9, 0))
        footer.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=110)
        self.progress.grid(row=0, column=0, padx=(0, 10))
        ttk.Label(footer, textvariable=self.status, style="Small.TLabel").grid(row=0, column=1, sticky="ew")
        self.cancel_button = ttk.Button(footer, text="Cancel processing", command=self.cancel_processing, state="disabled")
        self.cancel_button.grid(row=0, column=2)

    def _messages(self, parent, variable, height=2):
        frame = ttk.Frame(parent)
        text = tk.Text(frame, height=height, width=1, wrap="word", relief="flat",
                       background="#f2f4f7", foreground="#a13b22", state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        def refresh(*_):
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", variable.get())
            text.configure(state="disabled")
        variable.trace_add("write", refresh)
        refresh()
        return frame

    @staticmethod
    def _constrain_panes(panes, left, center, right):
        width = panes.winfo_width()
        if width < left + center + right + 10:
            return
        first = min(max(panes.sashpos(0), left), width - center - right - 10)
        second = min(max(panes.sashpos(1), first + center + 5), width - right - 5)
        panes.sashpos(0, first)
        panes.sashpos(1, second)

    def _build_review(self, parent):
        panes = ttk.Panedwindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, center, right = (ttk.Frame(panes, padding=(4, 4)) for _ in range(3))
        panes.add(left, weight=2)
        panes.add(center, weight=5)
        panes.add(right, weight=3)
        panes.bind("<Configure>", lambda _event: self._constrain_panes(panes, 220, 300, 330))
        for pane in (left, center, right):
            pane.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        center.rowconfigure(3, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(left, text="Document queue", style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Label(left, textvariable=self.queue_label, style="Small.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 8))
        frame, self.queue_tree = self._tree(left, ("document", "state"), ("Document", "Review"), (145, 85), 1)
        frame.grid(row=2, column=0, sticky="nsew")
        self.queue_tree.bind("<<TreeviewSelect>>", self._queue_selected)
        ttk.Button(left, text="Remove selected", command=self.remove_document).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(left, text="Upload a PDF or image, draw your answer masks, then save a named extraction type for matching forms.", style="Small.TLabel", wraplength=210).grid(row=4, column=0, sticky="w", pady=(8, 0))
        title = ttk.Label(center, textvariable=self.record_title, style="Heading.TLabel", width=1)
        title.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        title.bind("<Configure>", lambda event: title.configure(wraplength=max(180, event.width)))
        self.record_context_label = ttk.Label(center, textvariable=self.record_context, style="Small.TLabel", width=1)
        self.record_context_label.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.record_context_label.bind("<Configure>", lambda event: self.record_context_label.configure(wraplength=max(180, event.width)))
        tools = ttk.Frame(center)
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 7))
        ttk.Button(tools, text="‹", width=3, command=lambda: self.change_page(-1)).pack(side="left")
        ttk.Button(tools, text="›", width=3, command=lambda: self.change_page(1)).pack(side="left", padx=3)
        ttk.Label(tools, textvariable=self.page_label, style="Small.TLabel").pack(side="left", padx=5)
        ttk.Button(tools, text="−", width=3, command=lambda: self.change_zoom(.8)).pack(side="right")
        ttk.Button(tools, text="＋", width=3, command=lambda: self.change_zoom(1.25)).pack(side="right", padx=3)
        ttk.Button(tools, text="Fit width", command=self.fit_page).pack(side="right", padx=3)
        self.preview_frame = ttk.Frame(center)
        self.preview_frame.grid(row=3, column=0, sticky="nsew")
        self.canvas = tk.Canvas(self.preview_frame, width=1, height=1, background="#dce2e9", highlightthickness=0)
        yscroll = self.page_yscroll = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.canvas.yview)
        xscroll = self.page_xscroll = ttk.Scrollbar(self.preview_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._preview_resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
        self.canvas.bind("<ButtonPress-1>", self._mask_start)
        self.canvas.bind("<B1-Motion>", self._mask_motion)
        self.canvas.bind("<ButtonRelease-1>", self._mask_end)
        self.source_text = tk.Text(self.preview_frame, width=1, height=1, wrap="word", background="white", foreground="#253448", padx=18, pady=18, relief="flat", state="disabled", yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self._messages(center, self.source_issues).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.review_heading = ttk.Label(right, text="Review answers", style="Heading.TLabel")
        self.review_heading.grid(row=0, column=0, sticky="w", pady=(0, 5))
        frame, self.field_tree = self._tree(right, ("field", "value", "check"), ("Field", "Answer", "✓"), (125, 120, 38), 1)
        self.review_field_frame = frame
        frame.grid(row=1, column=0, sticky="nsew")
        self.field_tree.bind("<<TreeviewSelect>>", self._field_selected)
        editor = self.review_editor = ttk.Frame(right)
        editor.grid(row=2, column=0, sticky="ew")
        ttk.Label(editor, textvariable=self.field_title, style="Heading.TLabel", width=1).pack(fill="x", pady=(6, 2))
        self.entry = ttk.Entry(editor, textvariable=self.value_var)
        self.entry.pack(fill="x", pady=4)
        self.choice = ttk.Combobox(editor, textvariable=self.value_var, state="readonly")
        self.value_var.trace_add("write", self._value_changed)
        self.entry.bind("<Return>", lambda e: self.save_review())
        self.choice.bind("<<ComboboxSelected>>", lambda e: None)
        ttk.Label(editor, textvariable=self.field_detail, style="Error.TLabel", wraplength=310).pack(fill="x", pady=(2, 4))
        self.confirm_check = ttk.Checkbutton(editor, text="Confirmed against source", variable=self.confirm_var, command=self.confirm_field)
        self.confirm_check.pack(anchor="w", pady=2)
        review_actions = ttk.Frame(editor)
        review_actions.pack(fill="x", pady=2)
        self.save_review_button = ttk.Button(review_actions, text="Save draft", command=self.save_review)
        self.save_review_button.pack(side="left", fill="x", expand=True)
        ttk.Button(review_actions, text="Expand…", command=self.expand_answer).pack(side="right", padx=(6, 0))
        ttk.Separator(editor).pack(fill="x", pady=6)
        ttk.Label(editor, text="Reviewer", style="Small.TLabel").pack(anchor="w")
        self.reviewer_entry = ttk.Entry(editor, textvariable=self.reviewer_var)
        self.reviewer_entry.pack(fill="x", pady=4)
        self.approve_button = ttk.Button(editor, text="Approve document", command=self.approve_record)
        self.approve_button.pack(fill="x", pady=(4, 2))
        ttk.Label(editor, text="Approval requires valid values, every field confirmed and your reviewer name.", style="Small.TLabel", wraplength=310).pack(fill="x", pady=(4, 0))
        self._build_designer(right)

    def _build_designer(self, parent):
        panel = self.design_panel = ttk.Frame(parent)
        panel.grid(row=0, column=0, rowspan=3, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(3, weight=1)
        ttk.Label(panel, text="Design extraction type", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(panel, text="Type name", style="Small.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.type_name_entry = ttk.Entry(panel, textvariable=self.type_name)
        self.type_name_entry.grid(row=2, column=0, sticky="ew", pady=(2, 6))
        frame, self.mask_tree = self._tree(panel, ("field", "page"), ("Your fields", "Page"), (205, 50), 4)
        frame.grid(row=3, column=0, sticky="nsew")
        self.mask_tree.bind("<<TreeviewSelect>>", self._mask_selected)
        tools = ttk.Frame(panel)
        tools.grid(row=4, column=0, sticky="ew", pady=5)
        for column, (label, action) in enumerate((("Draw new", lambda: self._set_mask_tool("new")),
                                                ("Redraw", lambda: self._set_mask_tool("redraw")), ("Delete", self.delete_mask))):
            tools.columnconfigure(column, weight=1, uniform="masktools")
            ttk.Button(tools, text=label, command=action, width=5, padding=(3, 5)).grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0))
        ttk.Button(tools, text="Add mask by coordinates…", command=self.add_mask_coordinates).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        settings = ttk.Frame(panel)
        settings.grid(row=5, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((("Field name", self.design_name), ("Label", self.design_label))):
            ttk.Label(settings, text=label, style="Small.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            entry = ttk.Entry(settings, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            if row == 0:
                self.design_name_entry = entry
        ttk.Label(settings, text="Value type", style="Small.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Combobox(settings, textvariable=self.design_kind, values=("text", "integer", "number", "date", "choice"), state="readonly").grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(settings, text="Required", variable=self.design_required).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(settings, text="Use as record identifier (text)", variable=self.design_identifier).grid(row=4, column=0, columnspan=2, sticky="w")
        self.design_choices_label = ttk.Label(settings, text="Choice codes: 1=Yes;0=No", style="Small.TLabel")
        self.design_choices_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.design_choices_entry = ttk.Entry(settings, textvariable=self.design_choices)
        self.design_choices_entry.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 4))
        ttk.Label(panel, textvariable=self.design_help, style="Small.TLabel", wraplength=310).grid(row=6, column=0, sticky="ew", pady=6)
        actions = ttk.Frame(panel)
        actions.grid(row=7, column=0, sticky="ew")
        ttk.Button(actions, text="Apply type", command=self.apply_form_type).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text="Discard draft", command=self.discard_design).pack(side="right", padx=(5, 0))
        for variable in (self.type_name, self.design_name, self.design_label, self.design_kind, self.design_required, self.design_identifier, self.design_choices):
            variable.trace_add("write", self._design_changed)

    def _design_changed(self, *_):
        if self._rendering or self.design_draft is None:
            return
        self._show_choice_settings()
        self.design_draft["name"] = self.type_name.get()
        field = next((f for f in self.design_draft["fields"] if f["id"] == self.design_selected), None)
        if field:
            field.update(name=self.design_name.get(), label=self.design_label.get(),
                         type=self.design_kind.get(), required=self.design_required.get())
            if self.design_identifier.get():
                self.design_draft["identifierField"] = field["id"]
            elif self.design_draft["identifierField"] == field["id"]:
                self.design_draft["identifierField"] = None
            if field["type"] == "choice":
                choices = {}
                for item in self.design_choices.get().split(";"):
                    if not item.strip():
                        continue
                    code, separator, label = item.partition("=")
                    if not separator or code.strip() in choices:
                        self.design_help.set("Choices need unique code=label pairs separated by semicolons.")
                        self._choices_error = True
                        self._draft_unsent = True
                        return
                    choices[code.strip()] = label.strip()
                field["choices"] = choices
            else:
                field.pop("choices", None)
        self._choices_error = False
        self._draft_unsent = True

    def _persist_design(self, callback=None):
        self._draft_after = None
        if self._choices_error:
            self.design_help.set("Finish the choice codes as code=label pairs, or discard this draft.")
            self.status.set("Finish the choice codes before continuing.")
            return
        if not self._draft_unsent or self.design_draft is None:
            if callback:
                callback()
            return
        if self.busy or self.design_start is not None:
            self._draft_after = self.root.after(150, lambda: self._persist_design(callback))
            return
        draft = copy.deepcopy(self.design_draft)
        self._draft_unsent = False
        self._choices_error = False
        self._submit("Saving extraction-type draft", lambda: self.session.replace_draft(draft), lambda _: callback() if callback else None)

    def _show_mask(self):
        field = next((f for f in (self.design_draft or {}).get("fields", []) if f["id"] == self.design_selected), {})
        before = self._rendering
        self._rendering = True
        self.design_name.set(field.get("name", ""))
        self.design_label.set(field.get("label", ""))
        self.design_kind.set(field.get("type", "text"))
        self.design_required.set(field.get("required", False))
        self.design_identifier.set(bool(field) and self.design_draft["identifierField"] == field["id"])
        self.design_choices.set(";".join(f"{k}={v}" for k, v in field.get("choices", {}).items()))
        self._show_choice_settings()
        self._rendering = before

    def _show_choice_settings(self):
        for widget in (self.design_choices_label, self.design_choices_entry):
            widget.grid() if self.design_kind.get() == "choice" else widget.grid_remove()

    def _render_designer(self):
        design = self.snapshot.get("phase") in {"empty", "design"}
        for widget in (self.review_heading, self.review_field_frame, self.review_editor):
            widget.grid_remove() if design else widget.grid()
        self.design_panel.grid() if design else self.design_panel.grid_remove()
        self.design_draft = copy.deepcopy(self.snapshot.get("draft"))
        self._draft_unsent = False
        self._choices_error = False
        self._reset_gesture()
        self.type_name.set((self.design_draft or {}).get("name", ""))
        self.mask_tree.delete(*self.mask_tree.get_children())
        fields = (self.design_draft or {}).get("fields", [])
        if self.design_selected not in {f["id"] for f in fields}:
            self.design_selected = fields[0]["id"] if fields else None
        for field in fields:
            self.mask_tree.insert("", "end", iid=field["id"], values=(field.get("label") or field.get("name") or "Unnamed field", (field.get("region") or {}).get("page", "—")))
        if self.design_selected:
            self.mask_tree.selection_set(self.design_selected)
        self._show_mask()
        if design:
            if not self._record():
                self.design_help.set("Upload a PDF or image to draw masks, or load a saved extraction type.")
            elif self.design_draft is None:
                self.design_help.set("Choose Design masks to create an extraction type for this source.")
            elif not (self.design_draft or {}).get("pages"):
                self.design_help.set("Text-only sources cannot define masks. Upload a PDF or image.")
            else:
                self.design_help.set("Draw answer areas; name each field and explicitly select a text identifier. Dates use YYYY-MM-DD.")
                if not fields:
                    self.design_tool = "new"

    def _mask_selected(self, _event=None):
        if self._rendering or self.busy:
            return
        selection = self.mask_tree.selection()
        if not selection or selection[0] == self.design_selected:
            return
        target = selection[0]
        def select():
            self.design_selected = target
            self._show_mask()
            field = next((f for f in (self.design_draft or {}).get("fields", []) if f["id"] == target), {})
            if field.get("region"):
                self.page = field["region"]["page"]
            self._reset_gesture()
            self._render_page()
        self._persist_design(select)

    def _reset_gesture(self):
        self.design_start = None
        if self.design_drag_item is not None:
            self.canvas.delete(self.design_drag_item)
        self.design_drag_item = None

    def _set_mask_tool(self, tool):
        if self.busy or self.design_draft is None:
            return
        if tool == "redraw" and not self.design_selected:
            self.design_help.set("Select a field to redraw.")
            return
        self._reset_gesture()
        self.design_tool = tool
        self.canvas.configure(cursor="crosshair")
        self.design_help.set("Drag around the answer area on the source page.")

    def _mask_start(self, event):
        if self.busy or self.design_draft is None or not self.display_size:
            return
        point = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        width, height = self.display_size
        if not (12 <= point[0] <= 12 + width and 12 <= point[1] <= 12 + height):
            return
        if not self.design_tool:
            for field in reversed(self.design_draft["fields"]):
                r = field.get("region", {})
                if r.get("page") == self.page and r["x"] <= (point[0] - 12) / width <= r["x"] + r["width"] and r["y"] <= (point[1] - 12) / height <= r["y"] + r["height"]:
                    self.mask_tree.selection_set(field["id"])
                    self._mask_selected()
                    return
            return
        self.design_start = point
        self.design_drag_item = self.canvas.create_rectangle(*point, *point, outline="#d16a18", width=3, dash=(5, 3))

    def _mask_motion(self, event):
        if self.design_start and self.design_drag_item is not None:
            self.canvas.coords(self.design_drag_item, *self.design_start, self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _mask_end(self, event):
        if not self.design_start or not self.display_size or self.busy:
            return
        try:
            region = normalized_drag(self.design_start, (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)), *self.display_size, self.page)
        except InputError as exc:
            self.design_help.set(str(exc))
            self._reset_gesture()
            return
        self._reset_gesture()
        self._add_mask(region, redraw=self.design_tool == "redraw")

    def _add_mask(self, region, redraw=False):
        if self.busy or self.design_draft is None:
            return
        region = validate_region(region)
        if redraw:
            field = next((f for f in self.design_draft["fields"] if f["id"] == self.design_selected), None)
            if field:
                field["region"] = region
        else:
            key = uuid.uuid4().hex
            number = len(self.design_draft["fields"]) + 1
            used = {f["name"] for f in self.design_draft["fields"]}
            while f"field_{number}" in used:
                number += 1
            self.design_draft["fields"].append({"id": key, "name": f"field_{number}", "label": f"Field {number}", "type": "text", "required": False, "aliases": [], "region": region})
            self.design_selected = key
        self.design_tool = None
        self.canvas.configure(cursor="")
        self._draft_unsent = True
        self._persist_design()

    def add_mask_coordinates(self):
        if self.busy or self.design_draft is None or not self.design_draft["pages"]:
            self.status.set("Import a PDF or image and open Design masks first.")
            return
        self._persist_design(self._open_mask_coordinates)

    def _open_mask_coordinates(self):
        if self.busy or self.design_draft is None:
            return
        field = next((f for f in self.design_draft["fields"] if f["id"] == self.design_selected), {})
        region = field.get("region", {"page": self.page, "x": 0, "y": 0, "width": .2, "height": .05})
        dialog = tk.Toplevel(self.root)
        dialog.title("Add mask by coordinates")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Add an answer mask", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Percentages of the full page, measured from the top left.\nTab moves between fields; Enter adds the mask.", style="Small.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 12))
        variables = {}
        first = None
        for row, (key, label) in enumerate((("page", "Page"), ("x", "Left (%)"), ("y", "Top (%)"), ("width", "Width (%)"), ("height", "Height (%)")), 2):
            variables[key] = tk.StringVar(value=str(region[key]) if key == "page" else f'{region[key] * 100:.6g}')
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4)
            entry = ttk.Entry(frame, textvariable=variables[key], width=16)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            first = first or entry
        error = tk.StringVar()
        ttk.Label(frame, textvariable=error, style="Error.TLabel", wraplength=390).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        actions = ttk.Frame(frame)
        actions.grid(row=8, column=0, columnspan=2, sticky="e", pady=(6, 0))
        def add(_event=None):
            try:
                new_region = percentage_region(*(variables[key].get() for key in ("page", "x", "y", "width", "height")), len(self.design_draft["pages"]))
            except InputError as exc:
                error.set(str(exc))
                return "break"
            dialog.destroy()
            self.page = new_region["page"]
            self._add_mask(new_region)
            return "break"
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Add mask", command=add).pack(side="left")
        dialog.bind("<Return>", add)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()
        dialog.wait_visibility()
        first.focus_force()
        first.selection_range(0, "end")

    def set_selected_value_type(self, kind):
        if not self.busy and self.design_draft is not None and self.design_selected:
            self.design_kind.set(kind)
            self._persist_design()

    def use_selected_identifier(self):
        if self.busy or self.design_draft is None or not self.design_selected:
            return
        if self.design_kind.get() != "text":
            self.design_help.set("Choose Text in Selected value type before using this field as the identifier.")
            return
        self.design_required.set(True)
        self.design_identifier.set(True)
        self._persist_design()

    def delete_mask(self):
        if self.busy or self.design_draft is None or not self.design_selected:
            return
        self.design_draft["fields"] = [f for f in self.design_draft["fields"] if f["id"] != self.design_selected]
        if self.design_draft["identifierField"] == self.design_selected:
            self.design_draft["identifierField"] = None
        self.design_selected = None
        self._draft_unsent = True
        self._persist_design()

    def start_design(self):
        if not self.busy:
            self._with_draft(lambda: self._submit("Opening extraction-type designer", lambda: self.session.start_design(self.selected_record)))

    def apply_form_type(self):
        if not self.busy:
            self._persist_design(lambda: self._submit("Applying masks and reprocessing documents", self.session.apply_draft))

    def discard_design(self):
        if not self.busy and self.snapshot.get("draft") is not None:
            if messagebox.askyesno("Discard type draft", "Discard the current mask and field edits? Your committed extraction type and source documents remain in this project.", parent=self.root):
                self._draft_unsent = False
                self._submit("Discarding extraction-type draft", self.session.discard_draft)

    def save_form_type(self):
        if self.busy:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Save reusable extraction type (rules only)", defaultextension=".json", initialfile="extraction-type.json", filetypes=[("Extraction type", "*.json")])
        if path:
            self._persist_design(lambda: self._submit("Saving reusable extraction type", lambda: self.session.save_form_type(path), lambda _: self.status.set("Extraction type saved. It contains rules and masks only; load it for matching forms.")))

    def load_form_type(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Load reusable extraction type", filetypes=[("Extraction type", "*.json")])
        if path and self._confirm_schema_change():
            self._with_draft(lambda: self._submit("Loading extraction type and reprocessing documents", lambda: self.session.load_form_type(path)))

    def _build_spreadsheet(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=3)
        parent.rowconfigure(5, minsize=74)
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Import XLSX / CSV…", command=self.import_template).pack(side="left")
        ttk.Button(toolbar, text="Use categories as columns", command=lambda: self._with_draft(lambda: self._submit("Preparing category columns", self.session.use_categories_as_columns))).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Friendly example", command=lambda: self.load_template_sample("friendly")).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Raw example", command=lambda: self.load_template_sample("raw")).pack(side="left")
        ttk.Label(parent, textvariable=self.mapping_label, style="Heading.TLabel", width=1).grid(row=1, column=0, sticky="ew", pady=5)
        configure = ttk.Frame(parent)
        configure.grid(row=2, column=0, sticky="ew", pady=(0, 9))
        ttk.Label(configure, text="Worksheet", style="Small.TLabel").pack(side="left")
        self.sheet_combo = ttk.Combobox(configure, textvariable=self.sheet_var, state="readonly", width=20)
        self.sheet_combo.pack(side="left", padx=6)
        ttk.Label(configure, text="Header row", style="Small.TLabel").pack(side="left")
        ttk.Spinbox(configure, from_=1, to=2000, textvariable=self.header_var, width=5).pack(side="left", padx=6)
        ttk.Button(configure, text="Apply sheet / row", command=self.configure_template).pack(side="left")
        ttk.Label(configure, text="Changing these clears column assignments.", style="Small.TLabel").pack(side="left", padx=12)
        upper_viewport = ttk.Frame(parent)
        upper_viewport.grid(row=3, column=0, sticky="nsew")
        upper_viewport.rowconfigure(0, weight=1)
        upper_viewport.columnconfigure(0, weight=1)
        upper_canvas = tk.Canvas(upper_viewport, width=1, height=1, highlightthickness=0,
                                background="#f2f4f7", yscrollincrement=16)
        upper_scroll = ttk.Scrollbar(upper_viewport, orient="vertical", command=upper_canvas.yview)
        upper_canvas.configure(yscrollcommand=upper_scroll.set)
        upper_canvas.grid(row=0, column=0, sticky="nsew")
        upper_scroll.grid(row=0, column=1, sticky="ns")
        upper = ttk.Panedwindow(upper_canvas, orient="horizontal")
        upper_window = upper_canvas.create_window(0, 0, anchor="nw", window=upper)
        def size_upper(_event=None):
            upper_canvas.itemconfigure(upper_window, width=upper_canvas.winfo_width(),
                                       height=max(upper.winfo_reqheight(), upper_canvas.winfo_height()))
            upper_canvas.configure(scrollregion=upper_canvas.bbox(upper_window))
        self._size_spreadsheet_upper = size_upper
        upper_canvas.bind("<Configure>", size_upper)
        upper_canvas.bind("<MouseWheel>", lambda event: upper_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        sources = ttk.Frame(upper, padding=4)
        destinations = ttk.Frame(upper, padding=4)
        assignment = ttk.Frame(upper, padding=(12, 4))
        upper.add(sources, weight=2)
        upper.add(destinations, weight=4)
        upper.add(assignment, weight=3)
        def upper_changed(_event=None):
            self._constrain_panes(upper, 200, 260, 280)
            size_upper()
        upper.bind("<Configure>", upper_changed)
        for pane in (sources, destinations):
            pane.columnconfigure(0, weight=1)
            pane.rowconfigure(1, weight=1)
        ttk.Label(sources, text="Source categories", style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        frame, self.source_tree = self._tree(sources, ("label", "name"), ("Label", "Variable"), (140, 110), 1)
        frame.grid(row=1, column=0, sticky="nsew")
        self.source_tree.bind("<ButtonPress-1>", self._drag_start)
        self.source_tree.bind("<ButtonRelease-1>", self._drag_drop)
        ttk.Label(sources, text="Drag a category to a destination, or select a destination and use its dropdown.", style="Small.TLabel", wraplength=240).grid(row=2, column=0, sticky="ew", pady=6)
        ttk.Label(destinations, text="Destination columns", style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        frame, self.destination_tree = self._tree(destinations, ("column", "source", "example"), ("Column", "Assigned category", "Example value"), (160, 150, 130), 1)
        frame.grid(row=1, column=0, sticky="nsew")
        self.destination_tree.bind("<<TreeviewSelect>>", self._destination_selected)
        ttk.Label(assignment, text="Assign selected column", style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(assignment, textvariable=self.mapping_column, wraplength=250).pack(anchor="w", pady=2)
        self.mapping_combo = ttk.Combobox(assignment, textvariable=self.mapping_choice, state="readonly")
        self.mapping_combo.pack(fill="x", pady=3)
        self.mapping_combo.bind("<<ComboboxSelected>>", self.assign_column)
        ttk.Label(assignment, textvariable=self.example_value, style="Small.TLabel", wraplength=250).pack(fill="x", pady=3)
        ttk.Button(assignment, text="Use suggested assignments", command=self.suggest_mapping).pack(fill="x", pady=(6, 3))
        ttk.Button(assignment, text="Confirm column mapping", command=self.confirm_mapping).pack(fill="x", pady=3)
        self.mapping_state = ttk.Label(assignment, text="Mapping is unconfirmed", style="Small.TLabel", wraplength=250)
        self.mapping_state.pack(fill="x", pady=4)
        ttk.Label(parent, text="Populated preview — select a row to change the example values above", style="Heading.TLabel").grid(row=4, column=0, sticky="w", pady=(8, 5))
        frame, self.preview_tree = self._tree(parent, ("state",), ("Status",), (120,), 1)
        frame.grid(row=5, column=0, sticky="nsew")
        self.preview_tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_destinations())
        self._messages(parent, self.mapping_errors).grid(row=6, column=0, sticky="ew", pady=6)
        bottom = ttk.Frame(parent)
        bottom.grid(row=7, column=0, sticky="ew", pady=(4, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.export_help, style="Small.TLabel", wraplength=600).grid(row=0, column=0, sticky="w")
        self.export_csv_button = ttk.Button(bottom, text="Export CSV…", command=lambda: self.export("csv"))
        self.export_csv_button.grid(row=0, column=2, padx=5)
        self.export_xlsx_button = ttk.Button(bottom, text="Export XLSX…", command=lambda: self.export("xlsx"))
        self.export_xlsx_button.grid(row=0, column=1, padx=5)

    def _build_menu(self):
        menu = tk.Menu(self.root)
        modifier = "Control" if os.name == "nt" else "Command"
        prefix = "Ctrl+" if os.name == "nt" else "⌘"
        def add(target, label, command, key=None, display=None):
            options = {"label": label, "command": command}
            if key:
                options["accelerator"] = prefix + (display or key.upper())
                def shortcut(_event, action=command):
                    action()
                    return "break"
                self.root.bind(f"<{modifier}-{key}>", shortcut)
            target.add_command(**options)
        file_menu = tk.Menu(menu, tearoff=False)
        for label, command in [("New project", self.new_project), ("Open project…", self.open_project), ("Save project", self.save_project), ("Save project as…", lambda: self.save_project(save_as=True)), ("Import forms…", self.import_forms)]:
            file_menu.add_command(label=label, command=command)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.request_close)
        menu.add_cascade(label="File", menu=file_menu)
        type_menu = tk.Menu(menu, tearoff=False)
        for label, action in (("Design masks", self.start_design), ("Draw new field", lambda: self._set_mask_tool("new")),
                              ("Add mask by coordinates…", self.add_mask_coordinates),
                              ("Redraw selected field", lambda: self._set_mask_tool("redraw")), ("Delete selected field", self.delete_mask),
                              ("Apply extraction type", self.apply_form_type), ("Save extraction type…", self.save_form_type),
                              ("Load extraction type…", self.load_form_type),
                              ("Edit type name", lambda: self._focus_editor(self.type_name_entry)),
                              ("Edit field name", lambda: self._focus_editor(self.design_name_entry))):
            add(type_menu, label, action)
        add(type_menu, "Use selected field as record identifier", self.use_selected_identifier)
        value_type_menu = tk.Menu(type_menu, tearoff=False)
        for kind in ("text", "integer", "number", "date", "choice"):
            add(value_type_menu, kind.title(), lambda selected=kind: self.set_selected_value_type(selected))
        type_menu.add_cascade(label="Selected value type", menu=value_type_menu)
        menu.add_cascade(label="Form type", menu=type_menu)
        review_menu = tk.Menu(menu, tearoff=False)
        add(review_menu, "Show review forms", lambda: self.show_tab(0), "1")
        review_menu.add_separator()
        add(review_menu, "Previous document", lambda: self.move_document(-1))
        add(review_menu, "Next document", lambda: self.move_document(1))
        add(review_menu, "Previous field", lambda: self.move_field(-1), "bracketleft", "[")
        add(review_menu, "Next field", lambda: self.move_field(1), "bracketright", "]")
        add(review_menu, "Confirm current field against source and next", self.confirm_and_next, "k")
        add(review_menu, "Save review draft", self.save_review)
        add(review_menu, "Edit current answer", self.focus_answer)
        add(review_menu, "Expand text answer…", self.expand_answer)
        add(review_menu, "Edit reviewer name", lambda: self.focus_answer(reviewer=True))
        add(review_menu, "Approve document", self.approve_record, "Shift-A", "⇧A")
        review_menu.add_separator()
        add(review_menu, "Previous source page", lambda: self.change_page(-1))
        add(review_menu, "Next source page", lambda: self.change_page(1))
        add(review_menu, "Scroll source up", lambda: self.scroll_source(-1))
        add(review_menu, "Scroll source down", lambda: self.scroll_source(1))
        add(review_menu, "Fit source width", self.fit_page)
        menu.add_cascade(label="Review", menu=review_menu)
        spreadsheet_menu = tk.Menu(menu, tearoff=False)
        add(spreadsheet_menu, "Show categories and spreadsheet", lambda: self.show_tab(1), "2")
        add(spreadsheet_menu, "Import XLSX / CSV…", self.import_template)
        add(spreadsheet_menu, "Use categories as columns", lambda: self._with_draft(lambda: self._submit("Preparing category columns", self.session.use_categories_as_columns)))
        sample_menu = tk.Menu(spreadsheet_menu, tearoff=False)
        add(sample_menu, "Friendly example", lambda: self.load_template_sample("friendly"))
        add(sample_menu, "Raw example", lambda: self.load_template_sample("raw"))
        spreadsheet_menu.add_cascade(label="Load fictional sample template", menu=sample_menu)
        spreadsheet_menu.add_separator()
        add(spreadsheet_menu, "Use suggested assignments", self.suggest_mapping)
        add(spreadsheet_menu, "Confirm column mapping", self.confirm_mapping)
        spreadsheet_menu.add_separator()
        self.export_menu_entries = []
        add(spreadsheet_menu, "Export CSV…", lambda: self.export("csv"))
        self.export_menu_entries.append((spreadsheet_menu, spreadsheet_menu.index("end"), "csv"))
        add(spreadsheet_menu, "Export XLSX…", lambda: self.export("xlsx"))
        self.export_menu_entries.append((spreadsheet_menu, spreadsheet_menu.index("end"), "xlsx"))
        menu.add_cascade(label="Spreadsheet", menu=spreadsheet_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label=f"About {PRODUCT_NAME}", command=lambda: messagebox.showinfo(PRODUCT_NAME, OWNERSHIP_NOTICE + "\n\nNative local form review and spreadsheet mapping.\n\nUpload a PDF or image, draw masks around answer areas and name the fields you need. Save a reusable named extraction type containing only rules and masks.\n\nReview and confirm every answer against its source, then approve records before spreadsheet export. Matching page shapes do not establish that two documents use the same layout.\n\nProjects retain original documents, answers and unfinished type drafts; reopening requires fresh review.", parent=self.root))
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menu)

    def _domain_loop(self):
        while True:
            command = self.commands.get()
            if command is None:
                return
            operation_id, function = command
            try:
                result = function()
                state = self.session.snapshot() if not self.session.closed else None
                event = ("done", operation_id, result, state)
            except Exception as exc:
                # Do not log source paths, payloads, tracebacks or document contents.
                text = str(exc)[:500] if isinstance(exc, (InputError, ValueError)) else "The operation could not be completed. Check the file and try again."
                event = ("error", operation_id, text, self.session.snapshot() if not self.session.closed else None)
            finally:
                self.session.end_operation()
            self.events.put(event)

    def _submit(self, title, function, callback=None):
        if self.busy or self.closing:
            return False
        self.session.begin_operation()
        self.busy = True
        self._operation_id += 1
        self._callback = callback
        self.status.set(title + "…")
        self._set_busy(True)
        self.commands.put((self._operation_id, function))
        return True

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    if event[1] == self._operation_id:
                        self.status.set(f"Processing document {event[2]} of {event[3]}…")
                    continue
                kind, operation_id, result, state = event
                if operation_id != self._operation_id:
                    continue
                callback, self._callback = self._callback, None
                self.busy = False
                self._set_busy(False)
                if state is not None:
                    self._render(state)
                if self.closing:
                    if kind == "error":
                        messagebox.showwarning("Workspace cleanup", "The workspace could not be fully cleaned up. Local temporary files may remain. Close the app and remove them when no processing is running.", parent=self.root)
                    self._finish_close()
                    return
                if self._after_busy:
                    action, self._after_busy = self._after_busy, None
                    action()
                    continue
                if kind == "error":
                    self.status.set(result)
                    messagebox.showerror(PRODUCT_NAME, result, parent=self.root)
                else:
                    self.status.set("Ready.")
                    if callback:
                        callback(result)
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    def _set_busy(self, busy):
        if busy:
            self._disabled_states = []
            def disable(widget):
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Checkbutton, ttk.Spinbox)) and child is not getattr(self, "cancel_button", None):
                        self._disabled_states.append((child, child.state()))
                        child.state(["disabled"])
                    disable(child)
            disable(self.root)
            self.progress.start(15)
            self.cancel_button.state(["!disabled"])
            self._set_export_controls(False)
        else:
            for widget, old in self._disabled_states:
                if widget.winfo_exists():
                    widget.state(["!disabled"])
                    widget.state(old)
            self._disabled_states = []
            self.progress.stop()
            self.cancel_button.state(["disabled"])

    def _render(self, state):
        self._rendering = True
        self.snapshot = state
        ids = {r["id"] for r in state["records"]}
        if self.selected_record not in ids:
            self.selected_record = state["records"][0]["id"] if state["records"] else None
            self.selected_field = None
            self.page = 1
        self.queue_tree.delete(*self.queue_tree.get_children())
        staging = state.get("profile") == "neurology-training-v1"
        if staging:
            self.mode_label.set("Staging export • source MRN groups assessments\nStudy REDCap mapping pending")
            columns = ("document", "state")
            headings = ("Assessment", "Review")
            widths = (155, 75)
        else:
            definition = state.get("formType")
            self.mode_label.set("LOCAL DESKTOP · " + state.get("phase", "review").upper() + "\n" + (definition["name"] if definition else "Create your own extraction type"))
            columns, headings, widths = ("document", "state"), ("Document", "Review"), (145, 85)
        self.queue_tree.configure(columns=columns)
        self.queue_tree.configure(style="StagingQueue.Treeview" if staging else "Treeview")
        for name, heading, width in zip(columns, headings, widths):
            self.queue_tree.heading(name, text=heading)
            self.queue_tree.column(name, width=width, minwidth=75 if staging and name == "state" else 65, stretch=not (staging and name == "state"))
        approved = 0
        for record in state["records"]:
            approved += record["status"] == "approved"
            applicable = set(record.get("applicableFields", [field["name"] for field in state["schema"]]))
            checked = len(set(record["confirmed"]) & applicable)
            review = "Approved" if record["status"] == "approved" else f"{checked}/{len(applicable)}" + ("" if staging else " checked")
            if not state["schema"]:
                review = "Setup"
            if record.get("groupConflict") or record.get("profileBlockingIssues"):
                review = "Conflict" if staging else review + " • conflict"
            values = record["values"]
            filename = record["filename"]
            if staging:
                concise = filename if len(filename) <= 22 else filename[:12] + "…" + filename[-9:]
                details = " · ".join(value for value in (values.get("instrument_family", ""), values.get("form_date", "")) if value)
                row = (concise + ("\n" + details if details else ""), review)
            else:
                row = (filename, review)
            self.queue_tree.insert("", "end", iid=record["id"], values=row)
        if staging:
            groups = state.get("patientGroups", [])
            conflicts = sum(bool(group.get("conflict")) for group in groups)
            self.queue_label.set(f'{len(ids)} documents · {len(groups)} MRN groups\n{approved} approved · {conflicts} group conflicts')
        else:
            self.queue_label.set(f'{len(ids)} documents · {approved} approved')
        if self.selected_record:
            self.queue_tree.selection_set(self.selected_record)
        self.reviewer_var.set(state.get("reviewer", self.reviewer_var.get()))
        path = state.get("projectPath")
        self.project_label.configure(text=(Path(path).name if path else "Unsaved project") + ("  •" if state["dirty"] else ""))
        self.editor_dirty = False
        record = self._record()
        self.review_values = dict(record["values"]) if record else {}
        self.review_confirmed = set(record["confirmed"]) if record else set()
        self.mappings = dict(state["template"]["mappings"]) if state.get("template") else {}
        self.mapping_dirty = False
        self._render_designer()
        self._render_fields()
        self._render_page()
        self._render_spreadsheet()
        self._rendering = False

    def _record(self):
        return next((r for r in self.snapshot["records"] if r["id"] == self.selected_record), None)

    def _active_fields(self):
        record = self._record()
        applicable = record.get("applicableFields") if record else None
        names = set(applicable) if applicable is not None else None
        fields = [field for field in self.snapshot["schema"] if names is None or field["name"] in names]
        if self.snapshot.get("profile"):
            fields.sort(key=lambda field: field["name"] == "document_id")
        return fields

    def _queue_selected(self, _event=None):
        if self._rendering or self.busy:
            return
        selection = self.queue_tree.selection()
        if not selection or selection[0] == self.selected_record:
            return
        target = selection[0]
        self._with_draft(lambda: self._select_record(target))

    def _select_record(self, record_id):
        self.selected_record = record_id
        self.selected_field = None
        self.page = 1
        self._render(self.snapshot)

    def move_document(self, delta):
        if self.busy or self.closing:
            return
        ids = [record["id"] for record in self.snapshot["records"]]
        if not ids:
            return
        index = ids.index(self.selected_record) if self.selected_record in ids else 0
        target = ids[max(0, min(len(ids) - 1, index + delta))]
        if target != self.selected_record:
            self._with_draft(lambda: self._select_record(target))

    def _render_fields(self):
        self.field_tree.delete(*self.field_tree.get_children())
        fields = self._active_fields()
        for field in fields:
            self.field_tree.insert("", "end", iid=field["name"], values=(field["label"], self.review_values.get(field["name"], ""), "✓" if field["name"] in self.review_confirmed else ""))
        names = {field["name"] for field in fields}
        if self.selected_field not in names:
            self.selected_field = "patient_mrn" if self.snapshot.get("profile") and "patient_mrn" in names else fields[0]["name"] if fields else None
        if self.selected_field is None:
            self.field_title.set("No applicable fields")
            self.value_var.set("")
            return
        self.field_tree.selection_set(self.selected_field)
        self._show_field()

    def _field_selected(self, _event=None):
        if self._rendering or self.busy:
            return
        selection = self.field_tree.selection()
        if selection and selection[0] in {field["name"] for field in self._active_fields()}:
            self.selected_field = selection[0]
            self._show_field()
            record = self._record()
            evidence = record.get("evidence", {}).get(self.selected_field) if record else None
            field = next(f for f in self.snapshot["schema"] if f["name"] == self.selected_field)
            page = (evidence or {}).get("page", (field.get("region") or {}).get("page"))
            if page:
                self.page = page
            self._render_page()

    def move_field(self, delta):
        if self.busy or self.closing:
            return
        names = [field["name"] for field in self._active_fields()]
        if not names:
            return
        index = names.index(self.selected_field) if self.selected_field in names else 0
        target = names[max(0, min(len(names) - 1, index + delta))]
        self.field_tree.selection_set(target)
        self.field_tree.focus(target)
        self.field_tree.see(target)
        self._field_selected()

    def confirm_and_next(self):
        if self.busy or self.closing or not self._record() or not self.selected_field:
            return
        command = self._review_command(confirm=(self.selected_field, True))
        self._submit("Saving current field confirmation", command, lambda _: self.move_field(1))

    def show_tab(self, index):
        self.notebook.select(index)
        # Keep a hidden answer editor from retaining focus after navigation.
        self.notebook.focus_set()

    def focus_answer(self, reviewer=False):
        if self.busy or self.closing:
            return
        field = next((field for field in self.snapshot["schema"] if field["name"] == self.selected_field), {})
        widget = self.reviewer_entry if reviewer else self.choice if field.get("type") == "choice" else self.entry
        self._focus_editor(widget)

    def _focus_editor(self, widget):
        if self.busy or self.closing:
            return
        self.show_tab(0)
        def focus():
            if not self.busy and not self.closing and widget.winfo_exists() and widget.winfo_ismapped():
                self.root.lift()
                widget.focus_force()
                widget.selection_range(0, "end")
        # Native menu dismissal restores the old focus after its command returns.
        self.root.after_idle(focus)

    def expand_answer(self):
        if self.busy or self.closing or not self._record():
            return
        field = next((field for field in self._active_fields() if field["name"] == self.selected_field), None)
        if not field or field["type"] != "text":
            self.status.set("Expanded editing is available for text answers. Use the current field control for other types.")
            return
        selected = (self.selected_record, self.selected_field)
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit answer • " + field["label"])
        dialog.geometry("720x460")
        dialog.minsize(440, 280)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text=field["label"], style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        editor = tk.Text(frame, wrap="word", undo=True, width=1, height=1, padx=10, pady=10)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        editor.configure(yscrollcommand=scroll.set)
        editor.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        editor.insert("1.0", self.value_var.get())
        ttk.Label(frame, text="Applying an edit clears this field's confirmation. Check the complete answer against its source.", style="Small.TLabel", wraplength=640).grid(row=2, column=0, sticky="w", pady=8)
        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, sticky="e")
        def apply(_event=None):
            if self.busy or self.closing:
                return "break"
            if selected != (self.selected_record, self.selected_field):
                messagebox.showwarning("Selection changed", "Reopen the expanded editor for the currently selected field.", parent=dialog)
                return "break"
            self.value_var.set(editor.get("1.0", "end-1c"))
            dialog.destroy()
            return "break"
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)
        ttk.Button(buttons, text="Apply answer", command=apply).pack(side="left")
        dialog.bind("<Control-Return>" if os.name == "nt" else "<Command-Return>", apply)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.lift()
        dialog.focus_force()
        editor.focus_set()

    def _show_field(self):
        field = next((f for f in self.snapshot["schema"] if f["name"] == self.selected_field), None)
        if not field:
            return
        self._rendering = True
        self.field_title.set(field["label"])
        value = self.review_values.get(field["name"], "")
        self.entry.pack_forget()
        self.choice.pack_forget()
        if field["type"] == "choice":
            self._choice_codes = {f'{label} ({code})': code for code, label in field["choices"].items()}
            self.choice.configure(values=[""] + list(self._choice_codes))
            self.value_var.set(next((label for label, code in self._choice_codes.items() if code == value), value))
            self.choice.pack(fill="x", pady=4, before=self.confirm_check)
        else:
            self.value_var.set(value)
            self.entry.pack(fill="x", pady=4, before=self.confirm_check)
        self.confirm_var.set(field["name"] in self.review_confirmed)
        errors = validate_values(self.snapshot["schema"], self.review_values) if self._record() else {}
        detail = errors.get(field["name"], f'{field["name"]} · {field["type"]}' + (" · required" if field["required"] else " · optional"))
        if self.snapshot.get("profile") and field["name"] == "document_id" and field["name"] not in errors:
            detail = "Derived source reference; no PDF region. Review identity fields separately."
        self.field_detail.set(detail)
        self._rendering = False

    def _value_changed(self, *_):
        if self._rendering or self.busy or not self._record() or not self.selected_field:
            return
        field = next(f for f in self.snapshot["schema"] if f["name"] == self.selected_field)
        value = self.value_var.get()
        if field["type"] == "choice":
            value = getattr(self, "_choice_codes", {}).get(value, value)
        if self.review_values.get(field["name"]) != value:
            self.review_values[field["name"]] = value
            self.review_confirmed.discard(field["name"])
            self.confirm_var.set(False)
            self.editor_dirty = True
            self.field_tree.set(field["name"], "value", value)
            self.field_tree.set(field["name"], "check", "")
            self.queue_tree.set(self.selected_record, "state", "Draft" if self.snapshot.get("profile") == "neurology-training-v1" else "Unsaved draft")
            self.field_detail.set(validate_values(self.snapshot["schema"], self.review_values).get(field["name"], "Value changed. Save and confirm it against the source."))
            self.status.set("Unsaved answer edit. Prior approval will be cleared when saved.")
            self._set_export_controls(False)

    def _review_command(self, *, confirm=None, approve=False):
        record = self._record()
        if not record:
            return None
        rid, values = record["id"], dict(self.review_values)
        confirmed = list(self.review_confirmed)
        reviewer = self.reviewer_var.get()
        expected = record["revision"]
        def execute():
            saved = self.session.review_record(rid, values, confirmed, reviewer, False, expected)
            final_confirmed = set(saved["confirmed"])
            if confirm is not None:
                name, checked = confirm
                if checked:
                    final_confirmed.add(name)
                else:
                    final_confirmed.discard(name)
            if confirm is not None or approve:
                return self.session.review_record(rid, saved["values"], list(final_confirmed), reviewer, approve, saved["revision"])
            return saved
        return execute

    def save_review(self, callback=None):
        if self.busy:
            return
        command = self._review_command()
        if command:
            self._submit("Saving review draft", command, callback)

    def confirm_field(self):
        if self.busy or not self._record():
            return
        command = self._review_command(confirm=(self.selected_field, self.confirm_var.get()))
        self._submit("Saving field confirmation", command)

    def approve_record(self):
        if self.busy or not self._record():
            return
        self._submit("Approving reviewed document", self._review_command(approve=True))

    def _with_draft(self, action):
        if self._draft_unsent:
            self._persist_design(lambda: self._with_draft(action))
            return
        if self.busy:
            return
        reviewer_dirty = self._record() is not None and self.reviewer_var.get() != self.snapshot.get("reviewer", "")
        if self.editor_dirty or reviewer_dirty:
            self.save_review(lambda _: action())
        else:
            action()

    def _preview_resize(self, _event=None):
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(130, self._render_page)

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def change_page(self, delta):
        self._reset_gesture()
        record = self._record()
        if record and record.get("pages"):
            self.page = max(1, min(len(record["pages"]), self.page + delta))
            self._render_page()

    def scroll_source(self, delta):
        record = self._record()
        if record:
            source = self.canvas if record.get("pages") else self.source_text
            source.yview_scroll(delta, "pages")

    def change_zoom(self, factor):
        self._reset_gesture()
        self.fit_width = False
        self.zoom = max(.15, min(3, self.zoom * factor))
        self._render_page()

    def fit_page(self):
        self._reset_gesture()
        self.fit_width = True
        self._render_page()

    def _render_page(self):
        self._resize_after = None
        self.canvas.delete("all")
        self._reset_gesture()
        self.display_size = None
        self.photo = None
        record = self._record()
        self.source_text.grid_remove()
        self.canvas.grid()
        self.page_yscroll.configure(command=self.canvas.yview)
        self.page_xscroll.configure(command=self.canvas.xview)
        if not record:
            self.record_title.set("Source document")
            self.record_context_label.grid_remove()
            self.page_label.set("No document selected")
            self.source_issues.set("")
            self.canvas.create_text(max(140, self.canvas.winfo_width() / 2), 150, text="Import a form to review its source here.", fill="#617084", font=("Helvetica Neue", 13), width=300)
            return
        self.record_title.set(record["filename"])
        if self.snapshot.get("profile") == "neurology-training-v1":
            values = self.review_values
            self.record_context.set(f'MRN {values.get("patient_mrn", "")} · {values.get("patient_name", "")} · DOB {values.get("patient_dob", "")}\n{values.get("instrument_family", "")} · form date {values.get("form_date", "")}')
            self.record_context_label.grid()
        else:
            self.record_context_label.grid_remove()
        issues = list(dict.fromkeys(record.get("formTypeIssues", []) + record.get("issues", []) + record.get("groupConflicts", []) + record.get("profileBlockingIssues", [])))
        self.source_issues.set("\n".join(issues))
        pages = record.get("pages", [])
        if not pages:
            self.canvas.grid_remove()
            self.source_text.grid(row=0, column=0, sticky="nsew")
            self.page_yscroll.configure(command=self.source_text.yview)
            self.page_xscroll.configure(command=self.source_text.xview)
            self.source_text.configure(state="normal")
            self.source_text.delete("1.0", "end")
            self.source_text.insert("1.0", record.get("sourceText", "No text preview available."))
            self.source_text.configure(state="disabled")
            self.page_label.set("Text source")
            return
        self.page = max(1, min(len(pages), self.page))
        path = record.get("pagePaths", {}).get(str(self.page))
        if not path:
            self.page_label.set("Page preview unavailable")
            return
        try:
            with Image.open(path) as source:
                width, height = source.size
                if self.fit_width:
                    self.zoom = max(.1, min(2, (max(200, self.canvas.winfo_width()) - 28) / width))
                display = source.resize((max(1, round(width * self.zoom)), max(1, round(height * self.zoom))), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(display, master=self.root)
            self.display_size = (display.width, display.height)
            self.canvas.create_image(12, 12, image=self.photo, anchor="nw")
            self.canvas.configure(scrollregion=(0, 0, display.width + 24, display.height + 24))
            self.page_label.set(f"Page {self.page} / {len(pages)} · {round(self.zoom * 100)}%")
            if self.design_draft is not None:
                for field in self.design_draft["fields"]:
                    region = field.get("region")
                    if region and region["page"] == self.page:
                        selected = field["id"] == self.design_selected
                        x1, y1 = 12 + region["x"] * display.width, 12 + region["y"] * display.height
                        self.canvas.create_rectangle(x1, y1, x1 + region["width"] * display.width, y1 + region["height"] * display.height, outline="#d16a18" if selected else "#147d9b", width=3 if selected else 2)
                        self.canvas.create_text(x1 + 3, y1 + 2, text=field.get("name", ""), anchor="nw", fill="#9b460c" if selected else "#08617a", font=("Helvetica Neue", 10, "bold"))
                return
            field = next((f for f in self.snapshot["schema"] if f["name"] == self.selected_field), {})
            evidence = record.get("evidence", {}).get(self.selected_field, {})
            region = evidence.get("region") or field.get("region")
            page = evidence.get("page") or (region or {}).get("page")
            if region and page == self.page:
                x1, y1 = 12 + region["x"] * display.width, 12 + region["y"] * display.height
                x2, y2 = x1 + region["width"] * display.width, y1 + region["height"] * display.height
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="#147d9b", width=3)
        except (OSError, ValueError, tk.TclError):
            self.page_label.set("Page preview unavailable")

    def import_forms(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title="Import forms", filetypes=[("Forms", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.txt"), ("All files", "*")])
        if paths:
            self._with_draft(lambda: self._import_paths(paths))

    def _import_paths(self, paths):
        operation_id = self._operation_id + 1
        def progress(current, total):
            self.events.put(("progress", operation_id, current, total))
        def complete(result):
            if result["failed"]:
                lines = [f'{failure["filename"]}: {failure["error"]}' for failure in result["failed"]]
                messagebox.showwarning("Import summary", f'Imported {len(result["added"])} document(s).\n\n' + "\n".join(lines), parent=self.root)
            else:
                self.status.set(f'Imported {len(result["added"])} document(s). Review every answer against the source.')
        self._submit("Processing forms", lambda: self.session.import_documents(paths, progress), complete)

    def import_example(self):
        self._with_draft(lambda: self._import_paths([ROOT / "samples/practice-01-text.pdf"]))

    def use_neurology_profile(self):
        if self.busy or self.closing:
            return
        if self._confirm_schema_change():
            self._with_draft(lambda: self._submit("Preparing neurology training staging categories", self.session.use_neurology_profile))

    def remove_document(self):
        if self.busy or not self.selected_record:
            return
        if messagebox.askyesno("Remove document", "Remove the selected document and its review from this project?", parent=self.root):
            rid = self.selected_record
            self._submit("Removing document", lambda: self.session.remove_document(rid))

    def import_dictionary(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Import categories / REDCap dictionary (replaces current categories)", filetypes=[("Category definitions", "*.csv *.json"), ("All files", "*")])
        if path and self._confirm_schema_change(custom=True):
            self._with_draft(lambda: self._submit("Applying categories and reprocessing sources", lambda: self.session.import_dictionary(path)))

    def _confirm_schema_change(self, custom=False):
        text = "Changing extraction rules replaces the current type draft, reprocesses every document and clears field confirmations, approvals and mapping confirmation."
        if custom and self.snapshot.get("profile"):
            text += " Custom categories leave neurology staging mode. An explicitly marked built-in profile dictionary retains its profile mode."
        return not (self.snapshot["records"] or self.snapshot.get("draft") or self._draft_unsent) or messagebox.askyesno("Reprocess sources", text + " Continue?", parent=self.root)

    def edit_categories(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit categories")
        dialog.geometry("900x580")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Your form's categories", style="Heading.TLabel").pack(anchor="w")
        if self.snapshot.get("profile"):
            ttk.Label(frame, text="Applying custom categories leaves neurology staging mode and removes its profile rules.", style="Error.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(frame, text="One line per field: variable_name | Human label | type | required | choices\nTypes: text, date, integer, number, choice. Choices: 1=Yes;0=No. The first field is your required text identifier.\nExisting aliases, regions and numeric bounds are retained for matching variable names.", style="Small.TLabel").pack(anchor="w", pady=8)
        editor = tk.Text(frame, wrap="none", undo=True, padx=10, pady=10, relief="solid", borderwidth=1)
        editor.pack(fill="both", expand=True)
        previous = {f["name"]: copy.deepcopy(f) for f in self.snapshot["schema"]}
        for field in self.snapshot["schema"]:
            choices = ";".join(f"{code}={label}" for code, label in field.get("choices", {}).items())
            editor.insert("end", f'{field["name"]} | {field["label"]} | {field["type"]} | {"yes" if field["required"] else "no"} | {choices}\n')
        error = tk.StringVar()
        ttk.Label(frame, textvariable=error, style="Error.TLabel", wraplength=850).pack(fill="x", pady=5)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=6)
        def apply():
            try:
                from server import parse_schema
                fields = []
                for line in editor.get("1.0", "end").splitlines():
                    if not line.strip():
                        continue
                    parts = [part.strip() for part in line.split("|")]
                    if len(parts) not in {4, 5}:
                        raise InputError("Each line needs variable | label | type | required | choices.")
                    name, label, kind, required = parts[:4]
                    if required.lower() not in {"yes", "no", "true", "false", "y", "n"}:
                        raise InputError("Required must be yes or no.")
                    field = {**previous.get(name, {}), "name": name, "label": label, "type": kind, "required": required.lower() in {"yes", "true", "y"}}
                    field.pop("profile", None)
                    if kind == "choice":
                        choices = {}
                        for item in (parts[4] if len(parts) == 5 else "").split(";"):
                            code, sep, choice_label = item.partition("=")
                            if not sep or code.strip() in choices:
                                raise InputError("Choices need unique code=label pairs, separated by semicolons.")
                            choices[code.strip()] = choice_label.strip()
                        field["choices"] = choices
                    else:
                        field.pop("choices", None)
                    fields.append(field)
                fields = parse_schema(fields)
            except (InputError, ValueError) as exc:
                error.set(str(exc))
                return
            if self._confirm_schema_change(custom=True):
                dialog.destroy()
                self._with_draft(lambda: self._submit("Applying categories and reprocessing sources", lambda: self.session.set_schema(fields)))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Apply categories", command=apply).pack(side="right", padx=8)

    def import_template(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Import blank spreadsheet", filetypes=[("Blank spreadsheets", "*.xlsx *.csv"), ("All files", "*")])
        if path:
            self._with_draft(lambda: self._submit("Inspecting blank spreadsheet", lambda: self.session.import_template(path)))

    def load_template_sample(self, name):
        self._with_draft(lambda: self._submit("Loading fictional spreadsheet", lambda: self.session.load_sample_template(name)))

    def configure_template(self):
        template = self.snapshot.get("template")
        if self.busy or not template:
            return
        try:
            row = int(self.header_var.get())
        except ValueError:
            messagebox.showerror("Header row", "Use a whole row number.", parent=self.root)
            return
        sheet = self.sheet_var.get()
        def perform():
            revision = self.snapshot["template"]["revision"]
            self._submit("Inspecting selected worksheet", lambda: self.session.configure_template(sheet, row, revision))
        self._with_draft(perform)

    def _set_export_controls(self, enabled):
        template = self.snapshot.get("template") or {}
        available = {"csv": bool(enabled), "xlsx": bool(enabled and template.get("format") == "xlsx")}
        for format, button in (("csv", self.export_csv_button), ("xlsx", self.export_xlsx_button)):
            button.state(["!disabled"] if available[format] else ["disabled"])
        for menu, index, format in getattr(self, "export_menu_entries", []):
            menu.entryconfigure(index, state="normal" if available[format] else "disabled")

    def _render_spreadsheet(self):
        schema, template = self.snapshot["schema"], self.snapshot.get("template")
        self.export_help.set("Staging export • source MRN groups assessments; study REDCap mapping pending. Exports include approved records." if self.snapshot.get("profile") else "XLSX retains supported blank-template layout. CSV contains values only. Exports include approved records.")
        self.source_tree.delete(*self.source_tree.get_children())
        self.mapping_display = {f'{f["label"]} ({f["name"]})': f["name"] for f in schema}
        self.mapping_combo.configure(values=["Unassigned", "Leave blank"] + list(self.mapping_display))
        for field in schema:
            self.source_tree.insert("", "end", iid=field["name"], values=(field["label"], field["name"]))
        self.preview_tree.delete(*self.preview_tree.get_children())
        preview = self.snapshot.get("templatePreview")
        if template:
            self.mapping_label.set(f'{template["name"]}  ·  {template["sheet"] or "CSV"}  ·  header row {template["headerRow"]}')
            self.sheet_combo.configure(values=template.get("sheets", [template["sheet"]]) or [template["sheet"]])
            self.sheet_var.set(template["sheet"] or "CSV")
            self.header_var.set(str(template["headerRow"]))
            self.mapping_state.configure(text="Mapping confirmed" if template["confirmed"] else "Mapping unconfirmed — review each assignment")
            columns = [column["name"] for column in template["columns"]]
            keys = ["status"] + [f"c{index}" for index in range(len(columns))]
            self.preview_tree.configure(columns=keys)
            for key, title in zip(keys, ["Review status"] + columns):
                self.preview_tree.heading(key, text=title)
                self.preview_tree.column(key, width=145, minwidth=90, stretch=False)
            for row in preview["rows"]:
                self.preview_tree.insert("", "end", iid=row["id"], values=(["Approved" if row["status"] == "approved" else "Draft"] + [row["values"][col] for col in columns]))
            if self.selected_record and self.preview_tree.exists(self.selected_record):
                self.preview_tree.selection_set(self.selected_record)
            self.mapping_errors.set("\n".join(list(template.get("warnings", [])) + preview["errors"] + self.snapshot.get("schemaWarnings", [])))
        else:
            self.mapping_label.set("Choose a blank spreadsheet or create columns from your categories")
            self.mapping_errors.set("Every destination requires a category or explicit Leave blank. The record identifier must be mapped exactly once.")
            self.sheet_var.set("")
            self.mapping_state.configure(text="No mapping yet")
        if template and template.get("format") == "csv":
            self.export_help.set(self.export_help.get() + " For XLSX export, import an XLSX template or use categories as columns.")
        self._refresh_destinations()
        enabled = bool(preview and preview["ready"] and not self.editor_dirty and not self.busy)
        self._set_export_controls(enabled)
        self.root.after_idle(self._size_spreadsheet_upper)

    def _refresh_destinations(self):
        selected = self.destination_tree.selection()
        self.destination_tree.delete(*self.destination_tree.get_children())
        template = self.snapshot.get("template")
        if not template:
            return
        preview = self.snapshot.get("templatePreview") or {}
        selection = self.preview_tree.selection()
        example = next((r for r in preview.get("rows", []) if selection and r["id"] == selection[0]), None)
        if example is None:
            example = next(iter(preview.get("rows", [])), None)
        source_record = next((r for r in self.snapshot["records"] if example and r["id"] == example["id"]), None)
        self.example_record = source_record
        labels = {f["name"]: f["label"] for f in self.snapshot["schema"]}
        for index, column in enumerate(template["columns"]):
            name = column["name"]
            value = self.mappings.get(name)
            label = "Unassigned" if name not in self.mappings else "Leave blank" if value is None else labels.get(value, value)
            sample = source_record["values"].get(value, "") if source_record else ""
            self.destination_tree.insert("", "end", iid=f"dest{index}", values=(name, label, sample))
        if selected and self.destination_tree.exists(selected[0]):
            self.destination_tree.selection_set(selected[0])
        elif self.destination_tree.get_children():
            self.destination_tree.selection_set(self.destination_tree.get_children()[0])
        self._destination_selected()

    def _destination_selected(self, _event=None):
        selection = self.destination_tree.selection()
        if not selection:
            return
        column = self.destination_tree.item(selection[0], "values")[0]
        value = self.mappings.get(column)
        self.mapping_column.set(column)
        display = "Unassigned" if column not in self.mappings else "Leave blank" if value is None else next((label for label, name in self.mapping_display.items() if name == value), "Unassigned")
        self.mapping_choice.set(display)
        example = getattr(self, "example_record", None)
        self.example_value.set("Example: " + (example["values"].get(value, "") if example else "No document loaded"))

    def assign_column(self, _event=None, *, column=None, source=None):
        if self.busy or not self.snapshot.get("template"):
            return
        selection = self.destination_tree.selection()
        if column is None:
            if not selection:
                return
            column = self.destination_tree.item(selection[0], "values")[0]
            choice = self.mapping_choice.get()
            source = None if choice == "Leave blank" else self.mapping_display.get(choice)
            if choice == "Unassigned":
                mappings = dict(self.mappings)
                mappings.pop(column, None)
            else:
                mappings = {**self.mappings, column: source}
        else:
            mappings = {**self.mappings, column: source}
        self._save_mapping(mappings, False, "Saving column assignment")

    def suggest_mapping(self):
        template = self.snapshot.get("template")
        if self.busy or not template:
            return
        # Suggestions remain a draft and must still be deliberately confirmed.
        mappings = dict(template.get("suggestions", {}))
        self._save_mapping(mappings, False, "Saving suggested assignments as draft")

    def confirm_mapping(self):
        template = self.snapshot.get("template")
        if self.busy or not template:
            return
        self._save_mapping(dict(self.mappings), True, "Confirming column mapping")

    def _save_mapping(self, mappings, confirmed, title):
        def perform():
            revision = self.snapshot["template"]["revision"]
            self._submit(title, lambda: self.session.set_mapping(mappings, confirmed, revision))
        self._with_draft(perform)

    def _drag_start(self, event):
        self.drag_field = self.source_tree.identify_row(event.y)

    def _drag_drop(self, event):
        if not self.drag_field or self.busy:
            return
        x, y = event.x_root - self.destination_tree.winfo_rootx(), event.y_root - self.destination_tree.winfo_rooty()
        target = self.destination_tree.identify_row(y)
        if 0 <= x < self.destination_tree.winfo_width() and target:
            column = self.destination_tree.item(target, "values")[0]
            self.assign_column(column=column, source=self.drag_field)
        self.drag_field = None

    def export(self, format):
        if self.busy:
            return
        if self.editor_dirty:
            self._with_draft(lambda: self.export(format))
            return
        template = self.snapshot.get("template")
        if not template:
            return
        if format == "xlsx" and template.get("format") != "xlsx":
            self.status.set("XLSX export needs an XLSX template. Import one or use categories as columns.")
            return
        if not (self.snapshot.get("templatePreview") or {}).get("ready"):
            self.status.set("Approve the applicable fields and confirm the column mapping before export.")
            return
        path = filedialog.asksaveasfilename(parent=self.root, title=f"Export approved records as {format.upper()}", defaultextension="." + format, initialfile="reviewed-records." + format, filetypes=[(format.upper(), "*." + format)])
        if path:
            # The domain checks captured revision and approval gates after Save As.
            revision = template["revision"]
            self._submit("Exporting approved records", lambda: self.session.export(format, path, revision), lambda _: self.status.set("Approved records exported successfully."))

    def save_project(self, save_as=False, callback=None):
        if self.busy:
            return
        def perform():
            path = None if save_as else self.snapshot.get("projectPath")
            if not path:
                path = filedialog.asksaveasfilename(parent=self.root, title=f"Save {PRODUCT_NAME} project", defaultextension=".json", initialfile="quickcap-project.json", filetypes=[(f"{PRODUCT_NAME} project", "*.json")])
            if not path:
                return
            self._submit("Saving local project", lambda: self.session.save_project(path), lambda _: callback() if callback else self.status.set("Project saved. Reopening requires fresh field confirmation and approval."))
        self._with_draft(perform)

    def _guard_unsaved(self, action):
        if self.busy:
            return
        if self._draft_unsent:
            self._persist_design(lambda: self._guard_unsaved(action))
            return
        if self.snapshot["dirty"] or self.editor_dirty:
            answer = messagebox.askyesnocancel("Save changes?", "Save your changes before continuing?\n\nYes: Save · No: Discard · Cancel: Keep working", parent=self.root)
            if answer is None:
                return
            if answer:
                self.save_project(callback=action)
                return
        action()

    def open_project(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title=f"Open {PRODUCT_NAME} project", filetypes=[(f"{PRODUCT_NAME} project", "*.json"), ("All files", "*")])
        if path:
            self._guard_unsaved(lambda: self._submit("Opening and reprocessing project", lambda: self.session.open_project(path), lambda _: self.status.set("Project opened. All confirmations and approvals require fresh review.")))

    def new_project(self):
        self._guard_unsaved(lambda: self._submit("Starting new project", self.session.reset))

    def cancel_processing(self):
        if self.busy:
            self.status.set("Cancelling local processing…")
            # stop_jobs can wait for process termination; keep it off Tk's thread.
            threading.Thread(target=self.session.cancel, name="FormbridgeCancel", daemon=True).start()

    def request_close(self):
        if self.closing:
            return
        if self.busy:
            if messagebox.askyesno("Stop processing and close?", "Stop current processing, then review whether to save changes before closing?", parent=self.root):
                self._after_busy = self.request_close
                self.cancel_processing()
            return
        self._guard_unsaved(self._start_close)

    def _start_close(self):
        self.closing = True
        self.status.set("Closing local workspace…")
        self.session.begin_operation()
        self.busy = True
        self._operation_id += 1
        self._set_busy(True)
        self.commands.put((self._operation_id, self.session.close))

    def _finish_close(self):
        self.commands.put(None)
        self.photo = None
        self.root.destroy()


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
