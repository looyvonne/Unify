import customtkinter as ctk
import os
from dotenv import load_dotenv
from datetime import datetime
from tkinter import messagebox
from google.cloud import firestore

# Load the variables from the .env file
load_dotenv()

# --- CLOUD CONTEXT CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = "firebase_credentials.json"

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
                if "categories" not in data:
                    data["categories"] = ["General", "Rainy Days", "Travel", "Gaming"]
                if "savings" not in data:
                    data["savings"] = {cat: 0.0 for cat in data["categories"]}
                for cat in data["categories"]:
                    if cat not in data["savings"]:
                        data["savings"][cat] = 0.0
                if "months" not in data:
                    data["months"] = {}
                return data
        except Exception as e:
            print(f"⚠️ Failed reading from Firestore cloud: {e}")
            
    return {
        "current": 0.0, 
        "savings": {"General": 0.0, "Rainy Days": 0.0, "Travel": 0.0, "Gaming": 0.0}, 
        "categories": ["General", "Rainy Days", "Travel", "Gaming"], 
        "months": {}
    }

def save_data(data):
    """Pushes any structural state modifications instantly up to the Firestore Cloud backend"""
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("userdata").document("premium_wallet")
            doc_ref.set(data)
            return True
        except Exception as e:
            print(f"❌ Failed pushing data to Firestore cloud: {e}")
    return False


# --- Dark Themed Text Input Dialog ---
class ThemedInputDialog(ctk.CTkToplevel):
    def __init__(self, title_text, prompt_text, sky_blue):
        super().__init__()
        self.title(title_text)
        self.configure(fg_color="#0D0D0D")
        self.result = None
        self.resizable(False, False)
        
        # FIX: Set explicit, spacious window boundaries immediately to prevent squishing
        window_width = 380
        window_height = 210
        
        # Center window coordinates calculations 
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (window_width // 2)
        y = (self.winfo_screenheight() // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Visual UI Layout structure elements
        ctk.CTkLabel(self, text=title_text, font=("Arial", 16, "bold"), text_color=sky_blue).pack(anchor="w", padx=25, pady=(20, 5))
        ctk.CTkLabel(self, text=prompt_text, font=("Arial", 11), text_color="#666").pack(anchor="w", padx=25, pady=(0, 15))
        
        self.entry = ctk.CTkEntry(self, placeholder_text="Type here...", fg_color="#141414", border_color="#222", height=34, corner_radius=6)
        self.entry.pack(fill="x", padx=25, pady=(0, 20))
        self.entry.focus()
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(0, 20))
        
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="transparent", text_color="#A9A9A9", border_width=1, border_color="#222", font=("Arial", 11), height=32, corner_radius=6, command=self.destroy).pack(side="left", expand=True, padx=(0, 5), fill="x")
        ctk.CTkButton(btn_frame, text="Confirm", fg_color=sky_blue, text_color="black", font=("Arial", 11, "bold"), height=32, corner_radius=6, command=self.on_confirm).pack(side="left", expand=True, padx=(5, 0), fill="x")
        
        self.entry.bind("<Return>", lambda event: self.on_confirm())
        
        self.grab_set()
        self.wait_window()
        
    def on_confirm(self):
        self.result = self.entry.get()
        self.destroy()


