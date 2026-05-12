import os
import sys
import re
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ClientManager:
    def __init__(self, root, current_user="Unknown"):
        self.root = root
        self.current_user = current_user
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Quarium Client Manager")
            self.root.geometry("1000x700")

        # Client database
        self.db_path = os.path.join(BASE_DIR, 'clients.db')

        self.init_db()
        self.create_ui()
        # Startup speedup: Data loading deferred to switch_view

        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Enable foreign key constraints
        self.cursor.execute("PRAGMA foreign_keys = ON")

        # Companies table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                code INTEGER NOT NULL UNIQUE,
                created_at TEXT,
                updated_by TEXT
            )
        ''')

        # Clients table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                funding_code TEXT,
                is_academic INTEGER DEFAULT 0,
                company_id INTEGER,
                created_at TEXT,
                updated_at TEXT,
                updated_by TEXT,
                FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE SET NULL
            )
        ''')

        self.cursor.execute("PRAGMA table_info(clients)")
        client_columns = [column[1] for column in self.cursor.fetchall()]
        if 'phone' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN phone TEXT')
        if 'cpf_cnpj' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN cpf_cnpj TEXT')
        if 'observations' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN observations TEXT')
        if 'client_type' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN client_type TEXT DEFAULT "PF"')
        if 'profession' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN profession TEXT')
        if 'marital_status' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN marital_status TEXT')
        if 'nationality' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN nationality TEXT')
        if 'id_number' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN id_number TEXT')
        if 'id_issuer' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN id_issuer TEXT')
        if 'updated_by' not in client_columns:
            self.cursor.execute('ALTER TABLE clients ADD COLUMN updated_by TEXT')
            try: self.cursor.execute('ALTER TABLE companies ADD COLUMN updated_by TEXT')
            except: pass

        self.conn.commit()

    def create_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Left panel - Client & Company Tree
        left_panel = ttk.LabelFrame(main_frame, text="Clients by Company", padding=10)
        left_panel.pack(side="left", fill="y", padx=(0, 10))

        # Treeview (hierarchical with companies)
        self.tree = ttk.Treeview(left_panel, columns=("Email", "Academic"), height=20)
        self.tree.heading("#0", text="Name")
        self.tree.heading("Email", text="Email")
        self.tree.heading("Academic", text="Academic")
        self.tree.column("#0", width=180)
        self.tree.column("Email", width=150)
        self.tree.column("Academic", width=80)
        self.tree.pack(fill="y", expand=True)

        # Tree buttons
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Add Client", command=self.add_client).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Add Company", command=self.add_company).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Edit Selected", command=self.edit_selected).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_selected).pack(fill="x", pady=2)

        # Right panel - Client Details form
        right_panel = ttk.LabelFrame(main_frame, text="Client Details", padding=10)
        right_panel.pack(side="right", fill="both", expand=True)

        info_frame = ttk.Frame(right_panel)
        info_frame.pack(fill="x", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="Client Type:").grid(row=0, column=0, sticky="w", pady=5)
        type_frame = ttk.Frame(info_frame)
        type_frame.grid(row=0, column=1, sticky="w", padx=5)
        self.client_type_var = tk.StringVar(value="PF")
        ttk.Radiobutton(type_frame, text="Pessoa Física", variable=self.client_type_var, value="PF", command=self.update_cpf_cnpj_label).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(type_frame, text="Pessoa Jurídica", variable=self.client_type_var, value="PJ", command=self.update_cpf_cnpj_label).pack(side="left")

        ttk.Label(info_frame, text="Client Name * :").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Client Email * :").grid(row=2, column=0, sticky="w", pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.email_var, width=40).grid(row=2, column=1, padx=5, pady=5, sticky="we")

        self.cpf_cnpj_label = ttk.Label(info_frame, text="CPF:")
        self.cpf_cnpj_label.grid(row=3, column=0, sticky="w", pady=5)
        self.cpf_cnpj_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.cpf_cnpj_var, width=40).grid(row=3, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Phone Number:").grid(row=4, column=0, sticky="w", pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.phone_var, width=40).grid(row=4, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Profession:").grid(row=5, column=0, sticky="w", pady=5)
        self.profession_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.profession_var, width=40).grid(row=5, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Marital Status:").grid(row=6, column=0, sticky="w", pady=5)
        self.marital_status_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.marital_status_var, width=40).grid(row=6, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Nationality:").grid(row=7, column=0, sticky="w", pady=5)
        self.nationality_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.nationality_var, width=40).grid(row=7, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="ID (RG, etc.):").grid(row=8, column=0, sticky="w", pady=5)
        self.id_number_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.id_number_var, width=40).grid(row=8, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="ID Issuer:").grid(row=9, column=0, sticky="w", pady=5)
        self.id_issuer_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.id_issuer_var, width=40).grid(row=9, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Client Address:").grid(row=10, column=0, sticky="nw", pady=5)
        self.address_text = tk.Text(info_frame, width=30, height=4,
                                    background="#F0F0F0", relief="flat", borderwidth=1)
        self.address_text.grid(row=10, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Funding Code:").grid(row=11, column=0, sticky="w", pady=5)
        self.funding_code_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.funding_code_var, width=40).grid(row=11, column=1, padx=5, pady=5, sticky="we")

        ttk.Label(info_frame, text="Observations:").grid(row=12, column=0, sticky="nw", pady=5)
        self.observations_text = tk.Text(info_frame, width=30, height=4,
                                         background="#F0F0F0", relief="flat", borderwidth=1)
        self.observations_text.grid(row=12, column=1, padx=5, pady=5, sticky="we")

        self.is_academic_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(info_frame, text="Academic Use", variable=self.is_academic_var).grid(row=13, column=0, columnspan=2, sticky="w", pady=10)

        # Save button docked to bottom
        save_frame = ttk.Frame(right_panel)
        save_frame.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(save_frame, text="Save Client", command=self.save_client).pack(side="right", padx=5)

        self.current_client_id = None

        # Bind events
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_end)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)

    def update_cpf_cnpj_label(self):
        if self.client_type_var.get() == "PF":
            self.cpf_cnpj_label.config(text="CPF:")
        else:
            self.cpf_cnpj_label.config(text="CNPJ:")
            
    def validate_cpf(self, cpf):
        numbers = [int(digit) for digit in re.findall(r'\d', cpf)]
        if len(numbers) != 11 or len(set(numbers)) == 1:
            return False
        sum_of_products = sum(a*b for a, b in zip(numbers[0:9], range(10, 1, -1)))
        expected_digit1 = (sum_of_products * 10 % 11) % 10
        if numbers[9] != expected_digit1:
            return False
        sum_of_products = sum(a*b for a, b in zip(numbers[0:10], range(11, 1, -1)))
        expected_digit2 = (sum_of_products * 10 % 11) % 10
        if numbers[10] != expected_digit2:
            return False
        return True

    def validate_cnpj(self, cnpj):
        numbers = [int(digit) for digit in re.findall(r'\d', cnpj)]
        if len(numbers) != 14 or len(set(numbers)) == 1:
            return False
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum_of_products = sum(a*b for a, b in zip(numbers[0:12], weights1))
        expected_digit1 = 11 - (sum_of_products % 11)
        if expected_digit1 >= 10: expected_digit1 = 0
        if numbers[12] != expected_digit1:
            return False
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum_of_products = sum(a*b for a, b in zip(numbers[0:13], weights2))
        expected_digit2 = 11 - (sum_of_products % 11)
        if expected_digit2 >= 10: expected_digit2 = 0
        if numbers[13] != expected_digit2:
            return False
        return True

    def load_clients(self):
        """Load all clients categorized by their companies"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Load companies
        self.cursor.execute("SELECT id, name, code FROM companies ORDER BY name")
        for comp_id, name, code in self.cursor.fetchall():
            node = self.tree.insert("", "end", text=f"{name} (Code: {code})", tags=("company", str(comp_id)), open=True)  # type: ignore
            
            # Load clients for this company
            self.cursor.execute("SELECT id, name, email, is_academic FROM clients WHERE company_id = ? ORDER BY name", (comp_id,))
            for client_id, c_name, c_email, is_acad in self.cursor.fetchall():
                acad_text = "Yes" if is_acad else "No"
                self.tree.insert(node, "end", text=c_name, values=(c_email, acad_text), tags=("client", str(client_id)))  # type: ignore

        # Load uncategorized clients
        uncat_node = self.tree.insert("", "end", text="Uncategorized", tags=("company", ""), open=True)  # type: ignore
        self.cursor.execute("SELECT id, name, email, is_academic FROM clients WHERE company_id IS NULL ORDER BY name")
        for client_id, c_name, c_email, is_acad in self.cursor.fetchall():
            acad_text = "Yes" if is_acad else "No"
            self.tree.insert(uncat_node, "end", text=c_name, values=(c_email, acad_text), tags=("client", str(client_id)))  # type: ignore

    def add_client(self):
        """Prepare form for new client entry"""
        self.clear_form()

    def add_company(self):
        """Add a new company with a number code"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Company")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Company Name:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=25).grid(row=0, column=1, padx=10, pady=5)
        
        # Calculate next unused integer code
        self.cursor.execute("SELECT MAX(code) FROM companies")
        max_code = self.cursor.fetchone()[0]
        next_code = (max_code or 0) + 1
        
        ttk.Label(dialog, text="Company Code:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        code_var = tk.StringVar(value=str(next_code))
        ttk.Entry(dialog, textvariable=code_var, width=25).grid(row=1, column=1, padx=10, pady=5)
        
        def save():
            name = name_var.get().strip()
            try:
                code = int(code_var.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Code must be an integer", parent=dialog)
                return
                
            if not name:
                messagebox.showerror("Error", "Company name is required", parent=dialog)
                return
                
            try:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute("INSERT INTO companies (name, code, created_at, updated_by) VALUES (?, ?, ?, ?)", (name, code, now, self.current_user))
                self.conn.commit()
                self.load_clients()
                dialog.destroy()
            except sqlite3.IntegrityError as e:
                if "code" in str(e).lower():
                    messagebox.showerror("Error", f"Company code '{code}' is already used by another company.", parent=dialog)
                else:
                    messagebox.showerror("Error", "A company with this name already exists", parent=dialog)
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Could not add company: {e}", parent=dialog)

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def edit_selected(self):
        """Edit either a client or a company"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to edit")
            return
        item_type, item_id = self.tree.item(selection[0], "tags")
        if item_type == "company":
            self.edit_company(item_id)
        elif item_type == "client":
            self.load_client_to_form(item_id)

    def edit_company(self, company_id):
        """Edit company details"""
        if not company_id or company_id == 'None':
            messagebox.showerror("Error", "Cannot edit the Uncategorized folder")
            return

        self.cursor.execute("SELECT name, code FROM companies WHERE id = ?", (company_id,))
        result = self.cursor.fetchone()
        if not result:
            return
            
        current_name, current_code = result

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Company")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Company Name:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        name_var = tk.StringVar(value=current_name)
        ttk.Entry(dialog, textvariable=name_var, width=25).grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text="Company Code:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        code_var = tk.StringVar(value=str(current_code))
        ttk.Entry(dialog, textvariable=code_var, width=25).grid(row=1, column=1, padx=10, pady=5)

        def save():
            new_name = name_var.get().strip()
            try:
                new_code = int(code_var.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Code must be an integer", parent=dialog)
                return

            if not new_name:
                messagebox.showerror("Error", "Company name is required", parent=dialog)
                return

            try:
                self.cursor.execute("UPDATE companies SET name = ?, code = ?, updated_by = ? WHERE id = ?", (new_name, new_code, self.current_user, company_id))
                self.conn.commit()
                self.load_clients()
                dialog.destroy()
            except sqlite3.IntegrityError as e:
                if "code" in str(e).lower():
                    messagebox.showerror("Error", f"Company code '{new_code}' is already used by another company.", parent=dialog)
                else:
                    messagebox.showerror("Error", "A company with this name already exists", parent=dialog)
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Could not update company: {e}", parent=dialog)

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def delete_selected(self):
        """Delete either a client or a company"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to delete")
            return
        item_type, item_id = self.tree.item(selection[0], "tags")
        
        if item_type == "company":
            if not item_id or item_id == 'None':
                messagebox.showerror("Error", "Cannot delete the Uncategorized folder")
                return
            self.cursor.execute("SELECT COUNT(*) FROM clients WHERE company_id = ?", (item_id,))
            count = self.cursor.fetchone()[0]
            if count > 0:
                if not messagebox.askyesno("Confirm Delete", f"This company contains {count} client(s). Deleting it will move them to 'Uncategorized'. Continue?"):
                    return
            try:
                self.cursor.execute("UPDATE clients SET company_id = NULL WHERE company_id = ?", (item_id,))
                self.cursor.execute("DELETE FROM companies WHERE id = ?", (item_id,))
                self.conn.commit()
                self.load_clients()
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Could not delete company: {e}")
                
        elif item_type == "client":
            if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this client?"):
                try:
                    self.cursor.execute("DELETE FROM clients WHERE id = ?", (item_id,))
                    self.conn.commit()
                    self.load_clients()
                    self.clear_form()
                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Could not delete client: {e}")

    def load_client_to_form(self, client_id):
        """Load existing client details onto the UI inputs"""
        self.cursor.execute("SELECT name, email, phone, address, funding_code, is_academic, cpf_cnpj, observations, client_type, profession, marital_status, nationality, id_number, id_issuer FROM clients WHERE id = ?", (client_id,))
        result = self.cursor.fetchone()
        if result:
            name, email, phone, address, funding_code, is_academic, cpf_cnpj, observations, client_type, profession, marital_status, nationality, id_number, id_issuer = result
            self.client_type_var.set(client_type or "PF")
            self.update_cpf_cnpj_label()
            self.name_var.set(name)
            self.email_var.set(email)
            self.phone_var.set(phone or "")
            self.cpf_cnpj_var.set(cpf_cnpj or "")
            self.profession_var.set(profession or "")
            self.marital_status_var.set(marital_status or "")
            self.nationality_var.set(nationality or "")
            self.id_number_var.set(id_number or "")
            self.id_issuer_var.set(id_issuer or "")
            self.address_text.delete("1.0", tk.END)
            if address:
                self.address_text.insert(tk.END, address)
            self.funding_code_var.set(funding_code or "")
            self.observations_text.delete("1.0", tk.END)
            if observations:
                self.observations_text.insert(tk.END, observations)
            self.is_academic_var.set(bool(is_academic))
            self.current_client_id = client_id

    def save_client(self):
        """Persist UI Client form to DB"""
        client_type = self.client_type_var.get()
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        phone = self.phone_var.get().strip()
        cpf_cnpj = self.cpf_cnpj_var.get().strip()
        profession = self.profession_var.get().strip()
        marital_status = self.marital_status_var.get().strip()
        nationality = self.nationality_var.get().strip()
        id_number = self.id_number_var.get().strip()
        id_issuer = self.id_issuer_var.get().strip()
        address = self.address_text.get("1.0", tk.END).strip()
        funding_code = self.funding_code_var.get().strip()
        observations = self.observations_text.get("1.0", tk.END).strip()
        is_academic = 1 if self.is_academic_var.get() else 0

        if not name or not email:
            messagebox.showerror("Error", "Name and Email are required")
            return
            
        if cpf_cnpj:
            if client_type == "PF" and not self.validate_cpf(cpf_cnpj):
                messagebox.showerror("Validation Error", "The provided CPF is invalid.")
                return
            elif client_type == "PJ" and not self.validate_cnpj(cpf_cnpj):
                messagebox.showerror("Validation Error", "The provided CNPJ is invalid.")
                return

        # Email validation regex
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messagebox.showerror("Error", "Please enter a valid email address format")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if self.current_client_id:
                self.cursor.execute('''
                    UPDATE clients SET name = ?, email = ?, phone = ?, cpf_cnpj = ?, address = ?, funding_code = ?, observations = ?, is_academic = ?, client_type = ?, profession = ?, marital_status = ?, nationality = ?, id_number = ?, id_issuer = ?, updated_at = ?, updated_by = ?
                    WHERE id = ?
                ''', (name, email, phone, cpf_cnpj, address, funding_code, observations, is_academic, client_type, profession, marital_status, nationality, id_number, id_issuer, now, self.current_user, self.current_client_id))
            else:
                self.cursor.execute('''
                    INSERT INTO clients (name, email, phone, cpf_cnpj, address, funding_code, observations, is_academic, client_type, profession, marital_status, nationality, id_number, id_issuer, created_at, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, email, phone, cpf_cnpj, address, funding_code, observations, is_academic, client_type, profession, marital_status, nationality, id_number, id_issuer, now, now, self.current_user))
                self.current_client_id = self.cursor.lastrowid
            
            self.conn.commit()
            self.load_clients()
            
            # Auto-highlight and focus the newly saved client
            if self.current_client_id:
                for comp_node in self.tree.get_children():
                    for client_node in self.tree.get_children(comp_node):
                        tags = self.tree.item(client_node, "tags")
                        if tags and tags[0] == "client" and str(tags[1]) == str(self.current_client_id):
                            self.tree.selection_set(client_node)
                            self.tree.see(client_node)
                            break
                            
            messagebox.showinfo("Success", "Client saved successfully")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Could not save client: {e}")

    def on_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item_type, item_id = self.tree.item(selection[0], "tags")
        if item_type == "client" and item_id:
            self.load_client_to_form(item_id)
        else:
            self.clear_form()

    def clear_form(self):
        self.client_type_var.set("PF")
        self.update_cpf_cnpj_label()
        self.name_var.set("")
        self.email_var.set("")
        self.phone_var.set("")
        self.cpf_cnpj_var.set("")
        self.profession_var.set("")
        self.marital_status_var.set("")
        self.nationality_var.set("")
        self.id_number_var.set("")
        self.id_issuer_var.set("")
        self.address_text.delete("1.0", tk.END)
        self.funding_code_var.set("")
        self.observations_text.delete("1.0", tk.END)
        self.is_academic_var.set(False)
        self.current_client_id = None

    # Drag and drop functionality
    def on_drag_start(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            item_type, item_id = self.tree.item(item, "tags")
            if item_type == "client":
                self.drag_item = item
                self.drag_item_type = item_type
                self.drag_item_id = item_id
                self.original_selection = self.tree.selection()

    def on_drag_motion(self, event):
        if not hasattr(self, 'drag_item') or not self.drag_item:
            return
        current_item = self.tree.identify_row(event.y)
        
        if hasattr(self, 'drag_highlight') and self.drag_highlight:
            self.tree.selection_remove(self.drag_highlight)
        
        if current_item:
            item_type, _ = self.tree.item(current_item, "tags")
            if item_type == "company":
                self.tree.item(current_item, open=True)
                self.tree.selection_add(current_item)
                self.drag_highlight = current_item
            elif item_type == "client" and current_item != self.drag_item:
                self.tree.selection_add(current_item)
                self.drag_highlight = current_item
            else:
                self.drag_highlight = None
        else:
            self.drag_highlight = None

    def on_drag_end(self, event):
        if not hasattr(self, 'drag_item') or not self.drag_item:
            return

        if hasattr(self, 'drag_highlight') and self.drag_highlight:
            self.tree.selection_remove(self.drag_highlight)
        
        if hasattr(self, 'original_selection'):
            try:
                item_type, _ = self.tree.item(self.original_selection[0], "tags") if self.original_selection else (None, None)
                if item_type == "client":
                    self.tree.selection_set(self.original_selection)
            except:
                pass

        target_item = self.tree.identify_row(event.y)
        if target_item and target_item != self.drag_item:
            target_type, target_id = self.tree.item(target_item, "tags")
            if target_type == "company" and self.drag_item_type == "client":
                try:
                    if not target_id or target_id == 'None':
                        self.cursor.execute("UPDATE clients SET company_id = NULL WHERE id = ?", (self.drag_item_id,))
                    else:
                        self.cursor.execute("UPDATE clients SET company_id = ? WHERE id = ?", (target_id, self.drag_item_id))
                    self.conn.commit()
                    self.load_clients()
                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Could not move client: {e}")

        self.drag_item = None
        self.drag_item_type = None
        self.drag_item_id = None
        if hasattr(self, 'drag_highlight'):
            self.drag_highlight = None
        if hasattr(self, 'original_selection'):
            delattr(self, 'original_selection')

    def on_closing(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.destroy()
            
if __name__ == "__main__":
    root = tk.Tk()
    app = ClientManager(root)
    root.mainloop()