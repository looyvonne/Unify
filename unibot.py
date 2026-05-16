import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands  
from google.cloud import firestore

# Load the variables from the .env file
load_dotenv()

# --- CLOUD CONTEXT CONFIGURATION ---
CREDENTIALS_PATH = "firebase_credentials.json"
SAVINGS_CATEGORIES = ["General", "Rainy Days", "Travel", "Gaming"]
BOT_TOKEN = os.getenv("BOT_TOKEN")

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
            
    return {"current": 0.0, "savings": {cat: 0.0 for cat in SAVINGS_CATEGORIES}, "months": {}}

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
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Successfully synchronized {len(synced)} application slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync command tree: {e}")

@bot.tree.command(name="ping", description="Test if the Unify engine is awake and listening")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓")

@bot.tree.command(name="balance", description="Fetch live universal financial data metrics from Firestore")
async def check_balance_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False) 

    current_data = load_data()
    current_val = current_data["current"]
    savings_dict = current_data["savings"]
    total_savings = sum(savings_dict.values())
    
    embed = discord.Embed(title="📊 Unify Cloud Balance Ledger", color=0x87CEEB, timestamp=datetime.now())
    embed.add_field(name="💳 Checking Account", value=f"RM {current_val:,.2f}", inline=False)
    embed.add_field(name="📈 Total Savings Vaults", value=f"RM {total_savings:,.2f}", inline=False)
    
    for cat, val in savings_dict.items():
        embed.add_field(name=f"  • {cat}", value=f"RM {val:,.2f}", inline=True)
        
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="deposit", description="Log incoming funds or deposits directly into your Checking Account")
@app_commands.describe(amount="The financial value to add", purpose="Source of income (e.g., Salary, Freelance)", notes="Custom context tag or hash")
async def discord_deposit_slash(interaction: discord.Interaction, amount: float, purpose: str, notes: str = "Logged via Discord Client"):
    await interaction.response.defer(ephemeral=True)

    if amount <= 0:
        await interaction.followup.send("❌ Transaction aborted. Amount must be greater than RM 0.00.")
        return

    current_data = load_data()
    current_data["current"] += amount
    m_key = datetime.now().strftime("%B %Y")
    
    if m_key not in current_data["months"]: 
        current_data["months"][m_key] = []
    
    current_data["months"][m_key].insert(0, {
        "account": "current",
        "category": "Current",
        "purpose": purpose,
        "amount": amount,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": notes,
        "type": "INCOME"
    })
    
    save_data(current_data)
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)
        
    await interaction.followup.send(f"✅ **RM {amount:,.2f}** deposited successfully for *'{purpose}'*.")

@bot.tree.command(name="spend", description="Log an expense out of checking or a specific cloud savings vault")
@app_commands.describe(source="Where is the money leaving from?", amount="Total spent", purpose="What did you buy?", notes="Extra references")
@app_commands.choices(source=[
    app_commands.Choice(name="Current Checking", value="current"),
    app_commands.Choice(name="General Vault", value="General"),
    app_commands.Choice(name="Rainy Days Vault", value="Rainy Days"),
    app_commands.Choice(name="Travel Vault", value="Travel"),
    app_commands.Choice(name="Gaming Vault", value="Gaming")
])
async def discord_spend_slash(interaction: discord.Interaction, source: app_commands.Choice[str], amount: float, purpose: str, notes: str = "Logged via Discord Client"):
    await interaction.response.defer(ephemeral=True)

    if amount <= 0:
        await interaction.followup.send("❌ Transaction aborted. Amount must be greater than RM 0.00.")
        return

    current_data = load_data()
    m_key = datetime.now().strftime("%B %Y")
    
    if source.value == "current":
        if current_data["current"] < amount:
            await interaction.followup.send(f"❌ Transaction Blocked! Insufficient checking funds (Available: RM {current_data['current']:,.2f}).")
            return
        current_data["current"] -= amount
        acc_tag = "current"
        cat_tag = "Current"
    else:
        vault_name = source.value
        vault_bal = current_data["savings"].get(vault_name, 0.0)
        if vault_bal < amount:
            await interaction.followup.send(f"❌ Transaction Blocked! Insufficient funds in {vault_name} Vault (Available: RM {vault_bal:,.2f}).")
            return
        current_data["savings"][vault_name] -= amount
        acc_tag = "savings"
        cat_tag = vault_name

    if m_key not in current_data["months"]: 
        current_data["months"][m_key] = []
        
    current_data["months"][m_key].insert(0, {
        "account": acc_tag,
        "category": cat_tag,
        "purpose": purpose,
        "amount": amount,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": notes,
        "type": "EXPENSES"
    })
    
    save_data(current_data)
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)
        
    await interaction.followup.send(f"💸 Logged spending of **RM {amount:,.2f}** for *'{purpose}'* from **{source.name}**.")