# --- Vault Specific Logs Modal ---
class VaultLogsModal(ctk.CTkToplevel):
    def __init__(self, vault_name, sky_blue, data):
        super().__init__()
        self.title(f"Unify | {vault_name} Logs")
        self.configure(fg_color="#0D0D0D")
        
        window_width = 580
        window_height = 600
        
        ctk.CTkLabel(self, text=f"{vault_name.upper()} Vault History", font=("Arial", 20, "bold"), text_color=sky_blue).pack(anchor="w", padx=30, pady=(25, 4))
        ctk.CTkLabel(self, text="Historical transactions linked explicitly to this allocation bucket.", font=("Arial", 11), text_color="#555").pack(anchor="w", padx=30, pady=(0, 15))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color="#222")
        self.scroll_frame.pack(fill="both", expand=True, padx=25, pady=5)

        matching_logs = []
        for month_name, items in data.get("months", {}).items():
            for item in items:
                is_savings_exp = item.get("account") == "savings" and item.get("category") == vault_name
                is_internal_trans = item.get("account") == "internal_transfer" and (vault_name in item.get("category", ""))
                
                if is_savings_exp or is_internal_trans:
                    item_copy = item.copy()
                    item_copy["_month_ctx"] = month_name
                    matching_logs.append(item_copy)

        try:
            matching_logs.sort(key=lambda x: datetime.strptime(x.get("date", "01/01/2000"), "%d/%m/%Y"), reverse=True)
        except Exception:
            pass 

        if not matching_logs:
            ctk.CTkLabel(self.scroll_frame, text="No transactional history found for this vault.", font=("Arial", 12), text_color="#444").pack(pady=100)
        else:
            for item in matching_logs:
                row = ctk.CTkFrame(self.scroll_frame, fg_color="#111111", corner_radius=10, height=70)
                row.pack(fill="x", pady=5, padx=5)
                row.pack_propagate(False)

                details = ctk.CTkFrame(row, fg_color="transparent")
                details.pack(side="left", padx=15, expand=True, fill="both")

                note_text = f" | Note: {item['notes']}" if item.get("notes") else ""
                
                is_incoming = item["type"] == "TRANSFER_IN" or (item.get("account") == "internal_transfer" and f"➔ {vault_name}" in item["purpose"])
                
                if item.get("account") == "internal_transfer":
                    lbl_txt = f"Internal Move: {item['purpose']}"
                else:
                    lbl_txt = f"Expense: {item['purpose']}"

                lbl_title = ctk.CTkLabel(details, text=lbl_txt, font=("Arial", 14, "bold"), text_color="white", anchor="w")
                lbl_title.pack(fill="x", anchor="w", pady=(12, 0))

                lbl_meta = ctk.CTkLabel(details, text=f"{item['date']}{note_text}", font=("Arial", 11), text_color="#666", anchor="w")
                lbl_meta.pack(fill="x", anchor="w", pady=(1, 0))

                color = sky_blue if is_incoming else "#FF5F5F"
                prefix = "+" if is_incoming else "-"

                lbl_amount = ctk.CTkLabel(row, text=f"{prefix}RM {item['amount']:,.2f}", font=("Arial", 14, "bold"), text_color=color, anchor="e")
                lbl_amount.pack(side="right", padx=15, pady=18)

        btn_close = ctk.CTkButton(self, text="Close Workspace Logs", fg_color="#141414", hover_color="#1F1F1F", border_width=1, border_color="#222", text_color="white", font=("Arial", 12, "bold"), height=36, corner_radius=6, command=self.destroy)
        btn_close.pack(fill="x", padx=30, pady=20)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (580 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"580x600+{x}+{y}")
        
        self.grab_set()
        self.wait_window()


