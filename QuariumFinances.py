import os
import sys
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import tempfile
import webbrowser

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib import colors  # type: ignore
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
    from reportlab.lib.units import cm  # type: ignore
    from reportlab.pdfgen import canvas  # type: ignore
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    A4 = (595.27, 841.89)  # type: ignore
    cm = 28.3465  # type: ignore

    class _DummyColor:
        lightgrey = None
        grey = None
    colors = _DummyColor()  # type: ignore

    class SimpleDocTemplate:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def build(self, *args, **kwargs): pass

    class Paragraph:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class Spacer:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class Table:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def setStyle(self, *args, **kwargs): pass

    class TableStyle:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class RLImage:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class PageBreak:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    def getSampleStyleSheet(*args, **kwargs):  # type: ignore
        return {'Heading1': None, 'Normal': None}

    class ParagraphStyle:  # type: ignore
        def __init__(self, *args, **kwargs): pass

    class canvas:  # type: ignore
        class Canvas:
            def __init__(self, *args, **kwargs): pass
            def setFont(self, *args, **kwargs): pass
            def setFillColor(self, *args, **kwargs): pass
            def drawCentredString(self, *args, **kwargs): pass
            def drawRightString(self, *args, **kwargs): pass

if REPORTLAB_AVAILABLE:
    class NumberedCanvas(canvas.Canvas):
        contract_footer_text = "Quarium Consultoria em Biologia Analítica, Ltda. | Campinas, SP | Email: quarium.bio@gmail.com"
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []
        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()  # type: ignore
        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_number(num_pages)  # type: ignore
                canvas.Canvas.showPage(self)  # type: ignore
            canvas.Canvas.save(self)  # type: ignore
        def draw_page_number(self, page_count):
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.grey)
            self.drawRightString(A4[0] - 2.0 * cm, A4[1] - 1.0 * cm, f"Página {self._pageNumber} de {page_count}")
            lines = self.contract_footer_text.replace('\\n', '\n').splitlines()
            y_pos = 1.0 * cm + (len(lines) - 1) * 10
            for line in lines:
                self.drawCentredString(A4[0] / 2.0, y_pos, line.strip())
                y_pos -= 10