@bot.tree.command(name="transfer", description="Seamless internal reallocation across checking and ledger vaults")
@app_commands.describe(from_account="Origin account source", to_account="Destination account target", amount="Amount to move", notes="Reason for reallocating")
@app_commands.choices(
    from_account=[
        app_commands.Choice(name="Current Checking", value="Current"),
        app_commands.Choice(name="General Vault", value="General"),
        app_commands.Choice(name="Rainy Days Vault", value="Rainy Days"),
        app_commands.Choice(name="Travel Vault", value="Travel"),
        app_commands.Choice(name="Gaming Vault", value="Gaming")
    ],
    to_account=[
        app_commands.Choice(name="Current Checking", value="Current"),
        app_commands.Choice(name="General Vault", value="General"),
        app_commands.Choice(name="Rainy Days Vault", value="Rainy Days"),
        app_commands.Choice(name="Travel Vault", value="Travel"),
        app_commands.Choice(name="Gaming Vault", value="Gaming")
    ]
)
async def discord_transfer_slash(interaction: discord.Interaction, from_account: app_commands.Choice[str], to_account: app_commands.Choice[str], amount: float, notes: str = "Internal Transfer Routine"):
    await interaction.response.defer(ephemeral=True)

    src = from_account.value
    dest = to_account.value

    if src == dest:
        await interaction.followup.send("❌ Origin account and target destination cannot be identical.")
        return
    if amount <= 0:
        await interaction.followup.send("❌ Amount must be greater than RM 0.00.")
        return

    current_data = load_data()
    
    if src == "Current":
        if current_data["current"] < amount:
            await interaction.followup.send(f"❌ Transfer Denied! Checking balance is too low (Available: RM {current_data['current']:,.2f}).")
            return
    else:
        if current_data["savings"].get(src, 0.0) < amount:
            await interaction.followup.send(f"❌ Transfer Denied! {src} Vault balance is too low (Available: RM {current_data['savings'].get(src, 0.0):,.2f}).")
            return

    if src == "Current": current_data["current"] -= amount
    else: current_data["savings"][src] -= amount
        
    if dest == "Current": current_data["current"] += amount
    else: current_data["savings"][dest] += amount

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
    if m_key not in current_data["months"]: 
        current_data["months"][m_key] = []
    
    current_data["months"][m_key].insert(0, {
        "account": "internal_transfer",
        "category": category_tag,
        "purpose": purpose_text,
        "amount": amount,
        "type": type_text,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": notes
    })

    save_data(current_data)
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)
        
    await interaction.followup.send(f"⇄ Reallocated **RM {amount:,.2f}** from **{from_account.name}** into **{to_account.name}**.")

@bot.tree.command(name="adjust", description="Force-correct an account balance to match your real-world wallet")
@app_commands.describe(
    target="The account or vault you want to manually adjust",
    new_balance="The exact new total amount this account should show (e.g. 1500.50)",
    reason="Context on why you are adjusting (e.g. 'Syncing with bank statement')"
)
@app_commands.choices(target=[
    app_commands.Choice(name="Current Checking", value="Current"),
    app_commands.Choice(name="General Vault", value="General"),
    app_commands.Choice(name="Rainy Days Vault", value="Rainy Days"),
    app_commands.Choice(name="Travel Vault", value="Travel"),
    app_commands.Choice(name="Gaming Vault", value="Gaming")
])
async def discord_adjust_slash(interaction: discord.Interaction, target: app_commands.Choice[str], new_balance: float, reason: str = "Manual balance audit correction"):
    await interaction.response.defer(ephemeral=True)

    if new_balance < 0:
        await interaction.followup.send("❌ **Adjustment blocked.** An account balance cannot be a negative value.")
        return

    current_data = load_data()
    old_balance = 0.0
    account_key = target.value

    if account_key == "Current":
        old_balance = current_data["current"]
        current_data["current"] = new_balance
    else:
        old_balance = current_data["savings"].get(account_key, 0.0)
        current_data["savings"][account_key] = new_balance

    variance = new_balance - old_balance
    if variance == 0:
        await interaction.followup.send(f"ℹ️ The **{target.name}** balance is already exactly RM {new_balance:,.2f}. No adjustment needed.")
        return

    type_tag = "INCOME" if variance > 0 else "EXPENSES"
    abs_variance = abs(variance)
    purpose_text = f"⚙️ Balance Audit Adjustment ({'+' if variance > 0 else '-'}RM {abs_variance:,.2f})"

    m_key = datetime.now().strftime("%B %Y")
    if m_key not in current_data["months"]:
        current_data["months"][m_key] = []

    current_data["months"][m_key].insert(0, {
        "account": "current" if account_key == "Current" else "savings",
        "category": "Current" if account_key == "Current" else account_key,
        "purpose": purpose_text,
        "amount": abs_variance,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "notes": f"{reason} | Set balance from RM {old_balance:,.2f} to RM {new_balance:,.2f}",
        "type": type_tag
    })

    save_data(current_data)
    if app_instance:
        app_instance.after(0, app_instance.trigger_ui_refresh)

    await interaction.followup.send(
        f"🛠️ **Balance Adjusted!** Hard-set **{target.name}** to **RM {new_balance:,.2f}**.\n"
        f"📉 *Variance tracked:* `{'+' if variance > 0 else '-'}RM {abs_variance:,.2f}`"
    )

