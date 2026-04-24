import sqlite3
import hashlib
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import sys
import os

DB_PATH = "staff_system.db"   
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"  # change after first login in Settings for production

# ----------------------------
# Helper functions
# ----------------------------
def hash_password(password: str) -> str:
    """Return SHA-256 hash of the password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def resource_path(relative_path: str) -> str:
    """Return absolute path to resource, works for pyinstaller too."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------------------
# Database Initialization
# ----------------------------
class Database:
    """A dedicated class to handle all database interactions."""
    def __init__(self, db_path):
        self.db_path = db_path

    def _execute(self, query, params=(), fetch=None):
        """Internal method to execute queries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch == "one":
                    return cursor.fetchone()
                if fetch == "all":
                    return cursor.fetchall()
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}")
            return None if fetch else False

    def init_db(self):
        """Initializes the database tables and default admin user."""
        self._execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT NOT NULL,
                contact TEXT NOT NULL,
                department TEXT NOT NULL,
                date_joined TEXT
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        # Ensure default admin exists
        if not self.get_user(DEFAULT_ADMIN_USER):
            self._execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (DEFAULT_ADMIN_USER, hash_password(DEFAULT_ADMIN_PASS), "admin")
            )

    def get_user(self, username):
        """Fetches a user's password hash and role."""
        return self._execute("SELECT password_hash, role FROM users WHERE username=?", (username,), fetch="one")


# ----------------------------
# Base Page Class
# ----------------------------
class BasePage(ttk.Frame):
    """Base class for all content pages."""
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.app = app_instance
        self.db = app_instance.db
