import customtkinter as ctk
import os
from dotenv import load_dotenv
import asyncio
import threading
from datetime import datetime
from tkinter import messagebox
import discord
from discord.ext import commands
from google.cloud import firestore

# Load the variables from the .env file
load_dotenv()

# --- CLOUD CONTEXT CONFIGURATION ---
CREDENTIALS_PATH = "firebase_credentials.json"
SAVINGS_CATEGORIES = ["General", "Rainy Days", "Travel", "Gaming"]
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Assign the secret key location globally for the Firebase SDK
if os.path.exists(CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
else:
    print(f"⚠️ Error: {CREDENTIALS_PATH} missing from directory. Cloud sync offline.")

def get_firestore_client():
    try:
        return firestore.Client()
    except Exception as e:
        print(f"❌ Could not initialize Firestore Client: {e}")
        return None

def load_data():
    """Fetches the universal financial ledger dataset directly from the Firestore Cloud document"""
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("userdata").document("premium_wallet")
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Maintain data integrity safeguards
                if "savings" not in data:
                    data["savings"] = {cat: 0.0 for cat in SAVINGS_CATEGORIES}
                for cat in SAVINGS_CATEGORIES:
                    if cat not in data["savings"]:
                        data["savings"][cat] = 0.0
                if "months" not in data:
                    data["months"] = {}
                return data
        except Exception as e:
            print(f"⚠️ Failed reading from Firestore cloud: {e}")
            
    # Cloud fallback architecture
    return {"current": 0.0, "savings": {cat: 0.0 for cat in SAVINGS_CATEGORIES}, "months": {}}

def save_data(data):
    """Pushes any structural state modifications instantly up to the Firestore Cloud backend"""
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("userdata").document("premium_wallet")
            doc_ref.set(data) # Overwrites or creates the cloud document layout dynamically
            return True
        except Exception as e:
            print(f"❌ Failed pushing data to Firestore cloud: {e}")
    return False


# --- Streamlined Transaction Modal ---
class CenteredInput(ctk.CTkToplevel):
    def __init__(self, action_mode, sky_blue):
        super().__init__()
        self.geometry("+9999+9999")
        self.title(f"Unify | {action_mode}")
        self.configure(fg_color="#0D0D0D")
        self.result = None
        self.action_mode = action_mode  
        
        window_height = 520 if action_mode == "DEPOSIT" else 600
        
        self.lbl_header = ctk.CTkLabel(self, text=action_mode.title(), font=("Arial", 22, "bold"), text_color=sky_blue)
        self.lbl_header.pack(anchor="w", padx=30, pady=(25, 10))

        self.field_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.field_frame.pack(fill="both", expand=True, padx=30, pady=5)

        if self.action_mode == "DEPOSIT":
            ctk.CTkLabel(self.field_frame, text="Destination Account", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
            dest_lbl = ctk.CTkLabel(self.field_frame, text="Current Checking Account (Auto)", fg_color="#141414", height=32, corner_radius=6, text_color="#A9A9A9", anchor="w")
            dest_lbl.pack(fill="x", pady=(2, 12))
            dest_lbl.configure(padx=10)
        else:
            ctk.CTkLabel(self.field_frame, text="Target Account Source", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 3))
            self.acc_var = ctk.StringVar(value="Current")
            self.seg_btn = ctk.CTkSegmentedButton(self.field_frame, values=["Current", "Savings"], 
                                                  variable=self.acc_var, selected_color=sky_blue, 
                                                  selected_hover_color=sky_blue, unselected_color="#141414",
                                                  height=32, command=self.toggle_savings_menu)
            self.seg_btn.pack(fill="x", pady=(0, 12))

            self.cat_label = ctk.CTkLabel(self.field_frame, text="Savings Allocation Bucket", text_color="#666666", font=("Arial", 11, "bold"))
            self.cat_menu = ctk.CTkOptionMenu(self.field_frame, values=SAVINGS_CATEGORIES, fg_color="#141414", button_color="#1A1A1A", text_color="white", height=32)

        fields = [("Transaction Name", "ent_purpose", "e.g. Monthly Salary, Grocery Run"), 
                  ("Amount (RM)", "ent_amount", "0.00"), 
                  ("Date Reference", "ent_date", "DD/MM/YYYY"),
                  ("Transaction Notes", "ent_notes", "Add custom notes, context or hashtags here...")]
        
        for label, attr, placeholder in fields:
            ctk.CTkLabel(self.field_frame, text=label, text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(4, 2))
            setattr(self, attr, ctk.CTkEntry(self.field_frame, placeholder_text=placeholder, fg_color="#141414", border_color="#222", height=32, corner_radius=6))
            getattr(self, attr).pack(fill="x", pady=(0, 8))

        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="bottom", fill="x", padx=30, pady=(10, 25))

        self.btn_cancel = ctk.CTkButton(self.action_frame, text="Cancel", fg_color="transparent", text_color="#A9A9A9", border_width=1, border_color="#222", font=("Arial", 12), height=34, corner_radius=6, command=self.destroy)
        self.btn_cancel.pack(side="left", expand=True, padx=(0, 6), fill="x")

        self.btn_confirm = ctk.CTkButton(self.action_frame, text="Confirm", fg_color=sky_blue, text_color="black", font=("Arial", 12, "bold"), height=34, corner_radius=6, command=self.on_submit)
        self.btn_confirm.pack(side="left", expand=True, padx=(6, 0), fill="x")
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (360 // 2)
        y = (self.winfo_screenheight() // 2) - (window_height // 2)
        self.geometry(f"360x{window_height}+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(self.master)
        self.grab_set()
        self.wait_window()

    def toggle_savings_menu(self, selected_value):
        if selected_value == "Savings":
            self.cat_label.pack(anchor="w", after=self.seg_btn, pady=(4, 2))
            self.cat_menu.pack(fill="x", pady=(0, 12), after=self.cat_label)
        else:
            self.cat_label.pack_forget()
            self.cat_menu.pack_forget()

    def on_submit(self):
        try:
            account_selection = "current" if self.action_mode == "DEPOSIT" else self.acc_var.get().lower()
            category_selection = self.cat_menu.get() if (self.action_mode == "SPENDING" and self.acc_var.get() == "Savings") else "General"
            
            self.result = {
                "account": account_selection,
                "category": category_selection,
                "purpose": self.ent_purpose.get(),
                "amount": float(self.ent_amount.get()),
                "date": self.ent_date.get(),
                "notes": self.ent_notes.get()
            }
            self.destroy()
        except: pass


# --- Universal Multi-Directional Transfer Modal ---
class TransferModal(ctk.CTkToplevel):
    def __init__(self, sky_blue, current_balance, savings_data):
        super().__init__()
        self.geometry("+9999+9999")
        self.title("Unify | Internal Transfer")
        self.configure(fg_color="#0D0D0D")
        self.result = None
        self.current_balance = current_balance
        self.savings_data = savings_data
        
        self.account_options = ["Current"] + SAVINGS_CATEGORIES
        
        ctk.CTkLabel(self, text="Internal Transfer", font=("Arial", 24, "bold"), text_color=sky_blue).pack(anchor="w", padx=35, pady=(25, 4))
        ctk.CTkLabel(self, text="Transfer seamlessly across your workspaces and vaults.", font=("Arial", 12), text_color="#555").pack(anchor="w", padx=35, pady=(0, 15))

        self.field_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.field_frame.pack(fill="both", expand=True, padx=35, pady=5)

        ctk.CTkLabel(self.field_frame, text="From Account Source", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.from_menu = ctk.CTkOptionMenu(self.field_frame, values=self.account_options, fg_color="#141414", button_color="#1A1A1A", text_color="white", height=34, command=self.sync_balance_hint)
        self.from_menu.pack(fill="x", pady=(2, 14))

        ctk.CTkLabel(self.field_frame, text="To Destination Target", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.to_menu = ctk.CTkOptionMenu(self.field_frame, values=self.account_options, fg_color="#141414", button_color="#1A1A1A", text_color="white", height=34, command=self.sync_balance_hint)
        self.to_menu.set(SAVINGS_CATEGORIES[0]) 
        self.to_menu.pack(fill="x", pady=(2, 14))

        self.lbl_balance_hint = ctk.CTkLabel(self.field_frame, text="", text_color="#A9A9A9", fg_color="#141414", height=34, corner_radius=6, anchor="w")
        self.lbl_balance_hint.pack(fill="x", pady=(0, 14))
        self.lbl_balance_hint.configure(padx=12)

        ctk.CTkLabel(self.field_frame, text="Transfer Amount (RM)", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.ent_amount = ctk.CTkEntry(self.field_frame, placeholder_text="0.00", fg_color="#141414", border_color="#222", height=34, corner_radius=6)
        self.ent_amount.pack(fill="x", pady=(2, 14))

        ctk.CTkLabel(self.field_frame, text="Transfer Notes / Context", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.ent_notes = ctk.CTkEntry(self.field_frame, placeholder_text="e.g. Funding vacation, splitting allocations...", fg_color="#141414", border_color="#222", height=34, corner_radius=6)
        self.ent_notes.pack(fill="x", pady=(2, 10))

        self.sync_balance_hint()

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="bottom", fill="x", padx=35, pady=(15, 30))

        self.btn_cancel = ctk.CTkButton(self.action_frame, text="Cancel", fg_color="transparent", text_color="#A9A9A9", border_width=1, border_color="#222", font=("Arial", 12), height=36, corner_radius=6, command=self.destroy)
        self.btn_cancel.pack(side="left", expand=True, padx=(0, 8), fill="x")

        self.btn_confirm = ctk.CTkButton(self.action_frame, text="Transfer", fg_color=sky_blue, text_color="black", font=("Arial", 12, "bold"), height=36, corner_radius=6, command=self.on_submit)
        self.btn_confirm.pack(side="left", expand=True, padx=(8, 0), fill="x")
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.winfo_screenheight() // 2) - (560 // 2)
        self.geometry(f"420x560+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(self.master)
        self.grab_set()
        self.wait_window()

    def sync_balance_hint(self, *args):
        src = self.from_menu.get()
        if src == "Current":
            self.lbl_balance_hint.configure(text=f"Available Checking: RM {self.current_balance:,.2f}")
        else:
            vault_bal = self.savings_data.get(src, 0.0)
            self.lbl_balance_hint.configure(text=f"Available Vault ({src}): RM {vault_bal:,.2f}")

    def on_submit(self):
        src = self.from_menu.get()
        dest = self.to_menu.get()
        if src == dest: return
            
        try:
            amt = float(self.ent_amount.get())
            if amt <= 0: return
            
            self.result = {
                "from_acc": src,
                "to_acc": dest,
                "amount": amt,
                "notes": self.ent_notes.get()
            }
            self.destroy()
        except: pass


# --- Master Workspace Layout ---
class UnifyModern(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.title("UNIFY | Financial Cloud Workspace")
        
        window_width = 950
        window_height = 620
        self.resizable(False, False)
        
        self.black = "#0A0A0A"
        self.card_bg = "#111111"
        self.sky_blue = "#87CEEB"
        self.configure(fg_color=self.black)

        # ==========================================
        # LEFT COLUMN: CONTROL SIDEBAR
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, fg_color="#0D0D0D", width=280, corner_radius=0, border_width=1, border_color="#141414")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="UNIFY.", font=("Arial", 22, "bold"), text_color="white").pack(anchor="w", padx=25, pady=(30, 20))

        self.card_current = ctk.CTkFrame(self.sidebar, fg_color=self.card_bg, corner_radius=12, height=75)
        self.card_current.pack(fill="x", padx=20, pady=6)
        self.card_current.pack_propagate(False)
        ctk.CTkLabel(self.card_current, text="CURRENT CHECKING (CLOUD)", font=("Arial", 10, "bold"), text_color="#555").pack(anchor="w", padx=15, pady=(12, 0))
        self.lbl_current = ctk.CTkLabel(self.card_current, text="", font=("Arial", 18, "bold"), text_color="white")
        self.lbl_current.pack(anchor="w", padx=15)

        self.card_savings = ctk.CTkFrame(self.sidebar, fg_color=self.card_bg, corner_radius=12, height=75)
        self.card_savings.pack(fill="x", padx=20, pady=6)
        self.card_savings.pack_propagate(False)
        ctk.CTkLabel(self.card_savings, text="CORE SAVINGS TOTAL", font=("Arial", 10, "bold"), text_color=self.sky_blue).pack(anchor="w", padx=15, pady=(12, 0))
        self.lbl_savings = ctk.CTkLabel(self.card_savings, text="", font=("Arial", 18, "bold"), text_color="white")
        self.lbl_savings.pack(anchor="w", padx=15)

        self.action_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.action_box.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(self.action_box, text="↓  Deposit Funds", fg_color=self.sky_blue, hover_color="#70C0E0", text_color="black", font=("Arial", 12, "bold"), height=35, corner_radius=6, command=lambda: self.open_input("DEPOSIT")).pack(fill="x", pady=4)
        ctk.CTkButton(self.action_box, text="†  Log Spending", fg_color="#141414", hover_color="#1F1F1F", border_width=1, border_color="#222", text_color="white", font=("Arial", 12, "bold"), height=35, corner_radius=6, command=lambda: self.open_input("SPENDING")).pack(fill="x", pady=4)
        ctk.CTkButton(self.action_box, text="⇄  Move Money", fg_color="#141414", hover_color="#1F1F1F", border_width=1, border_color="#222", text_color="#A9A9A9", font=("Arial", 12, "bold"), height=35, corner_radius=6, command=self.open_transfer).pack(fill="x", pady=4)

        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=20, side="bottom", pady=25)
        
        self.btn_nav_dashboard = ctk.CTkButton(self.nav_frame, text="❖    Savings Vaults", fg_color="#141414", text_color="white", anchor="w", font=("Arial", 12, "bold"), height=38, corner_radius=6, command=self.show_dashboard_view)
        self.btn_nav_dashboard.pack(fill="x", pady=3)
        self.btn_nav_history = ctk.CTkButton(self.nav_frame, text="☲    Transaction Ledger", fg_color="transparent", text_color="#888", anchor="w", font=("Arial", 12, "bold"), height=38, corner_radius=6, command=self.show_ledger_view)
        self.btn_nav_history.pack(fill="x", pady=3)

        # ==========================================
        # RIGHT COLUMN: MAIN CANVAS WORKSPACE
        # ==========================================
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.pack(side="right", fill="both", expand=True, padx=30, pady=30)

        self.view_dashboard = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.view_ledger = ctk.CTkFrame(self.workspace, fg_color="transparent")
        
        self.show_dashboard_view()
        self.update_dashboard_balances()
        
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = (screen_width // 2) - (window_width // 2)
        center_y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    def trigger_ui_refresh(self):
        """Forces app to fetch latest data state from Firebase cloud bucket"""
        self.data = load_data()
        self.update_dashboard_balances()
        if self.view_dashboard.winfo_manager(): 
            self.render_dashboard_content()
        else: 
            self.render_ledger_content()

    def show_dashboard_view(self):
        self.btn_nav_dashboard.configure(fg_color="#141414", text_color="white")
        self.btn_nav_history.configure(fg_color="transparent", text_color="#888")
        self.view_ledger.pack_forget()
        self.view_dashboard.pack(fill="both", expand=True)
        self.render_dashboard_content()

    def show_ledger_view(self):
        self.btn_nav_dashboard.configure(fg_color="transparent", text_color="#888")
        self.btn_nav_history.configure(fg_color="#141414", text_color="white")
        self.view_dashboard.pack_forget()
        self.view_ledger.pack(fill="both", expand=True)
        self.render_ledger_content()

    def render_dashboard_content(self):
        for widget in self.view_dashboard.winfo_children(): widget.destroy()
        ctk.CTkLabel(self.view_dashboard, text="Active Cloud Savings Vaults", font=("Arial", 18, "bold"), text_color="white").pack(anchor="w", pady=(0, 15))
        
        grid_frame = ctk.CTkFrame(self.view_dashboard, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)
        grid_frame.rowconfigure((0, 1), weight=1, uniform="equal")
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")

        total_savings = sum(self.data["savings"].values())

        for idx, cat in enumerate(SAVINGS_CATEGORIES):
            r, c = idx // 2, idx % 2
            val = self.data["savings"].get(cat, 0.0)
            pct = (val / total_savings) if total_savings > 0 else 0.0
            
            box = ctk.CTkFrame(grid_frame, fg_color=self.card_bg, corner_radius=14, border_width=1, border_color="#1A1A1A")
            box.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            box.pack_propagate(False)

            ctk.CTkLabel(box, text=cat.upper(), font=("Arial", 11, "bold"), text_color="#666").pack(anchor="w", padx=20, pady=(18, 2))
            ctk.CTkLabel(box, text=f"RM {val:,.2f}", font=("Arial", 22, "bold"), text_color="white").pack(anchor="w", padx=20)
            
            prog_bar = ctk.CTkProgressBar(box, height=5, progress_color=self.sky_blue, fg_color="#222", corner_radius=10)
            prog_bar.set(pct)
            prog_bar.pack(fill="x", padx=20, side="bottom", pady=20)
            
            ctk.CTkLabel(box, text=f"{pct*100:.1f}% of core total", font=("Arial", 10), text_color="#444").pack(anchor="w", padx=20, side="bottom")

    def render_ledger_content(self):
        for widget in self.view_ledger.winfo_children(): widget.destroy()
        header = ctk.CTkFrame(self.view_ledger, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(header, text="Transaction History Ledger", font=("Arial", 18, "bold"), text_color="white").pack(side="left")
        
        filter_box = ctk.CTkFrame(header, fg_color="transparent")
        filter_box.pack(side="right")
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.populate_ledger_feed)
        
        self.ent_search = ctk.CTkEntry(filter_box, placeholder_text="🔍 Search transactions...", width=180, height=30, fg_color="#141414", border_color="#222")
        self.ent_search.pack(side="left", padx=(0, 10))

        self.month_sel = ctk.CTkOptionMenu(filter_box, values=self.get_month_list(), width=140, height=30, fg_color="#141414", button_color="#1A1A1A", command=self.populate_ledger_feed)
        self.month_sel.pack(side="left")

        self.ledger_scroll = ctk.CTkScrollableFrame(self.view_ledger, fg_color="transparent", scrollbar_button_color="#222")
        self.ledger_scroll.pack(fill="both", expand=True)
        self.populate_ledger_feed()

    def populate_ledger_feed(self, *args):
        for widget in self.ledger_scroll.winfo_children(): widget.destroy()
        m = self.month_sel.get()
        search_query = self.ent_search.get().strip().lower() if hasattr(self, 'ent_search') else ""
        
        if m in self.data["months"] and self.data["months"][m]:
            visible_rows = 0
            for item in self.data["months"][m]:
                purpose_match = search_query in item.get("purpose", "").lower()
                notes_match = search_query in item.get("notes", "").lower()
                
                if search_query and not (purpose_match or notes_match):
                    continue
                
                visible_rows += 1
                row = ctk.CTkFrame(self.ledger_scroll, fg_color=self.card_bg, corner_radius=8, height=65) 
                row.pack(fill="x", pady=4)
                row.pack_propagate(False)

                details = ctk.CTkFrame(row, fg_color="transparent")
                details.pack(side="left", padx=15, pady=6)
                
                acc_label = item.get("account", "current").upper()
                if acc_label == "SAVINGS":
                    tag_str = f"Savings ↗ {item.get('category', 'General')}"
                    tag_color = self.sky_blue
                elif acc_label == "INTERNAL_TRANSFER":
                    tag_str = f"Internal Move  •  {item.get('category', 'General')}"
                    tag_color = "#D1D1D1"
                else:
                    tag_str = "Current Checking"
                    tag_color = "#666"

                note_text = f" | Notes: {item['notes']}" if item.get("notes") else ""

                ctk.CTkLabel(details, text=item["purpose"], font=("Arial", 13, "bold"), text_color="white").pack(anchor="w")
                ctk.CTkLabel(details, text=f"{tag_str}  •  {item['date']}{note_text}", font=("Arial", 10), text_color=tag_color).pack(anchor="w")

                color = self.sky_blue if item["type"] in ["INCOME", "TRANSFER_IN"] else "#FF5F5F"
                prefix = "+" if item["type"] in ["INCOME", "TRANSFER_IN"] else "-"
                ctk.CTkLabel(row, text=f"{prefix}RM {item['amount']:,.2f}", font=("Arial", 13, "bold"), text_color=color).pack(side="right", padx=15, pady=15)
                
            if visible_rows == 0:
                ctk.CTkLabel(self.ledger_scroll, text="No transactions found matching your search.", font=("Arial", 12), text_color="#555").pack(pady=40)
        else:
            ctk.CTkLabel(self.ledger_scroll, text="No transactions recorded for this month.", font=("Arial", 12), text_color="#444").pack(pady=40)

    def open_transfer(self):
        modal = TransferModal(self.sky_blue, self.data["current"], self.data["savings"])
        res = modal.result
        if res:
            src = res["from_acc"]
            dest = res["to_acc"]
            amt = res["amount"]
            notes = res["notes"]
            
            if src == "Current":
                if self.data["current"] < amt:
                    messagebox.showwarning("Insufficient Funds", "Transfer Denied! Your Checking balance is too low.")
                    return
            else:
                current_vault_bal = self.data["savings"].get(src, 0.0)
                if current_vault_bal < amt:
                    messagebox.showwarning("Insufficient Funds", f"Transfer Denied! Your {src} Vault balance is too low.")
                    return
                
            if src == "Current": self.data["current"] -= amt
            else: self.data["savings"][src] -= amt
                
            if dest == "Current": self.data["current"] += amt
            else: self.data["savings"][dest] += amt
                
            if src == "Current":
                purpose_text = f"Moved to {dest} Vault"
                type_text = "TRANSFER_OUT"
                category_tag = dest
            elif dest == "Current":
                purpose_text = f"Pulled from {src} Vault"
                type_text = "TRANSFER_IN"
                category_tag = src
            else:
                purpose_text = f"Reallocated {src} ➔ {dest}"
                type_text = "TRANSFER_OUT" 
                category_tag = f"{src} to {dest}"
                
            m_key = datetime.now().strftime("%B %Y")
            if m_key not in self.data["months"]: self.data["months"][m_key] = []
            
            self.data["months"][m_key].insert(0, {
                "account": "internal_transfer",
                "category": category_tag,
                "purpose": purpose_text,
                "amount": amt,
                "type": type_text,
                "date": datetime.now().strftime("%d/%m/%Y"),
                "notes": notes
            })
            
            save_data(self.data)
            self.trigger_ui_refresh()

    def open_input(self, action_mode):
        form = CenteredInput(action_mode, self.sky_blue)
        res = form.result
        if res:
            amt = res["amount"]
            acc = res["account"]
            cat = res["category"]
            
            if action_mode == "SPENDING":
                if acc == "current":
                    if self.data["current"] < amt:
                        messagebox.showwarning("Insufficient Funds", "Spending Blocked! Your Current Checking balance is too low.")
                        return
                else:
                    current_vault_bal = self.data["savings"].get(cat, 0.0)
                    if current_vault_bal < amt:
                        messagebox.showwarning("Insufficient Funds", f"Spending Blocked! Your {cat} Vault balance is too low.")
                        return

            if action_mode == "DEPOSIT":
                self.data["current"] += amt
                type_tag = "INCOME"
            else:
                if acc == "current": self.data["current"] -= amt
                else: self.data["savings"][cat] -= amt
                type_tag = "EXPENSES"
            
            try: m_key = datetime.strptime(res["date"], "%d/%m/%Y").strftime("%B %Y")
            except: m_key = datetime.now().strftime("%B %Y")

            if m_key not in self.data["months"]: self.data["months"][m_key] = []
            self.data["months"][m_key].insert(0, {**res, "type": type_tag})
            
            save_data(self.data)
            self.trigger_ui_refresh()

    def update_dashboard_balances(self):
        total_savings = sum(self.data["savings"].values())
        self.lbl_current.configure(text=f"RM {self.data['current']:,.2f}")
        self.lbl_savings.configure(text=f"RM {total_savings:,.2f}")

    def get_month_list(self):
        months = list(self.data["months"].keys())
        curr = datetime.now().strftime("%B %Y")
        if curr not in months: months.append(curr)
        return sorted(months, reverse=True)


# ==========================================
# DISCORD BOT BACKEND ARCHITECTURE
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
app_instance = None  

@bot.event
async def on_ready():
    print(f"⚡ Unify Cloud Bot Active! Online as {bot.user}")

@bot.command(name="balance")
async def check_balance(ctx):
    """Command: !balance"""
    # Fetch fresh live data from Firebase directly, regardless of whether the PC is open
    current_data = load_data()
    
    current_val = current_data["current"]
    savings_dict = current_data["savings"]
    total_savings = sum(savings_dict.values())
    
    embed = discord.Embed(title="📊 Unify Cloud Balance Ledger", color=0x87CEEB, timestamp=datetime.now())
    embed.add_field(name="💳 Checking Account", value=f"RM {current_val:,.2f}", inline=False)
    embed.add_field(name="📈 Total Savings Vaults", value=f"RM {total_savings:,.2f}", inline=False)
    
    for cat, val in savings_dict.items():
        embed.add_field(name=f"  • {cat}", value=f"RM {val:,.2f}", inline=True)
        
    await ctx.send(embed=embed)

@bot.command(name="deposit")
async def discord_deposit(ctx, amount: float, *, purpose: str):
    """Command: !deposit 150.00 Freelance"""
    if amount <= 0:
        await ctx.send("❌ Amount must be greater than 0.")
        return

    current_data = load_data()
    current_data["current"] += amount
    m_key = datetime.now().strftime("%B %Y")
    if m_key not in current_data["months"]: current_data["months"][m_key] = []
    
    current_data["months"][m_key].insert(0, {
        "account": "current",
        "category": "General",
        "purpose": purpose,
        "amount": amount,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": "Logged via Discord Cloud Client",
        "type": "INCOME"
    })
    
    save_data(current_data)
    
    # If the local app happens to be open right now, trigger a thread-safe UI repaint
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)
        
    await ctx.send(f"✅ Deposited **RM {amount:,.2f}** for *'{purpose}'* into Cloud Ledger.")

@bot.command(name="spend")
async def discord_spend(ctx, account_type: str, amount: float, *, purpose: str):
    """Command: !spend current 50.00 Dinner OR !spend Gaming 120.00 Steam"""
    if amount <= 0:
        await ctx.send("❌ Amount must be greater than 0.")
        return

    current_data = load_data()
    account_type_clean = account_type.strip().lower()
    m_key = datetime.now().strftime("%B %Y")
    
    if account_type_clean == "current":
        if current_data["current"] < amount:
            await ctx.send(f"❌ Transaction Blocked! Insufficient funds (RM {current_data['current']:,.2f}).")
            return
        current_data["current"] -= amount
        acc_tag = "current"
        cat_tag = "General"
    else:
        matched_category = None
        for cat in SAVINGS_CATEGORIES:
            if cat.lower() == account_type_clean:
                matched_category = cat
                break
                
        if not matched_category:
            await ctx.send(f"❌ Unknown account. Choose `current` or: {', '.join(SAVINGS_CATEGORIES)}")
            return
            
        vault_bal = current_data["savings"].get(matched_category, 0.0)
        if vault_bal < amount:
            await ctx.send(f"❌ Blocked! Insufficient funds in {matched_category} Vault (RM {vault_bal:,.2f}).")
            return
            
        current_data["savings"][matched_category] -= amount
        acc_tag = "savings"
        cat_tag = matched_category

    if m_key not in current_data["months"]: current_data["months"][m_key] = []
    current_data["months"][m_key].insert(0, {
        "account": acc_tag,
        "category": cat_tag,
        "purpose": purpose,
        "amount": amount,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": "Logged via Discord Cloud Client",
        "type": "EXPENSES"
    })
    
    save_data(current_data)
    
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)
        
    await ctx.send(f"💸 Logged cloud expense of **RM {amount:,.2f}** for *'{purpose}'* from **{account_type}**.")

def run_discord_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot.run(BOT_TOKEN)

if __name__ == "__main__":
    app_instance = UnifyModern()
    
    if BOT_TOKEN != "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE":
        bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
        bot_thread.start()
    else:
        print("⚠️ Discord Bot initialization skipped: BOT_TOKEN not configured.")

    app_instance.mainloop()