@bot.tree.command(name="search", description="Search transactions by partial keyword, specific month/year, or both!")
@app_commands.describe(
    keyword="Any partial or specific keyword (e.g., 'steam', 'salary', 'groceries')",
    month_year="Filter by specific time frame (e.g., 'May', '2026', or 'May 2026')"
)
async def discord_search_slash(interaction: discord.Interaction, keyword: str = None, month_year: str = None):
    await interaction.response.defer(ephemeral=True)

    if not keyword and not month_year:
        await interaction.followup.send("❌ **Search aborted.** Please provide a `keyword`, a `month_year`, or both to filter your ledger.")
        return

    current_data = load_data()
    results = []
    
    search_keyword = keyword.lower().strip() if keyword else None
    search_time = month_year.lower().strip() if month_year else None
    months_data = current_data.get("months", {})
    
    for month_key, transactions in months_data.items():
        time_matches = True
        if search_time and search_time not in month_key.lower():
            time_matches = False
            
        if not time_matches:
            continue
            
        for tx in transactions:
            purpose = str(tx.get("purpose", "")).lower()
            notes = str(tx.get("notes", "")).lower()
            category = str(tx.get("category", "")).lower()
            
            keyword_matches = True
            if search_keyword:
                if (search_keyword not in purpose and 
                    search_keyword not in notes and 
                    search_keyword not in category):
                    keyword_matches = False
            
            if keyword_matches:
                tx_copy = tx.copy()
                tx_copy["month_context"] = month_key
                results.append(tx_copy)

    if not results:
        err_msg = "🔍 No transactions found matching "
        if keyword: err_msg += f"keyword **'{keyword}'** "
        if month_year: err_msg += f"inside **'{month_year}'**"
        await interaction.followup.send(err_msg)
        return

    results = results[:5]
    
    embed = discord.Embed(
        title="🔍 Cloud History Search Results", 
        description=f"Showing closest matches found in your financial database.\n{ '─' * 32 }",
        color=0xFFA500
    )
    
    for i, tx in enumerate(results):
        tx_type = tx.get("type", "EXPENSE")
        month_context = tx.get("month_context", "Unknown Month")
        
        emoji = "🪙" if "INCOME" in tx_type else "💸"
        if "TRANSFER" in tx_type:
            emoji = "⇄"
            
        amount = tx.get("amount", 0.0)
        date = tx.get("date", "Unknown Date")
        purpose = tx.get("purpose", "No Description")
        
        category = tx.get("category", "General")
        if category.lower() == "current":
            category = "Current"
            
        notes = tx.get("notes", "")

        field_title = f"{emoji} Entry #{i+1}: RM {amount:,.2f}"
        
        field_value = (
            f"**🔹 Item:** {purpose}\n"
            f"**📅 Date:** {date} *({month_context})*\n"
            f"**📁 Wallet:** {category}"
        )
        if notes:
            field_value += f"\n**📝 Notes:** *{notes}*"
            
        if i < len(results) - 1:
            field_value += f"\n{ '─' * 24 }"

        embed.add_field(name=field_title, value=field_value, inline=False)
        
    embed.set_footer(text="Unify Financial Ledger System")
    await interaction.followup.send(embed=embed)


def run_discord_bot():
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ Runtime configuration payload exception: BOT_TOKEN environmental key missing.")

if __name__ == "__main__":
    run_discord_bot()