else:
    NumberedCanvas = None

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class FinancesManager:
    def __init__(self, root, current_user="Unknown"):
        self.root = root
        self.current_user = current_user
        self.db_path = os.path.join(BASE_DIR, 'projects.db')
        self.client_db_path = os.path.join(BASE_DIR, 'clients.db')
        
        self.init_db()
        self.create_ui()
        # Startup speedup: Data loading deferred to switch_view

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY,
                client_id INTEGER,
                total_cost REAL,
                generated_at TEXT,
                generated_by TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS contract_projects (
                contract_id INTEGER,
                project_id INTEGER,
                FOREIGN KEY (contract_id) REFERENCES contracts (id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def load_settings(self):
        settings_path = os.path.join(BASE_DIR, 'settings.json')
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings.update(json.load(f))
            except Exception: pass
        return settings

    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        title_lbl = ttk.Label(main_frame, text="Approved Estimates & Contracts", font=("Helvetica", 14, "bold"))
        title_lbl.pack(anchor="w", pady=(0, 10))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("Estimate", "Client", "Cost", "Contract Emitted"), selectmode="extended", height=20)
        self.tree.heading("#0", text="ID")
        self.tree.heading("Estimate", text="Estimate #")
        self.tree.heading("Client", text="Client")
        self.tree.heading("Cost", text="Total Cost")
        self.tree.heading("Contract Emitted", text="Contract Emitted")
        
        self.tree.column("#0", width=0, stretch=False)
        self.tree.column("Estimate", width=120)
        self.tree.column("Client", width=250)
        self.tree.column("Cost", width=120, anchor="e")
        self.tree.column("Contract Emitted", width=120, anchor="center")
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.bind("<Double-1>", self.on_double_click)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="Refresh List", command=self.load_data).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Generate PDF Contract", command=lambda: self.process_contract(preview=False), style="Accent.TButton").pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Preview PDF", command=lambda: self.process_contract(preview=True)).pack(side="right", padx=5)

    def format_br_currency(self, value):
        formatted = f"{value:,.2f}"
        formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {formatted}"

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.cursor.execute("ATTACH DATABASE ? AS clients_db", (self.client_db_path,))
        
        self.cursor.execute('''
            SELECT p.id, p.estimate_number, c.id, c.name, p.final_cost,
                   (SELECT COUNT(*) FROM contract_projects cp WHERE cp.project_id = p.id) as contract_count
            FROM projects p
            LEFT JOIN clients_db.clients c ON p.client_id = c.id
            WHERE p.status > 0
            ORDER BY c.name, p.estimate_number
        ''')
        
        for p_id, est_num, c_id, c_name, cost, c_count in self.cursor.fetchall():
            status_mark = "✔️ Yes" if c_count > 0 else "No"
            cost_str = self.format_br_currency(cost) if cost is not None else "R$ 0,00"
            self.tree.insert("", "end", values=(est_num, c_name or "Unknown", cost_str, status_mark), tags=(p_id, c_id))
            
        self.cursor.execute("DETACH DATABASE clients_db")

    def on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        
        p_id, _ = self.tree.item(item, "tags")
        est_num = self.tree.item(item, "values")[0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Contract History: {est_num}")
        dialog.geometry("650x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Generated Contracts for {est_num}", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        hist_tree = ttk.Treeview(dialog, columns=("Date", "Issuer", "Total Cost", "Co-Included Projects"), show="headings", height=8)
        hist_tree.heading("Date", text="Date Emitted")
        hist_tree.heading("Issuer", text="Issuer")
        hist_tree.heading("Total Cost", text="Total Cost")
        hist_tree.heading("Co-Included Projects", text="Co-Included Projects")
        
        hist_tree.column("Date", width=120)
        hist_tree.column("Issuer", width=120)
        hist_tree.column("Total Cost", width=100, anchor="e")
        hist_tree.column("Co-Included Projects", width=250)
        hist_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.cursor.execute('''
            SELECT c.id, c.generated_at, c.generated_by, c.total_cost
            FROM contracts c
            JOIN contract_projects cp ON c.id = cp.contract_id
            WHERE cp.project_id = ?
            ORDER BY c.generated_at DESC
        ''', (p_id,))
        
        contracts = self.cursor.fetchall()
        for c_id, g_at, g_by, t_cost in contracts:
            self.cursor.execute('''
                SELECT p.estimate_number 
                FROM projects p 
                JOIN contract_projects cp ON p.id = cp.project_id 
                WHERE cp.contract_id = ? AND p.id != ?
            ''', (c_id, p_id))
            co_projs = [r[0] for r in self.cursor.fetchall()]
            co_str = ", ".join(co_projs) if co_projs else "None"
            
            date_str = datetime.strptime(g_at.split()[0], '%Y-%m-%d').strftime('%d/%m/%Y') if g_at else "Unknown"
            cost_str = self.format_br_currency(t_cost) if t_cost else "R$ 0,00"
            
            hist_tree.insert("", "end", values=(date_str, g_by, cost_str, co_str))
            
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def process_contract(self, preview=False):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one estimate to generate a contract.")
            return
            
        projects = []
        clients_seen = {}
        total_cost = 0.0
        
        for item in selected:
            p_id, c_id = self.tree.item(item, "tags")
            est_num, c_name, cost_str, _ = self.tree.item(item, "values")
            
            self.cursor.execute("SELECT description, final_cost FROM projects WHERE id = ?", (p_id,))
            desc, db_cost = self.cursor.fetchone()
            
            projects.append({
                "id": p_id,
                "est_num": est_num,
                "desc": desc or "Serviços de consultoria em biologia analítica",
                "cost": db_cost or 0.0
            })
            total_cost += (db_cost or 0.0)
            clients_seen[c_id] = c_name
            
        primary_client_id = list(clients_seen.keys())[0]
        
        if len(clients_seen) > 1:
            res = messagebox.askyesno("Multiple Clients", "You have selected estimates belonging to different clients.\nDo you wish to combine them into a single contract?")
            if not res: return
            
            choices = [f"{c_id}: {name}" for c_id, name in clients_seen.items()]
            choice = simpledialog.askstring("Select Client", "Which client should be listed as the CONTRATANTE on the contract?\n\nOptions:\n" + "\n".join(choices))
            if not choice: return
            try:
                primary_client_id = choice.split(":")[0].strip()
            except:
                return
                
        self.verify_and_edit_client(primary_client_id, projects, total_cost, preview)

    def verify_and_edit_client(self, client_id, projects, total_cost, preview):
        try:
            conn_cli = sqlite3.connect(self.client_db_path)
            c_cli = conn_cli.cursor()
            c_cli.execute("SELECT name, nationality, marital_status, profession, id_number, id_issuer, cpf_cnpj, address, client_type FROM clients WHERE id = ?", (client_id,))
            cli_data = c_cli.fetchone()
            conn_cli.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to access client DB: {e}")
            return
            
        if not cli_data:
            messagebox.showerror("Error", "Client not found.")
            return
            
        name, nationality, marital_status, profession, id_number, id_issuer, cpf_cnpj, address, client_type = cli_data
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Verify Contract Details")
        dialog.geometry("550x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Review Payee / CONTRATANTE Information:", font=("Helvetica", 12, "bold")).pack(pady=10)
        ttk.Label(dialog, text="These fields will be printed on the contract. Any edits made here will also be saved back to the Client Manager.", wraplength=500, justify="center").pack(pady=(0, 15))
        
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)
        
        entries = {}
        fields = [
            ("Name", name),
            ("Nationality", nationality),
            ("Marital Status", marital_status),
            ("Profession", profession),
            ("ID Number (RG)", id_number),
            ("ID Issuer", id_issuer),
            ("CPF/CNPJ", cpf_cnpj),
            ("Additional Data", ""),
        ]
        
        for i, (label, val) in enumerate(fields):
            ttk.Label(frame, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=5)
            var = tk.StringVar(value=val or "")
            ttk.Entry(frame, textvariable=var, width=40).grid(row=i, column=1, sticky="w", padx=10, pady=5)
            entries[label] = var
            
        ttk.Label(frame, text="Address:").grid(row=len(fields), column=0, sticky="nw", pady=5)
        addr_text = tk.Text(frame, height=3, width=40)
        addr_text.grid(row=len(fields), column=1, sticky="w", padx=10, pady=5)
        addr_text.insert("1.0", address or "")
        
        def on_confirm():
            new_vals = {k: v.get().strip() for k, v in entries.items()}
            new_addr = addr_text.get("1.0", tk.END).strip()
            
            missing = [k for k, v in new_vals.items() if not v and k != "Additional Data"]
            if not new_addr: missing.append("Address")
            
            if missing:
                if not messagebox.askyesno("Missing Info", f"The following fields are empty:\n{', '.join(missing)}\n\nDo you want to generate the contract anyway with blank spaces?"):
                    return
                    
            try:
                conn_cli = sqlite3.connect(self.client_db_path)
                c_cli = conn_cli.cursor()
                c_cli.execute('''
                    UPDATE clients 
                    SET name=?, nationality=?, marital_status=?, profession=?, id_number=?, id_issuer=?, cpf_cnpj=?, address=?
                    WHERE id=?
                ''', (new_vals["Name"], new_vals["Nationality"], new_vals["Marital Status"], new_vals["Profession"], 
                      new_vals["ID Number (RG)"], new_vals["ID Issuer"], new_vals["CPF/CNPJ"], new_addr, client_id))
                conn_cli.commit()
                conn_cli.close()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to save client info: {e}")
                return
                
            dialog.destroy()
            
            client_dict = {
                "name": new_vals["Name"],
                "nationality": new_vals["Nationality"],
                "marital_status": new_vals["Marital Status"],
                "profession": new_vals["Profession"],
                "id_number": new_vals["ID Number (RG)"],
                "id_issuer": new_vals["ID Issuer"],
                "cpf_cnpj": new_vals["CPF/CNPJ"],
                "additional_data": new_vals.get("Additional Data", ""),
                "address": new_addr,
                "id": client_id
            }
            self.generate_pdf(client_dict, projects, total_cost, preview)
            
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Generate Contract", command=on_confirm, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=10)

    def preview_contract_template(self, override_settings):
        client = {
            "name": "João da Silva", "nationality": "brasileira",
            "marital_status": "casado", "profession": "Engenheiro",
            "id_number": "12.345.678-9", "id_issuer": "SSP/SP",
            "cpf_cnpj": "123.456.789-00",
            "additional_data": "Exemplo de dados adicionais.",
            "address": "Rua Exemplo, 123, Bairro, Cidade, SP"
        }
        projects = [{
            "est_num": "999-01v1",
            "desc": "Projeto de Exemplo para Visualização",
            "cost": 1500.00
        }]
        self.generate_pdf(client, projects, 1500.00, is_preview=True, override_settings=override_settings)

    def generate_pdf(self, client, projects, total_cost, is_preview, override_settings=None):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Dependency Missing", "Please install reportlab to generate PDFs.\nCommand: pip install reportlab")
            return
            
        est_num_str = "_".join([p["est_num"].split("v")[0] for p in projects])[:30]
        
        if is_preview:
            pdf_path = os.path.join(tempfile.gettempdir(), f"Preview_Contrato_{est_num_str}.pdf")
        else:
            pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Contrato_Quarium_{est_num_str}.pdf", title="Save Contract PDF", filetypes=[("PDF files", "*.pdf")])
            if not pdf_path: return
            
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm)
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, spaceAfter=20, alignment=1)
        normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=11, spaceAfter=12, alignment=4, leading=16) # Justified
        bold_style = ParagraphStyle('BoldStyle', parent=normal_style, fontName='Helvetica-Bold')
        
        settings = override_settings if override_settings else self.load_settings()
        NumberedCanvas.contract_footer_text = settings.get("contract_footer", settings.get("footer_text", "Quarium Consultoria em Biologia Analítica, Ltda. | Campinas, SP | Email: quarium.bio@gmail.com"))
        
        est_logo_file = settings.get("estimate_logo", "QLogo.png")
        logo_path = os.path.join(BASE_DIR, est_logo_file)
        if not os.path.exists(logo_path):
            logo_path = os.path.join(BASE_DIR, 'QLogo.png')
            
        if os.path.exists(logo_path):
            logo = RLImage(logo_path, width=3*cm, height=3*cm, kind='proportional')
            elements.append(logo)
            elements.append(Spacer(1, 0.5*cm))
            
        elements.append(Paragraph("TERMO DE ACEITE DE SERVIÇO", title_style))
        
        c_name = client.get("name", "___________________")
        c_nat = client.get("nationality", "___________________")
        c_mar = client.get("marital_status", "___________________")
        c_prof = client.get("profession", "___________________")
        c_rg = client.get("id_number", "______________")
        c_iss = client.get("id_issuer", "SSP")
        c_cpf = client.get("cpf_cnpj", "______________")
        c_addr = client.get("address", "______________________________________________________")
        c_add_data = client.get("additional_data", "")
        
        def_contratada = "<b>Contratada:</b> Quarium Consultoria em Biologia Analítica LTDA, pessoa jurídica de direito privado, inscrita no CNPJ 53.429.415/0001-41, com sede na Rua Maria Bicego, 323, Vila Santa Isabel, Campinas, SP. CEP: 13084-639, doravante denominada QUARIUM e neste ato representada por seu representante legal Lícia Carla da Silva Costa, Brasileira, Solteira, Bióloga, portadora do documento de identidade n° 56.727.423-8 emitido por SSP/SP, inscrito sob o CPF n° 086.388.957-39."
        contratada_text = settings.get("contract_contratada", def_contratada)
        elements.append(Paragraph(contratada_text, normal_style))
        
        def_contratante = "<b>Contratante:</b> {name}, pessoa física, nacionalidade {nationality}, estado civil {marital_status}, profissão {profession}, portador(a) do documento de identidade n° {id_number}, emissor {id_issuer}, inscrito(a) sob o CPF n° {cpf_cnpj}. {additional_data} doravante denominada CONTRATANTE."
        contratante_template = settings.get("contract_contratante", def_contratante)
        
        format_kwargs = {"name": c_name, "nationality": c_nat, "marital_status": c_mar, "profession": c_prof, "id_number": c_rg, "id_issuer": c_iss, "cpf_cnpj": c_cpf, "additional_data": c_add_data}
        try:
            contratante_text = contratante_template.format(**format_kwargs)
        except Exception:
            contratante_text = contratante_template.replace('{name}', c_name).replace('{cpf_cnpj}', c_cpf).replace('{additional_data}', c_add_data)
            
        elements.append(Paragraph(contratante_text, normal_style))
        
        
        # Projects Table
        table_data = [[Paragraph("<b>N° Orçamento</b>", normal_style), Paragraph("<b>Descrição do Projeto</b>", normal_style), Paragraph("<b>Custo</b>", normal_style)]]
        
        for p in projects:
            table_data.append([
                Paragraph(p["est_num"], normal_style),
                Paragraph(p["desc"].replace('\n', '<br/>'), normal_style),
                Paragraph(self.format_br_currency(p["cost"]), normal_style)
            ])
            
        table_data.append(["", Paragraph("<b>VALOR TOTAL:</b>", normal_style), Paragraph(f"<b>{self.format_br_currency(total_cost)}</b>", normal_style)])
        
        proj_table = Table(table_data, colWidths=[3.5*cm, A4[0] - 10.5*cm, 3*cm])
        proj_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('INNERGRID', (0,0), (-1,-2), 0.25, colors.grey),
            ('BOX', (0,0), (-1,-2), 0.25, colors.grey),
            ('LINEABOVE', (1,-1), (-1,-1), 1, colors.black)
        ]))
        
        docx_path = os.path.join(BASE_DIR, 'ContractTemplate.docx')
        if os.path.exists(docx_path):
            if not DOCX_AVAILABLE:
                elements.append(Spacer(1, 1*cm))
                elements.append(Paragraph("<b>[ERROR: 'python-docx' library is not installed. Please run 'pip install python-docx' to render the contract body.]</b>", normal_style))
            else:
                try:
                    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
                    doc_body = docx.Document(docx_path)
                    for i, p in enumerate(doc_body.paragraphs):
                        text = ""
                        for run in p.runs:
                            r_text = run.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            if run.bold: r_text = f"<b>{r_text}</b>"
                            if run.italic: r_text = f"<i>{r_text}</i>"
                            if run.underline: r_text = f"<u>{r_text}</u>"
                            text += r_text
                        
                        if not text.strip():
                            elements.append(Spacer(1, 12))
                            continue
                            
                        align = TA_LEFT
                        if p.alignment == WD_ALIGN_PARAGRAPH.CENTER: align = TA_CENTER
                        elif p.alignment == WD_ALIGN_PARAGRAPH.RIGHT: align = TA_RIGHT
                        elif p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY: align = TA_JUSTIFY
                        
                        left_indent = p.paragraph_format.left_indent.pt if p.paragraph_format.left_indent else 0
                        first_line = p.paragraph_format.first_line_indent.pt if p.paragraph_format.first_line_indent else 0
                        space_before = p.paragraph_format.space_before.pt if p.paragraph_format.space_before else 0
                        space_after = p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 6
                        
                        is_list = False
                        if p.style and p.style.name and any(x in p.style.name for x in ['List', 'Lista']):
                            is_list = True
                        if '<w:numPr>' in p._element.xml:
                            is_list = True
                            
                        if is_list:
                            if not text.startswith('•') and not text.lstrip().startswith(('1.', 'a.', 'i.', '-')):
                                text = f"• {text}"
                            if left_indent == 0:
                                left_indent = 20
                                
                        custom_style = ParagraphStyle(
                            f'Custom_{i}', 
                            parent=normal_style,
                            alignment=align,
                            leftIndent=left_indent,
                            firstLineIndent=first_line,
                            spaceBefore=space_before,
                            spaceAfter=space_after
                        )
                        elements.append(Paragraph(text, custom_style))
                except Exception as e:
                    elements.append(Spacer(1, 1*cm))
                    elements.append(Paragraph(f"<b>[ERROR reading ContractTemplate.docx: {e}]</b>", normal_style))
        
        elements.append(Spacer(1, 1*cm))
        elements.append(proj_table)
        
        # Signatures
        sig_style = ParagraphStyle('SigStyle', parent=normal_style, alignment=1)
        elements.append(Spacer(1, 2*cm))
        
        elements.append(Paragraph("_____________________________________________________", sig_style))
        elements.append(Paragraph(f"<b>CONTRATANTE</b><br/>{c_name}", sig_style))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(Paragraph("Local e Data: _________________________________, ____ de __________________ de 20__.", sig_style))
        
        elements.append(Spacer(1, 2*cm))
        
        elements.append(Paragraph("_____________________________________________________", sig_style))
        elements.append(Paragraph("<b>CONTRATADA</b><br/>Quarium Consultoria em Biologia Analítica", sig_style))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(Paragraph("Local e Data: _________________________________, ____ de __________________ de 20__.", sig_style))
        
        try:
            doc.build(elements, canvasmaker=NumberedCanvas)
            if is_preview:
                webbrowser.open(pdf_path)
            else:
                # Record generation in DB
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute("INSERT INTO contracts (client_id, total_cost, generated_at, generated_by) VALUES (?, ?, ?, ?)",
                                    (client["id"], total_cost, now, self.current_user))
                contract_id = self.cursor.lastrowid
                
                for p in projects:
                    self.cursor.execute("INSERT INTO contract_projects (contract_id, project_id) VALUES (?, ?)", (contract_id, p["id"]))
                    
                self.conn.commit()
                self.load_data()
                messagebox.showinfo("Success", f"Contract generated and recorded successfully:\n{pdf_path}")
                
        except PermissionError:
            messagebox.showerror("Export Error", "Cannot generate file. The previous file is likely currently open in your PDF viewer. Please close it and try again.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not generate PDF: {e}")