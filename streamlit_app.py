"""
Christmas Wishlist App - Streamlit Version
A beautiful, festive, multi-user Christmas wishlist app.
"""

import streamlit as st
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any

# --- Configuration ---
USER_CREDENTIALS = {
    "Dieter": "dieter123", "Gudrun": "gudrun123", "Lukas": "lukas123",
    "Pia": "pia123", "Emmy": "emmy123", "Tim": "tim123"
}
ALL_USERS = list(USER_CREDENTIALS.keys())
DATA_FILE = Path("wunschliste.json")

# --- Data Persistence ---
def load_data() -> List[Dict[str, Any]]:
    """Loads the wish list data from the JSON file."""
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data: List[Dict[str, Any]]):
    """Saves the wish list data to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Main App Logic ---
def login_page():
    """Displays the login page and handles authentication."""
    st.set_page_config(page_title="Wunschliste Login", layout="centered")
    st.title("🎄 Weihnachts-Wunschliste Login 🎄")
    
    with st.form("login_form"):
        username = st.selectbox("Wer bist du?", ALL_USERS)
        password = st.text_input("Passwort", type="password")
        submitted = st.form_submit_button("Anmelden")

        if submitted:
            if USER_CREDENTIALS.get(username) == password:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Falsches Passwort!")

def main_app():
    """The main application interface after successful login."""
    st.set_page_config(page_title="Weihnachts-Wunschliste", layout="wide")
    st.title(f"🎄 Willkommen, {st.session_state['username']}! 🎄")

    # Load data into session state if not already present
    if 'data' not in st.session_state:
        st.session_state['data'] = load_data()

    # Define columns for layout
    col1, col2 = st.columns(2)

    # --- Column 1: My Wishes & My Gifts ---
    with col1:
        # --- Add/Edit Wish Form ---
        with st.expander("📝 Neuen Wunsch hinzufügen / Bearbeiten", expanded=True):
            with st.form("wish_form", clear_on_submit=True):
                wish_name = st.text_input("Was wünschst du dir?")
                wish_desc = st.text_area("Beschreibung")
                wish_link = st.text_input("Link (optional)")
                wish_price = st.number_input("Preis (€)", min_value=0.0, format="%.2f")
                buy_option = st.radio(
                    "Wer soll es besorgen?",
                    ("Andere dürfen es kaufen", "Ich kaufe es selbst"),
                    horizontal=True
                )
                # Streamlit's file uploader is different, simplified for now
                # image_upload = st.file_uploader("Bilder hochladen", accept_multiple_files=True)
                
                other_users = [user for user in ALL_USERS if user != st.session_state['username']]
                responsible_person = st.selectbox("Experte (optional)", [""] + other_users)

                submit_button = st.form_submit_button("Wunsch hinzufügen")

                if submit_button and wish_name and wish_desc:
                    is_for_others = buy_option == "Andere dürfen es kaufen"
                    new_wish = {
                        "id": str(uuid.uuid4()), "owner_user": st.session_state['username'],
                        "wish_name": wish_name, "link": wish_link, "description": wish_desc,
                        "price": wish_price,
                        "note": "", "color": "", "buy_self": not is_for_others,
                        "others_can_buy": is_for_others, "images": [], 
                        "responsible_person": responsible_person if responsible_person else None,
                        "claimed_by": None, "claimed_at": None, "purchased": False,
                    }
                    st.session_state['data'].append(new_wish)
                    save_data(st.session_state['data'])
                    st.success(f"Wunsch '{wish_name}' hinzugefügt!")
                    st.rerun()

        # --- Display My Wishes ---
        st.header("Meine Wunschliste")
        my_wishes = [w for w in st.session_state['data'] if w["owner_user"] == st.session_state['username']]
        if not my_wishes:
            st.info("Du hast noch keine Wünsche hinzugefügt.")
        
        for wish in my_wishes:
            status = ""
            if wish["claimed_by"]:
                status = "🎁 Wird besorgt!"
            elif wish["buy_self"]:
                status = "🛍️ Kaufe ich selbst"

            with st.container(border=True):
                price_display = f"({wish['price']:.2f}€)" if wish.get('price') else ""
                st.subheader(f"{wish['wish_name']} {price_display} {status}")
                st.write(wish['description'])
                if wish['link']:
                    st.write(f"[Link zum Produkt]({wish['link']})")
                
                # Delete button
                if st.button(f"🗑️ Löschen", key=f"del_{wish['id']}"):
                    st.session_state['data'] = [w for w in st.session_state['data'] if w['id'] != wish['id']]
                    save_data(st.session_state['data'])
                    st.rerun()

        # --- Display My Claimed Items ---
        st.header("📋 Meine Besorgungen")
        my_claimed = [w for w in st.session_state['data'] if w.get("claimed_by") == st.session_state['username']]
        
        if not my_claimed:
            st.info("Du hast noch keine Geschenke für andere reserviert.")

        for item in my_claimed:
            with st.container(border=True):
                st.subheader(f"{item['wish_name']} (für {item['owner_user']})")
                if item.get("purchased"):
                    st.success("✅ Schon besorgt")
                else:
                    if st.button("✓ Als gekauft markieren", key=f"buy_{item['id']}"):
                        for w in st.session_state['data']:
                            if w['id'] == item['id']:
                                w['purchased'] = True
                                break
                        save_data(st.session_state['data'])
                        st.rerun()

    # --- Column 2: Others' Wishlists ---
    with col2:
        st.header("🎁 Wunschlisten der Anderen")
        other_wishes = [
            w for w in st.session_state['data'] 
            if w["owner_user"] != st.session_state['username'] and w["others_can_buy"]
        ]

        if not other_wishes:
            st.info("Es gibt derzeit keine Wünsche von anderen.")

        # Group by owner
        wishes_by_owner = {}
        for wish in other_wishes:
            owner = wish["owner_user"]
            if owner not in wishes_by_owner:
                wishes_by_owner[owner] = []
            wishes_by_owner[owner].append(wish)

        for owner, wishes in wishes_by_owner.items():
            st.subheader(f"Wünsche von {owner}")
            for wish in wishes:
                with st.container(border=True):
                    price_display = f"({wish['price']:.2f}€)" if wish.get('price') else ""
                    st.write(f"**{wish['wish_name']}** {price_display}")
                    st.write(wish['description'])
                    if wish['link']:
                        st.write(f"[Link]({wish['link']})")

                    if wish["claimed_by"] is None:
                        if st.button("Ich besorge das!", key=f"claim_{wish['id']}"):
                            for w in st.session_state['data']:
                                if w['id'] == wish['id']:
                                    w['claimed_by'] = st.session_state['username']
                                    w['claimed_at'] = datetime.datetime.now().isoformat()
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()
                    elif wish["claimed_by"] == st.session_state['username']:
                        st.success("Du besorgst das.")
                    else:
                        st.warning(f"Wird bereits von {wish['claimed_by']} besorgt.")

        # --- Display My Expert Assignments ---
        st.header("👨‍🏫 Meine Expertenaufträge")
        my_expert_tasks = [w for w in st.session_state['data'] if w.get("responsible_person") == st.session_state['username']]

        if not my_expert_tasks:
            st.info("Dir wurden keine Expertenaufträge zugewiesen.")
        
        for task in my_expert_tasks:
            with st.container(border=True):
                st.subheader(f"{task['wish_name']} (für {task['owner_user']})")
                st.write(f"**Wunsch:** {task['description']}")
                st.write(f"Du wurdest als Experte für diesen Wunsch benannt. Bitte hilf bei der Auswahl oder besorge das Geschenk.")
                # You could add claim/purchased buttons here as well if the expert should also be the buyer

# --- App Entry Point ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    main_app()
else:
    login_page()