# --- Streamlined Transaction Modal ---
class CenteredInput(ctk.CTkToplevel):
    def __init__(self, action_mode, sky_blue, current_categories):
        super().__init__()
        self.title(f"Unify | {action_mode}")
        self.configure(fg_color="#0D0D0D")
        self.result = None
        self.action_mode = action_mode  
        self.categories = current_categories
        
        window_width = 380
        window_height = 540 if action_mode == "DEPOSIT" else 660
        
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
            self.cat_menu = ctk.CTkOptionMenu(
                self.field_frame, 
                values=self.categories, 
                fg_color="#141414", 
                button_color="#1A1A1A", 
                text_color="white", 
                dropdown_fg_color="#141414",
                dropdown_hover_color="#1A1A1A",
                height=32
            )
            
            if self.action_mode == "ADJUST":
                self.acc_var.set("Current")

        ctk.CTkLabel(self.field_frame, text="Transaction Name", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(4, 2))
        
        if self.action_mode == "DEPOSIT":
            self.ent_purpose = ctk.CTkOptionMenu(
                self.field_frame, 
                values=["Salary", "Profit", "Interest"], 
                fg_color="#141414", 
                button_color="#1A1A1A", 
                text_color="white", 
                dropdown_fg_color="#141414",
                dropdown_hover_color="#1A1A1A",
                height=32
            )
            self.ent_purpose.set("Salary")
            self.ent_purpose.pack(fill="x", pady=(0, 8))
        elif self.action_mode == "SPENDING":
            self.ent_purpose = ctk.CTkOptionMenu(
                self.field_frame, 
                values=["Foods", "Entertainment", "Bills", "Groceries", "Loans", "Misc"], 
                fg_color="#141414", 
                button_color="#1A1A1A", 
                text_color="white", 
                dropdown_fg_color="#141414",
                dropdown_hover_color="#1A1A1A",
                height=32
            )
            self.ent_purpose.set("Foods")
            self.ent_purpose.pack(fill="x", pady=(0, 8))
        else:
            self.ent_purpose = ctk.CTkEntry(self.field_frame, placeholder_text="e.g. Audit correction, statement sync", fg_color="#141414", border_color="#222", height=32, corner_radius=6)
            self.ent_purpose.pack(fill="x", pady=(0, 8))

        amt_label = "New Target Balance (RM)" if action_mode == "ADJUST" else "Amount (RM)"
        
        ctk.CTkLabel(self.field_frame, text=amt_label, text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(4, 2))
        self.ent_amount = ctk.CTkEntry(self.field_frame, placeholder_text="0.00", fg_color="#141414", border_color="#222", height=32, corner_radius=6)
        self.ent_amount.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self.field_frame, text="Date Reference", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(4, 2))
        self.ent_date = ctk.CTkEntry(self.field_frame, placeholder_text="DD/MM/YYYY", fg_color="#141414", border_color="#222", height=32, corner_radius=6)
        self.ent_date.pack(fill="x", pady=(0, 8))
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))

        ctk.CTkLabel(self.field_frame, text="Transaction Notes", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w", pady=(4, 2))
        self.ent_notes = ctk.CTkEntry(self.field_frame, placeholder_text="Add custom notes, context or hashtags here...", fg_color="#141414", border_color="#222", height=32, corner_radius=6)
        self.ent_notes.pack(fill="x", pady=(0, 8))

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="bottom", fill="x", padx=30, pady=(10, 25))

        self.btn_cancel = ctk.CTkButton(self.action_frame, text="Cancel", fg_color="transparent", text_color="#A9A9A9", border_width=1, border_color="#222", font=("Arial", 12), height=34, corner_radius=6, command=self.destroy)
        self.btn_cancel.pack(side="left", expand=True, padx=(0, 6), fill="x")

        self.btn_confirm = ctk.CTkButton(self.action_frame, text="Confirm", fg_color=sky_blue, text_color="black", font=("Arial", 12, "bold"), height=34, corner_radius=6, command=self.on_submit)
        self.btn_confirm.pack(side="left", expand=True, padx=(6, 0), fill="x")
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (380 // 2)
        y = (self.winfo_screenheight() // 2) - (window_height // 2)
        self.geometry(f"380x{window_height}+{x}+{y}")
        
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
            category_selection = self.cat_menu.get() if (self.action_mode in ["SPENDING", "ADJUST"] and self.acc_var.get() == "Savings") else "Current"
            
            self.result = {
                "account": account_selection,
                "category": category_selection,
                "purpose": self.ent_purpose.get() if hasattr(self.ent_purpose, 'get') else self.ent_purpose.get(),
                "amount": float(self.ent_amount.get()),
                "date": self.ent_date.get(),
                "notes": self.ent_notes.get()
            }
            self.destroy()
        except Exception as e: 
            print(f"Error on Submit: {e}")


# --- Universal Multi-Directional Transfer Modal ---
class TransferModal(ctk.CTkToplevel):
    def __init__(self, sky_blue, current_balance, savings_data, current_categories):
        super().__init__()
        self.title("Unify | Internal Transfer")
        self.configure(fg_color="#0D0D0D")
        self.result = None
        self.current_balance = current_balance
        self.savings_data = savings_data
        self.account_options = ["Current"] + current_categories
        
        ctk.CTkLabel(self, text="Internal Transfer", font=("Arial", 24, "bold"), text_color=sky_blue).pack(anchor="w", padx=35, pady=(25, 4))
        ctk.CTkLabel(self, text="Transfer seamlessly across your workspaces and vaults.", font=("Arial", 12), text_color="#555").pack(anchor="w", padx=35, pady=(0, 15))

        self.field_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.field_frame.pack(fill="both", expand=True, padx=35, pady=5)

        ctk.CTkLabel(self.field_frame, text="From Account Source", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.from_menu = ctk.CTkOptionMenu(
            self.field_frame, 
            values=self.account_options, 
            fg_color="#141414", 
            button_color="#1A1A1A", 
            text_color="white", 
            dropdown_fg_color="#141414",
            dropdown_hover_color="#1A1A1A",
            height=34, 
            command=self.sync_balance_hint
        )
        self.from_menu.pack(fill="x", pady=(2, 14))

        ctk.CTkLabel(self.field_frame, text="To Destination Target", text_color="#666666", font=("Arial", 11, "bold")).pack(anchor="w")
        self.to_menu = ctk.CTkOptionMenu(
            self.field_frame, 
            values=self.account_options, 
            fg_color="#141414", 
            button_color="#1A1A1A", 
            text_color="white", 
            dropdown_fg_color="#141414",
            dropdown_hover_color="#1A1A1A",
            height=34, 
            command=self.sync_balance_hint
        )
        if len(current_categories) > 0:
            self.to_menu.set(current_categories[0]) 
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
        
        ctk.set_appearance_mode("dark")
        
        self.data = load_data()
        self.title("UNIFY | Financial Cloud Workspace")
        
        window_width = 1250
        window_height = 760
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
        ctk.CTkButton(self.action_box, text="🛠️  Adjust Balance", fg_color="#141414", hover_color="#1F1F1F", border_width=1, border_color="#222", text_color="#A9A9A9", font=("Arial", 12, "bold"), height=35, corner_radius=6, command=lambda: self.open_input("ADJUST")).pack(fill="x", pady=4)

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
        center_x = (self.winfo_screenwidth() // 2) - (1250 // 2)
        center_y = (self.winfo_screenheight() // 2) - (760 // 2)
        self.geometry(f"1250x760+{center_x}+{center_y}")

    def trigger_ui_refresh(self):
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

    def open_category_modal(self, mode, target_vault=None):
        """Creates or renames a workspace savings vault partition ledger card"""
        if mode == "CREATE":
            dialog = ThemedInputDialog("Unify | Create Vault", "Enter unique name for new structural vault:", self.sky_blue)
            new_name = dialog.result
            if new_name and new_name.strip():
                clean_name = new_name.strip()
                if clean_name in self.data["categories"]:
                    messagebox.showerror("Error", "A savings vault partition with that identifier already exists.")
                    return
                self.data["categories"].append(clean_name)
                self.data["savings"][clean_name] = 0.0
                save_data(self.data)
                self.trigger_ui_refresh()
        elif mode == "RENAME" and target_vault:
            dialog = ThemedInputDialog("Unify | Rename Vault", f"Enter new name for layout segment '{target_vault}':", self.sky_blue)
            new_name = dialog.result
            if new_name and new_name.strip():
                clean_name = new_name.strip()
                if clean_name in self.data["categories"]:
                    messagebox.showerror("Error", "A savings vault partition with that identifier already exists.")
                    return
                
                idx = self.data["categories"].index(target_vault)
                self.data["categories"][idx] = clean_name
                self.data["savings"][clean_name] = self.data["savings"].pop(target_vault, 0.0)
                
                for m_key in self.data["months"]:
                    for item in self.data["months"][m_key]:
                        if item.get("category") == target_vault:
                            item["category"] = clean_name
                
                save_data(self.data)
                self.trigger_ui_refresh()

    def remove_vault_partition(self, vault_name):
        """Deletes a vault partition completely and returns its funds safely to Checking"""
        if vault_name not in self.data["categories"]: return
        if len(self.data["categories"]) <= 1:
            messagebox.showwarning("Prohibited Action", "Your financial cloud layout must contain at least 1 active vault partition.")
            return
            
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you absolutely sure you want to remove '{vault_name}'?\nAny remaining funds inside will automatically roll back into your Current Checking account.")
        if confirm:
            refund_amt = self.data["savings"].pop(vault_name, 0.0)
            self.data["current"] += refund_amt
            self.data["categories"].remove(vault_name)
            
            m_key = datetime.now().strftime("%B %Y")
            if m_key not in self.data["months"]: self.data["months"][m_key] = []
            
            if refund_amt > 0:
                self.data["months"][m_key].insert(0, {
                    "account": "current",
                    "category": "Current",
                    "purpose": f"Rolled back liquid capital from closed vault: {vault_name}",
                    "amount": refund_amt,
                    "date": datetime.now().strftime("%d/%m/%Y"),
                    "notes": "Automated ledger closing balance settlement rule logic triggered.",
                    "type": "INCOME"
                })
                
            save_data(self.data)
            self.trigger_ui_refresh()

    def handle_vault_dropdown_action(self, option_value, vault_name):
        if option_value == "📜 Vault History":
            VaultLogsModal(vault_name, self.sky_blue, self.data)
        elif option_value == "✏️ Rename Vault":
            self.open_category_modal("RENAME", vault_name)
        elif option_value == "🗑️ Remove Vault":
            self.remove_vault_partition(vault_name)

    def render_dashboard_content(self):
        for widget in self.view_dashboard.winfo_children(): widget.destroy()
        
        top_row = ctk.CTkFrame(self.view_dashboard, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(top_row, text="Active Cloud Savings Vaults", font=("Arial", 18, "bold"), text_color="white").pack(side="left", anchor="w")
        
        btn_add_vault = ctk.CTkButton(top_row, text="+ Add Vault", fg_color="#141414", hover_color="#1F1F1F", border_width=1, border_color="#222", text_color=self.sky_blue, font=("Arial", 11, "bold"), width=100, height=30, corner_radius=6, command=lambda: self.open_category_modal("CREATE"))
        btn_add_vault.pack(side="right", anchor="e")
        
        scroll_container = ctk.CTkScrollableFrame(self.view_dashboard, fg_color="transparent", scrollbar_button_color="#222")
        scroll_container.pack(fill="both", expand=True)
        
        grid_frame = ctk.CTkFrame(scroll_container, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)
        
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")

        total_savings = sum(self.data["savings"].values())
        categories = self.data.get("categories", ["General", "Rainy Days", "Travel", "Gaming"])

        for idx, cat in enumerate(categories):
            r, c = idx // 2, idx % 2
            val = self.data["savings"].get(cat, 0.0)
            pct = (val / total_savings) if total_savings > 0 else 0.0
            
            box = ctk.CTkFrame(grid_frame, fg_color=self.card_bg, corner_radius=14, border_width=1, border_color="#1A1A1A", height=160)
            box.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            box.pack_propagate(False)

            card_header = ctk.CTkFrame(box, fg_color="transparent", height=30)
            card_header.pack(fill="x", padx=20, pady=(15, 0))

            ctk.CTkLabel(card_header, text=cat.upper(), font=("Arial", 11, "bold"), text_color="#666").pack(side="left", anchor="w")
            
            btn_options = ctk.CTkOptionMenu(
                card_header,
                values=["📜 Vault History", "✏️ Rename Vault", "🗑️ Remove Vault"],
                fg_color="#141414",
                button_color="#141414",
                button_hover_color="#1F1F1F",
                text_color="#888",
                dropdown_fg_color="#141414",
                dropdown_hover_color="#1F1F1F",
                dropdown_text_color="white",
                font=("Arial", 11, "bold"),
                width=28,
                height=24,
                corner_radius=6,
                command=lambda opt, c_name=cat: self.handle_vault_dropdown_action(opt, c_name)
            )
            btn_options.set("")
            btn_options.pack(side="right", anchor="e")

            ctk.CTkLabel(box, text=f"RM {val:,.2f}", font=("Arial", 22, "bold"), text_color="white").pack(anchor="w", padx=20, pady=(2, 0))
            
            prog_bar = ctk.CTkProgressBar(box, height=5, progress_color=self.sky_blue, fg_color="#222", corner_radius=10)
            prog_bar.set(pct)
            prog_bar.pack(fill="x", padx=20, side="bottom", pady=20)
            
            ctk.CTkLabel(box, text=f"{pct*100:.1f}% of core total", font=("Arial", 10), text_color="#444").pack(anchor="w", padx=20, side="bottom")

    def render_ledger_content(self):
        for widget in self.view_ledger.winfo_children(): widget.destroy()
        
        header = ctk.CTkFrame(self.view_ledger, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        lbl_title = ctk.CTkLabel(header, text="Transaction History Ledger", font=("Arial", 18, "bold"), text_color="white")
        lbl_title.pack(side="left", anchor="w")
        
        filter_box = ctk.CTkFrame(header, fg_color="transparent")
        filter_box.pack(side="right", anchor="e")
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.populate_ledger_feed)
        
        self.ent_search = ctk.CTkEntry(filter_box, placeholder_text="🔍 Search transactions...", width=200, height=32, fg_color="#141414", border_color="#222")
        self.ent_search.pack(side="left", padx=(0, 10))

        self.month_sel = ctk.CTkOptionMenu(filter_box, values=self.get_month_list(), width=140, height=32, fg_color="#141414", button_color="#1A1A1A", dropdown_fg_color="#141414", dropdown_hover_color="#1A1A1A", command=self.populate_ledger_feed)
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
                
                row = ctk.CTkFrame(self.ledger_scroll, fg_color="#111111", corner_radius=10, height=75) 
                row.pack(fill="x", pady=6, padx=5)
                row.pack_propagate(False)

                details = ctk.CTkFrame(row, fg_color="#111111", corner_radius=10)
                details.pack(side="left", padx=20, expand=True, fill="both")
                
                acc_label = item.get("account", "current").upper()
                if acc_label == "SAVINGS":
                    tag_str = f"Savings ↗ {item.get('category', 'General')}"
                elif acc_label == "INTERNAL_TRANSFER":
                    tag_str = f"Internal Move  •  {item.get('category', 'General')}"
                else:
                    tag_str = "Current Checking"

                note_text = f" | Notes: {item['notes']}" if item.get("notes") else ""

                lbl_purpose = ctk.CTkLabel(details, text=item["purpose"], font=("Arial", 15, "bold"), text_color="white", anchor="w")
                lbl_purpose.pack(fill="x", anchor="w", pady=(14, 0))
                
                lbl_meta = ctk.CTkLabel(details, text=f"{tag_str}  •  {item['date']}{note_text}", font=("Arial", 12), text_color="#A9A9A9", anchor="w")
                lbl_meta.pack(fill="x", anchor="w", pady=(2, 0))

                color = self.sky_blue if item["type"] in ["INCOME", "TRANSFER_IN"] else "#FF5F5F"
                prefix = "+" if item["type"] in ["INCOME", "TRANSFER_IN"] else "-"
                
                lbl_amount = ctk.CTkLabel(row, text=f"{prefix}RM {item['amount']:,.2f}", font=("Arial", 16, "bold"), text_color=color, anchor="e")
                lbl_amount.pack(side="right", padx=20, pady=20)
                
            if visible_rows == 0:
                ctk.CTkLabel(self.ledger_scroll, text="No transactions found matching your search.", font=("Arial", 12), text_color="#555").pack(pady=40)
        else:
            ctk.CTkLabel(self.ledger_scroll, text="No transactions recorded for this month.", font=("Arial", 12), text_color="#444").pack(pady=40)

    def open_transfer(self):
        modal = TransferModal(self.sky_blue, self.data["current"], self.data["savings"], self.data["categories"])
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
        form = CenteredInput(action_mode, self.sky_blue, self.data["categories"])
        res = form.result
        if res:
            target_amt = res["amount"]
            acc = res["account"]
            cat = res["category"]
            purpose_text = res["purpose"]
            
            if action_mode == "SPENDING":
                if acc == "current":
                    if self.data["current"] < target_amt:
                        messagebox.showwarning("Insufficient Funds", "Spending Blocked! Your Current Checking balance is too low.")
                        return
                else:
                    current_vault_bal = self.data["savings"].get(cat, 0.0)
                    if current_vault_bal < target_amt:
                        messagebox.showwarning("Insufficient Funds", f"Spending Blocked! Your {cat} Vault balance is too low.")
                        return

            if action_mode == "DEPOSIT":
                self.data["current"] += target_amt
                type_tag = "INCOME"
            elif action_mode == "SPENDING":
                if acc == "current": self.data["current"] -= target_amt
                else: self.data["savings"][cat] -= target_amt
                type_tag = "EXPENSES"
            elif action_mode == "ADJUST":
                if target_amt < 0:
                    messagebox.showwarning("Negative Constraint", "Adjustment Blocked! Balances cannot fall under RM 0.00.")
                    return
                
                old_bal = self.data["current"] if acc == "current" else self.data["savings"].get(cat, 0.0)
                variance = target_amt - old_bal
                
                if variance == 0: 
                    return 
                
                if acc == "current": self.data["current"] = target_amt
                else: self.data["savings"][cat] = target_amt
                
                type_tag = "INCOME" if variance > 0 else "EXPENSES"
                target_amt = abs(variance)
                
                if not purpose_text.strip():
                    purpose_text = f"⚙️ Balance Audit Adjustment ({'+' if variance > 0 else '-'}RM {target_amt:,.2f})"
            
            try: m_key = datetime.strptime(res["date"], "%d/%m/%Y").strftime("%B %Y")
            except: m_key = datetime.now().strftime("%B %Y")

            if m_key not in self.data["months"]: self.data["months"][m_key] = []
            
            self.data["months"][m_key].insert(0, {
                "account": acc if acc == "current" else "savings",
                "category": "Current" if acc == "current" else cat,
                "purpose": purpose_text,
                "amount": target_amt,
                "date": res["date"],
                "notes": res["notes"],
                "type": type_tag
            })
            
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


if __name__ == "__main__":
    app_instance = UnifyModern()
    app_instance.mainloop()