# ----------------------------
# Core Application Class
# ----------------------------
class StaffApp:
    """Main application class for the Staff Database System."""
    def __init__(self):
        # Initialize DB
        self.db = Database(DB_PATH)
        self.db.init_db()
        
        # ttkbootstrap style and root window
        self.style = tb.Style(theme="flatly")  # default light theme
        self.root = self.style.master
        self.root.title("Staff Database System")
        self.root.geometry("1100x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Currently logged-in user info
        self.current_user = None
        self.current_role = None

        # Variables
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.show_password_var = tk.BooleanVar(value=False)

        # For pages & widgets
        self.login_frame = None
        self.sidebar_frame = None
        self.topbar_frame = None
        self.content_frame = None
        self.pages = {}

        # Start with the animated login
        self.show_login(animated=True)

    # ----------------------------
    # Login Screen & Authentication
    # ----------------------------
    def show_login(self, animated: bool = True):
        """Create the login screen. Animated by fade-in and logo slide."""
        # If any main UI exists, destroy it (useful for logout)
        if self.sidebar_frame:
            self.sidebar_frame.destroy()
        if self.topbar_frame:
            self.topbar_frame.destroy()
        if self.content_frame:
            self.content_frame.destroy()

        self.login_frame = ttk.Frame(self.root)
        self.login_frame.place(relwidth=1, relheight=1)

        # Background card
        card = ttk.Frame(self.login_frame, padding=20, style="card.TFrame")
        card.place(relx=0.5, rely=0.5, anchor="center", width=720, height=420)

        # Left side decorative panel
        left_panel = ttk.Frame(card, width=280)
        left_panel.pack(side="left", fill="y", padx=(0,10))
        # Add a project name + small animated "logo" label
        logo_label = ttk.Label(left_panel, text="JanAI\nStaffDB", font=("Sans", 20, "bold"))
        logo_label.place(relx=0.5, rely=0.1, anchor="center")

        tagline = ttk.Label(left_panel, text="Secure. Modern. Simple.", font=("Sans", 10))
        tagline.place(relx=0.5, rely=0.24, anchor="center")

        # Right side: login form
        form = ttk.Frame(card)
        form.pack(side="right", fill="both", expand=True)

        title = ttk.Label(form, text="Sign in", font=("Helvetica", 18, "bold"))
        title.pack(pady=(10, 5))

        # Username
        ttk.Label(form, text="Username:").pack(anchor="w", padx=20, pady=(10, 3))
        username_entry = ttk.Entry(form, textvariable=self.username_var, width=30)
        username_entry.pack(padx=20)
        username_entry.focus()

        # Password
        ttk.Label(form, text="Password:").pack(anchor="w", padx=20, pady=(10, 3))
        self.password_entry = ttk.Entry(form, textvariable=self.password_var, width=30, show="*")
        self.password_entry.pack(padx=20)

        show_cb = ttk.Checkbutton(form, text="Show password", variable=self.show_password_var, bootstyle="secondary")
        show_cb.pack(anchor="w", padx=20, pady=(5, 8))
        show_cb.configure(command=self.toggle_show_password)

        # Buttons (Login)
        btn_frame = ttk.Frame(form)
        btn_frame.pack(pady=(10, 0))
        login_btn = tb.Button(btn_frame, text="Login", bootstyle="success", command=self.authenticate, width=18)
        login_btn.grid(row=0, column=0, padx=5)
        reset_btn = tb.Button(btn_frame, text="Clear", bootstyle="secondary", command=self.clear_login_fields, width=10)
        reset_btn.grid(row=0, column=1, padx=5)

        # Quick help & default credentials notice (non-intrusive)
        help_label = ttk.Label(form, text=f"Tip: default admin / {DEFAULT_ADMIN_PASS}", font=("Helvetica", 8))
        help_label.pack(side="bottom", pady=(10, 0))

        # Add keyboard binding for Enter key
        self.root.bind("<Return>", lambda e: self.authenticate())

        # Simple animation: fade-in whole window and slide the left logo downward
        if animated:
            self.root.attributes("-alpha", 0.0)
            self._fade_in(0.0)
            # Slide the logo label down
            self._slide_widget(logo_label, start_y=-80, end_y=35, duration=350)
        else:
            self.root.attributes("-alpha", 1.0)

    def _fade_in(self, alpha: float, step: float = 0.06):
        """Recursive fade-in of the window alpha attribute."""
        alpha += step
        if alpha >= 1.0:
            self.root.attributes("-alpha", 1.0)
            return
        self.root.attributes("-alpha", alpha)
        self.root.after(30, lambda: self._fade_in(alpha, step))

    def _slide_widget(self, widget, start_y: int, end_y: int, duration: int = 300):
        """Slide a widget vertically using place geometry (simple animation)."""
        steps = max(6, duration // 20)
        delta = (end_y - start_y) / steps
        current = start_y
        # initial placement
        widget.place(relx=0.5, y=current, anchor="n")
        def step():
            nonlocal current
            current += delta
            widget.place(relx=0.5, y=int(current), anchor="n")
            if (delta > 0 and current < end_y) or (delta < 0 and current > end_y):
                widget.after(20, step)
            else:
                widget.place(relx=0.5, y=end_y, anchor="n")
        step()

    def toggle_show_password(self):
        """Show/hide password characters."""
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

    def clear_login_fields(self):
        """Reset login fields."""
        self.username_var.set("")
        self.password_var.set("")

    def authenticate(self):
        """Authenticate user from users table."""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showerror("Validation", "Please enter username and password.")
            return

        row = self.db.get_user(username)
        if row and row[0] == hash_password(password):
            # Login success
            self.current_user = username
            self.current_role = row[1]
            # Clean up login UI and show main UI
            self.root.unbind("<Return>")
            # Fade out then build main UI
            self._fade_out_then_show_main()
        else:
            messagebox.showerror("Authentication Failed", "Invalid username or password.")

    def _fade_out_then_show_main(self):
        """Fade out the login screen and initialize the main app UI."""
        def fade_out(alpha):
            alpha -= 0.07
            if alpha <= 0:
                self.root.attributes("-alpha", 0.0)
                # Destroy login frame & build main UI
                if self.login_frame:
                    self.login_frame.destroy()
                    self.login_frame = None
                # Build main UI
                self.build_main_ui()
                # Fade in
                self.root.attributes("-alpha", 0.0)
                self._fade_in(0.0)
                return
            self.root.attributes("-alpha", alpha)
            self.root.after(30, lambda: fade_out(alpha))
        fade_out(1.0)

    # ----------------------------
    # Main UI Construction
    # ----------------------------
    def build_main_ui(self):
        """Create sidebar, topbar, and content area with all pages."""
        # Topbar
        self.topbar_frame = ttk.Frame(self.root, padding=(8, 8))
        self.topbar_frame.place(relx=0, rely=0, relwidth=1, height=60)

        app_label = ttk.Label(self.topbar_frame, text="Staff Database System", font=("Helvetica", 14, "bold"))
        app_label.pack(side="left", padx=12)

        # Spacer
        spacer = ttk.Label(self.topbar_frame, text="")
        spacer.pack(side="left", expand=True)

        # Light/Dark toggle
        self.theme_toggle_var = tk.BooleanVar(value=self.style.theme_use().startswith("dark"))
        theme_btn = tb.Button(self.topbar_frame, text="Toggle Theme", bootstyle="info-outline", command=self.toggle_theme)
        theme_btn.pack(side="right", padx=8)

        # User badge & logout
        user_label = ttk.Label(self.topbar_frame, text=f"User: {self.current_user} ({self.current_role})")
        user_label.pack(side="right", padx=12)

        # Sidebar
        self.sidebar_frame = ttk.Frame(self.root, width=220, padding=10, style="secondary.TFrame")
        self.sidebar_frame.place(x=0, y=60, relheight=1, height=-60)

        # Sidebar buttons
        bb_style = {"width": 20, "compound": "left", "bootstyle": "light"}
        tb.Button(self.sidebar_frame, text="📊 Dashboard", command=lambda: self.show_page("dashboard"), **bb_style).pack(fill="x", pady=6)
        tb.Button(self.sidebar_frame, text="👥 Staff List", command=lambda: self.show_page("staff"), **bb_style).pack(fill="x", pady=6)
        if self.current_role == "admin":
            tb.Button(self.sidebar_frame, text="➕ Add Staff", command=lambda: self.show_page("add"), **bb_style).pack(fill="x", pady=6)
        tb.Button(self.sidebar_frame, text="📈 Reports", command=lambda: self.show_page("reports"), **bb_style).pack(fill="x", pady=6)
        tb.Button(self.sidebar_frame, text="⚙️ Settings", command=lambda: self.show_page("settings"), **bb_style).pack(fill="x", pady=6)
        tb.Button(self.sidebar_frame, text="Logout", bootstyle="danger", command=self.logout).pack(side="bottom", fill="x", pady=8)

        # Main content area
        self.content_frame = ttk.Frame(self.root, padding=12)
        self.content_frame.place(x=220, y=60, relwidth=1, relheight=1, width=-220, height=-60)

        # Create pages (frames) and store in pages dict
        self.pages["dashboard"] = DashboardPage(self.content_frame, self)
        self.pages["staff"] = StaffPage(self.content_frame, self)
        self.pages["add"] = AddStaffPage(self.content_frame, self)
        self.pages["reports"] = ReportsPage(self.content_frame, self)
        self.pages["settings"] = SettingsPage(self.content_frame, self)

        for page in self.pages.values():
            page.place(relwidth=1, relheight=1)

        # Default show dashboard
        self.show_page("dashboard")

    def toggle_theme(self):
        """Toggle between a light and a dark theme."""
        current = self.style.theme_use()
        # Choose two themes that come with ttkbootstrap commonly available:
        # light: flatly, dark: darkly (but the exact availability may vary by ttkbootstrap version)
        if "dark" in current:
            self.style.theme_use("flatly")
        else:
            # try "darkly" else fallback
            try:
                self.style.theme_use("darkly")
            except Exception:
                # fallback to "cyborg" if not available
                self.style.theme_use("cyborg")

    def show_page(self, page_name: str):
        """Raise the specified page (simple show/hide)."""
        for name, frame in self.pages.items():
            if name == page_name:
                frame.lift()
            else:
                frame.lower()
        # On page show refresh data where needed
        if page_name == "dashboard":
            self.pages["dashboard"].refresh_dashboard()
        elif page_name == "staff":
            self.pages["staff"].refresh_staff_list()
        elif page_name == "add":
            # Clear form if not editing
            self.pages["add"].prepare_for_add()
        elif page_name == "reports":
            self.pages["reports"].refresh_reports()

    # ----------------------------
    # Logout & Close
    # ----------------------------
    def logout(self):
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if not confirm:
            return
        # Destroy main UI frames and show login again
        if self.sidebar_frame:
            self.sidebar_frame.destroy(); self.sidebar_frame = None
        if self.topbar_frame:
            self.topbar_frame.destroy(); self.topbar_frame = None
        if self.content_frame:
            self.content_frame.destroy(); self.content_frame = None
        self.current_user = None
        self.current_role = None
        self.show_login(animated=True)

    def on_close(self):
        """Graceful shutdown."""
        if messagebox.askokcancel("Quit", "Exit application?"):
            self.root.quit()
            self.root.destroy()

# ----------------------------
# Page Classes
# ----------------------------
class DashboardPage(BasePage):
    def __init__(self, master, app_instance):
        super().__init__(master, app_instance)
        self._build_dashboard_page()

    def _build_dashboard_page(self):
        # Statistics cards
        stat_frame = ttk.Frame(self)
        stat_frame.pack(fill="x", pady=(6,12))
        self.total_label = ttk.Label(stat_frame, text="Total staff: 0", font=("Helvetica", 12, "bold"))
        self.total_label.pack(side="left", padx=8)
        self.dept_label = ttk.Label(stat_frame, text="Departments: 0", font=("Helvetica", 12))
        self.dept_label.pack(side="left", padx=8)

        # Mini chart area
        chart_card = ttk.Labelframe(self, text="Staff by Department", padding=8)
        chart_card.pack(fill="both", expand=True)

        self.fig_dashboard, self.ax_dashboard = plt.subplots(figsize=(5,3))
        self.canvas_dashboard = FigureCanvasTkAgg(self.fig_dashboard, master=chart_card)
        self.canvas_dashboard.get_tk_widget().pack(fill="both", expand=True)

    def refresh_dashboard(self):
        """Update dashboard statistics and mini chart."""
        total_res = self.db._execute("SELECT COUNT(*) FROM staff", fetch="one")
        total = total_res[0] if total_res else 0
        depts_res = self.db._execute("SELECT COUNT(DISTINCT department) FROM staff", fetch="one")
        depts = depts_res[0] if depts_res else 0
        self.total_label.config(text=f"Total staff: {total}")
        self.dept_label.config(text=f"Departments: {depts}")

        rows = self.db._execute("SELECT department, COUNT(*) FROM staff GROUP BY department", fetch="all")
        departments = [r[0] for r in rows] if rows else []
        counts = [r[1] for r in rows] if rows else []

        self.ax_dashboard.clear()
        if departments:
            self.ax_dashboard.bar(departments, counts)
            self.ax_dashboard.set_xlabel("Department")
            self.ax_dashboard.set_ylabel("Number of staff")
            self.ax_dashboard.set_title("Staff per Department")
            self.fig_dashboard.tight_layout()
        else:
            self.ax_dashboard.text(0.5, 0.5, "No data available", ha="center")
        self.canvas_dashboard.draw()

class StaffPage(BasePage):
    def __init__(self, master, app_instance):
        super().__init__(master, app_instance)
        self._build_staff_page()

    def _build_staff_page(self):
        topbar = ttk.Frame(self)
        topbar.pack(fill="x")

        search_label = ttk.Label(topbar, text="Search (by name or department):")
        search_label.pack(side="left", padx=(8,4))
        self.staff_search_var = tk.StringVar()
        search_entry = ttk.Entry(topbar, textvariable=self.staff_search_var, width=35)
        search_entry.pack(side="left", padx=6)
        tb.Button(topbar, text="Search", bootstyle="info", command=self.search_staff).pack(side="left", padx=4)
        tb.Button(topbar, text="Show All", bootstyle="secondary", command=self.refresh_staff_list).pack(side="left", padx=4)
        tb.Button(topbar, text="Export Excel", bootstyle="success", command=self.export_staff_excel).pack(side="right", padx=6)

        columns = ("id", "name", "position", "contact", "department", "date_joined")
        self.staff_tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self.staff_tree.heading(col, text=col.capitalize())
            self.staff_tree.column(col, width={"name": 200, "position": 140, "contact": 120, "department": 140}.get(col, 80), anchor="center" if col != "name" else "w")
        self.staff_tree.pack(fill="both", expand=True, pady=(10,0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(8,0))
        if self.app.current_role == "admin":
            tb.Button(btn_frame, text="Add New", bootstyle="primary", command=lambda: self.app.show_page("add")).pack(side="left", padx=6)
            tb.Button(btn_frame, text="Edit Selected", command=self.open_edit_selected).pack(side="left", padx=6)
            tb.Button(btn_frame, text="Delete Selected", bootstyle="danger", command=self.delete_selected).pack(side="left", padx=6)
            self.staff_tree.bind("<Double-1>", lambda e: self.open_edit_selected())

    def refresh_staff_list(self):
        self.staff_search_var.set("")
        for row in self.staff_tree.get_children():
            self.staff_tree.delete(row)
        rows = self.db._execute("SELECT id, name, position, contact, department, date_joined FROM staff ORDER BY id DESC", fetch="all")
        if rows:
            for r in rows:
                self.staff_tree.insert("", "end", values=r)

    def search_staff(self):
        query = self.staff_search_var.get().strip()
        if not query:
            messagebox.showinfo("Search", "Enter a name or department to search.")
            return
        for row in self.staff_tree.get_children():
            self.staff_tree.delete(row)
        rows = self.db._execute("SELECT id, name, position, contact, department, date_joined FROM staff WHERE name LIKE ? OR department LIKE ?", (f"%{query}%", f"%{query}%"), fetch="all")
        if rows:
            for r in rows:
                self.staff_tree.insert("", "end", values=r)

    def open_edit_selected(self):
        if self.app.current_role != "admin":
            messagebox.showwarning("Permission Denied", "You do not have permission to edit records.")
            return
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Select a record to edit.")
            return
        staff_id = self.staff_tree.item(selected[0], "values")[0]
        self.app.show_page("add")
        self.app.pages["add"].prefill_add_form(staff_id)

    def delete_selected(self):
        if self.app.current_role != "admin":
            messagebox.showwarning("Permission Denied", "You do not have permission to delete records.")
            return
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Select a record to delete.")
            return
        staff_id, name = self.staff_tree.item(selected[0], "values")[0:2]
        if messagebox.askyesno("Confirm Delete", f"Delete staff '{name}' (ID {staff_id})?"):
            if self.db._execute("DELETE FROM staff WHERE id=?", (staff_id,)):
                messagebox.showinfo("Deleted", "Record deleted successfully.")
                self.refresh_staff_list()

    def export_staff_excel(self):
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM staff", conn)
            if df.empty:
                messagebox.showinfo("Export", "No data to export.")
                return
            file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")], parent=self.app.root)
            if file_path:
                df.to_excel(file_path, index=False)
                messagebox.showinfo("Export", f"Exported {len(df)} records to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export: {e}")

class AddStaffPage(BasePage):
    def __init__(self, master, app_instance):
        super().__init__(master, app_instance)
        self._build_add_page()

    def _build_add_page(self):
        form_frame = ttk.Frame(self, padding=12)
        form_frame.pack(pady=10)

        labels = ["Name:", "Position:", "Contact:", "Department:", "Date Joined (YYYY-MM-DD):"]
        self.string_vars = {
            "Name:": tk.StringVar(), "Position:": tk.StringVar(), "Contact:": tk.StringVar(),
            "Department:": tk.StringVar(), "Date Joined (YYYY-MM-DD):": tk.StringVar(value=datetime.date.today().isoformat())
        }

        for i, label_text in enumerate(labels):
            ttk.Label(form_frame, text=label_text).grid(row=i, column=0, sticky="w", padx=6, pady=6)
            ttk.Entry(form_frame, textvariable=self.string_vars[label_text], width=36).grid(row=i, column=1, padx=6, pady=6)

        self.editing_staff_id = None

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=12)
        tb.Button(btn_frame, text="Save", bootstyle="success", command=self.save_staff).pack(side="left", padx=6)
        tb.Button(btn_frame, text="Save & New", bootstyle="primary", command=lambda: self.save_staff(new=True)).pack(side="left", padx=6)
        tb.Button(btn_frame, text="Cancel", bootstyle="secondary", command=lambda: self.app.show_page("staff")).pack(side="left", padx=6)

    def prepare_for_add(self):
        """Clears the form if no staff is being edited."""
        if not self.editing_staff_id:
            self.clear_add_form()

    def prefill_add_form(self, staff_id: int):
        r = self.db._execute("SELECT id, name, position, contact, department, date_joined FROM staff WHERE id=?", (staff_id,), fetch="one")
        if not r:
            messagebox.showerror("Not Found", "Record not found.")
            return
        self.editing_staff_id = r[0]
        self.string_vars["Name:"].set(r[1])
        self.string_vars["Position:"].set(r[2])
        self.string_vars["Contact:"].set(r[3])
        self.string_vars["Department:"].set(r[4])
        self.string_vars["Date Joined (YYYY-MM-DD):"].set(r[5] if r[5] else datetime.date.today().isoformat())

    def save_staff(self, new: bool = False):
        if self.app.current_role != "admin":
            messagebox.showerror("Permission Denied", "You do not have permission to save staff data.")
            return

        name = self.string_vars["Name:"].get().strip()
        position = self.string_vars["Position:"].get().strip()
        contact = self.string_vars["Contact:"].get().strip()
        department = self.string_vars["Department:"].get().strip()
        date_joined = self.string_vars["Date Joined (YYYY-MM-DD):"].get().strip()

        if not (name and position and contact and department):
            messagebox.showerror("Validation", "Name, Position, Contact and Department are required.")
            return
        if not contact.isdigit() or len(contact) not in (10, 11, 12):
            messagebox.showerror("Validation", "Contact must be numeric (10-12 digits).")
            return
        try:
            datetime.datetime.strptime(date_joined, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Validation", "Date Joined must be YYYY-MM-DD.")
            return

        if self.editing_staff_id:
            query = "UPDATE staff SET name=?, position=?, contact=?, department=?, date_joined=? WHERE id=?"
            params = (name, position, contact, department, date_joined, self.editing_staff_id)
            if self.db._execute(query, params) is not False:
                 messagebox.showinfo("Updated", "Record updated successfully.")
                 self.clear_add_form()
                 self.app.show_page("staff")
        else:
            query = "INSERT INTO staff (name, position, contact, department, date_joined) VALUES (?, ?, ?, ?, ?)"
            params = (name, position, contact, department, date_joined)
            if self.db._execute(query, params):
                messagebox.showinfo("Added", "Staff added successfully.")
            self.clear_add_form()
            if not new:
                self.app.show_page("staff")

    def clear_add_form(self):
        self.editing_staff_id = None
        for var in self.string_vars.values():
            var.set("")
        self.string_vars["Date Joined (YYYY-MM-DD):"].set(datetime.date.today().isoformat())

class ReportsPage(BasePage):
    def __init__(self, master, app_instance):
        super().__init__(master, app_instance)
        self._build_reports_page()

    def _build_reports_page(self):
        header = ttk.Label(self, text="Reports & Analytics", font=("Helvetica", 14, "bold"))
        header.pack(pady=(6,10))
        ttk.Label(self, text="Click a bar to view staff in that department.").pack()

        chart_card = ttk.Frame(self)
        chart_card.pack(fill="both", expand=True, padx=6, pady=6)

        self.fig_reports, self.ax_reports = plt.subplots(figsize=(8,4))
        self.canvas_reports = FigureCanvasTkAgg(self.fig_reports, master=chart_card)
        self.canvas_reports.get_tk_widget().pack(fill="both", expand=True)
        self.canvas_reports.mpl_connect("button_press_event", self.on_reports_click)

        detail_card = ttk.Labelframe(self, text="Department Details", padding=8)
        detail_card.pack(fill="both", expand=False, padx=6, pady=(0,6))

        # Add a button to copy the content of the text widget
        copy_btn = tb.Button(detail_card, text="Copy to Clipboard", bootstyle="info-outline", command=self.copy_report_details)
        copy_btn.pack(anchor="ne", pady=(0, 5))

        self.report_detail_text = tk.Text(detail_card, height=8, wrap="word")
        self.report_detail_text.pack(fill="both", expand=True)

    def copy_report_details(self):
        """Copies the content of the report detail text widget to the clipboard."""
        content = self.report_detail_text.get(1.0, "end-1c") # Get all text except the final newline
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(content)

    def refresh_reports(self):
        rows = self.db._execute("SELECT department, COUNT(*) FROM staff GROUP BY department", fetch="all")
        self.ax_reports.clear()
        if rows:
            depts = [r[0] for r in rows]
            counts = [r[1] for r in rows]
            self.ax_reports.bar(depts, counts, picker=True)
            self.ax_reports.set_title("Staff count by Department")
            self.ax_reports.set_ylabel("Count")
            self.fig_reports.tight_layout()
        else:
            self.ax_reports.text(0.5, 0.5, "No data to display", ha="center")
        self.canvas_reports.draw()
        self.report_detail_text.delete(1.0, "end")

    def on_reports_click(self, event):
        if event.x is None or event.y is None or event.xdata is None: return
        try:
            bars = [bar for bar in self.ax_reports.patches]
            if not bars: return
            centers = [bar.get_x() + bar.get_width() / 2.0 for bar in bars]
            idx = min(range(len(centers)), key=lambda i: abs(centers[i] - event.xdata))
            ticklabels = [t.get_text() for t in self.ax_reports.get_xticklabels()]
            dept_name = ticklabels[idx] if idx < len(ticklabels) else ""
            
            rows = self.db._execute("SELECT name, position, contact, date_joined FROM staff WHERE department=?", (dept_name,), fetch="all")
            self.report_detail_text.delete(1.0, "end")
            if rows:
                text = f"Staff in {dept_name} ({len(rows)}):\n\n"
                for r in rows:
                    text += f"- {r[0]} | {r[1]} | {r[2]} | Joined: {r[3]}\n"
            else:
                text = f"No staff found in department: {dept_name}"
            self.report_detail_text.insert("end", text)
        except Exception as e:
            self.report_detail_text.delete(1.0, "end")
            self.report_detail_text.insert("end", f"Could not show details: {e}")

class SettingsPage(BasePage):
    def __init__(self, master, app_instance):
        super().__init__(master, app_instance)
        self._build_settings_page()

    def _build_settings_page(self):
        header = ttk.Label(self, text="Settings", font=("Helvetica", 14, "bold"))
        header.pack(pady=(6,10))

        theme_card = ttk.Labelframe(self, text="Appearance", padding=8)
        theme_card.pack(fill="x", padx=8, pady=6)
        ttk.Label(theme_card, text="Theme:").pack(side="left", padx=8)
        theme_combo = ttk.Combobox(theme_card, values=self.app.style.theme_names(), state="readonly", width=25)
        theme_combo.set(self.app.style.theme_use())
        theme_combo.pack(side="left", padx=8)
        def apply_theme():
            try:
                self.app.style.theme_use(theme_combo.get())
                messagebox.showinfo("Theme", f"Theme changed to {theme_combo.get()}")
            except Exception as e:
                messagebox.showerror("Theme Error", f"Could not set theme: {e}")
        tb.Button(theme_card, text="Apply", command=apply_theme).pack(side="left", padx=6)

        pwd_card = ttk.Labelframe(self, text="Change Password", padding=8)
        pwd_card.pack(fill="x", padx=8, pady=6)
        ttk.Label(pwd_card, text="New Password:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.new_pwd_var = tk.StringVar()
        ttk.Entry(pwd_card, textvariable=self.new_pwd_var, width=30, show="*").grid(row=0, column=1, padx=6, pady=6)
        tb.Button(pwd_card, text="Change Password", bootstyle="warning", command=self.change_password).grid(row=0, column=2, padx=6, pady=6)
        
        # --- Admin-only User Management ---
        if self.app.current_role == "admin":
            self._build_user_management_panel()

    def change_password(self):
        new_pwd = self.new_pwd_var.get().strip()
        if not new_pwd:
            messagebox.showerror("Validation", "Enter a new password.")
            return
        if self.db._execute("UPDATE users SET password_hash=? WHERE username=?", (hash_password(new_pwd), self.app.current_user)):
            messagebox.showinfo("Success", "Password changed successfully.")
            self.new_pwd_var.set("")

    def _build_user_management_panel(self):
        """Builds the UI for adding/deleting users, visible only to admins."""
        user_card = ttk.Labelframe(self, text="User Management", padding=8)
        user_card.pack(fill="both", expand=True, padx=8, pady=6)

        # Treeview to display users
        user_cols = ("username", "role")
        self.user_tree = ttk.Treeview(user_card, columns=user_cols, show="headings", height=5)
        self.user_tree.heading("username", text="Username")
        self.user_tree.heading("role", text="Role")
        self.user_tree.column("username", anchor="w")
        self.user_tree.column("role", width=100, anchor="center")
        self.user_tree.pack(fill="x", pady=(0, 8))

        # Buttons for user actions
        btn_frame = ttk.Frame(user_card)
        btn_frame.pack(fill="x")
        tb.Button(btn_frame, text="Add User", bootstyle="success", command=self.add_user_dialog).pack(side="left", padx=4)
        tb.Button(btn_frame, text="Delete Selected User", bootstyle="danger", command=self.delete_user).pack(side="left", padx=4)

        self.load_users()

    def load_users(self):
        """Fetches and displays all users in the treeview."""
        for row in self.user_tree.get_children():
            self.user_tree.delete(row)
        rows = self.db._execute("SELECT username, role FROM users ORDER BY username", fetch="all")
        if rows:
            for r in rows:
                self.user_tree.insert("", "end", values=r)

    def add_user_dialog(self):
        """Opens a dialog to add a new user."""
        win = tb.Toplevel(self.app.root, title="Add New User")
        win.geometry("350x300")

        form = ttk.Frame(win, padding=15)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Username:").grid(row=0, column=0, sticky="w", pady=5)
        user_var = tk.StringVar()
        ttk.Entry(form, textvariable=user_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(form, text="Password:").grid(row=1, column=0, sticky="w", pady=5)
        pass_var = tk.StringVar()
        ttk.Entry(form, textvariable=pass_var, width=30, show="*").grid(row=1, column=1, pady=5)

        ttk.Label(form, text="Role:").grid(row=2, column=0, sticky="w", pady=5)
        role_var = tk.StringVar(value="user")
        ttk.Combobox(form, textvariable=role_var, values=["user", "admin"], state="readonly", width=28).grid(row=2, column=1, pady=5)

        def save_user():
            username = user_var.get().strip()
            password = pass_var.get().strip()
            role = role_var.get()
            if not (username and password):
                messagebox.showerror("Validation", "Username and Password are required.", parent=win)
                return
            
            # Check if user exists
            if self.db.get_user(username):
                messagebox.showerror("Error", "Username already exists.", parent=win)
                return

            self.db._execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, hash_password(password), role))
            messagebox.showinfo("Success", f"User '{username}' created successfully.", parent=win)
            self.load_users()
            win.destroy()

        tb.Button(form, text="Save User", bootstyle="success", command=save_user).grid(row=3, columnspan=2, pady=15)

    def delete_user(self):
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select a user to delete.")
            return
        username_to_delete = self.user_tree.item(selected[0], "values")[0]

        if username_to_delete == self.app.current_user:
            messagebox.showerror("Action Denied", "You cannot delete your own account.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the user '{username_to_delete}'? This action cannot be undone."):
            self.db._execute("DELETE FROM users WHERE username=?", (username_to_delete,))
            messagebox.showinfo("Deleted", f"User '{username_to_delete}' has been deleted.")
            self.load_users()

# ----------------------------
# Entry point
# ----------------------------
def main():
    app = StaffApp()
    # Start the mainloop
    app.root.mainloop()

if __name__ == "__main__":
    main()