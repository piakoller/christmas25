"""
Christmas Wishlist App - Streamlit Version
A beautiful, festive, multi-user Christmas wishlist app.
"""

import streamlit as st
import json
import uuid
import datetime
import base64
from pathlib import Path
from typing import List, Dict, Any
from io import BytesIO

# --- Configuration ---
USER_CREDENTIALS = {
    "Dieter": "dieter123", "Gudrun": "gudrun123", "Lukas": "lukas123",
    "Pia": "pia123", "Emmy": "emmy123", "Tim": "tim123"
}
ALL_USERS = list(USER_CREDENTIALS.keys())
SUPER_USERS = ["Dieter", "Gudrun"]
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
    if 'edit_wish_id' not in st.session_state:
        st.session_state['edit_wish_id'] = None

    # Define columns for layout
    col1, col2 = st.columns(2)

    # --- Column 1: My Wishes & My Gifts ---
    with col1:
        # --- Add/Edit Wish Form ---
        with st.expander("📝 Wunsch hinzufügen / Bearbeiten", expanded=True):
            
            edit_mode = st.session_state.edit_wish_id is not None
            wish_to_edit = next((w for w in st.session_state.data if w['id'] == st.session_state.edit_wish_id), None) if edit_mode else None

            with st.form("wish_form"):
                st.subheader("Neuen Wunsch hinzufügen" if not edit_mode else "Wunsch bearbeiten")
                
                wish_name = st.text_input("Was wünschst du dir?", value=wish_to_edit.get("wish_name", "") if wish_to_edit else "")
                wish_desc = st.text_area("Beschreibung", value=wish_to_edit.get("description", "") if wish_to_edit else "")
                wish_link = st.text_input("Link (optional)", value=wish_to_edit.get("link", "") if wish_to_edit else "")
                wish_price = st.number_input("Preis (€)", min_value=0.0, value=wish_to_edit.get("price", 0.0) if wish_to_edit else 0.0, format="%.2f")
                
                # Image upload
                uploaded_images = st.file_uploader(
                    "Bilder hochladen (optional)", 
                    accept_multiple_files=True,
                    type=['png', 'jpg', 'jpeg'],
                    help="Du kannst mehrere Bilder hochladen"
                )
                
                buy_options = ("Andere dürfen es kaufen", "Ich kaufe es selbst")
                buy_option_index = 1 if (wish_to_edit and wish_to_edit.get("buy_self")) else 0
                buy_option = st.radio("Wer soll es besorgen?", buy_options, index=buy_option_index, horizontal=True)
                
                other_users = [user for user in ALL_USERS if user != st.session_state['username']]
                expert_options = [""] + other_users
                responsible = wish_to_edit.get("responsible_person") if wish_to_edit else None
                expert_index = expert_options.index(responsible) if responsible and responsible in expert_options else 0
                responsible_person = st.selectbox("Experte (optional)", expert_options, index=expert_index)

                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submit_button = st.form_submit_button("💾 Änderungen speichern" if edit_mode else "➕ Wunsch hinzufügen")
                with col_cancel:
                    if edit_mode:
                        if st.form_submit_button("❌ Abbrechen"):
                            st.session_state.edit_wish_id = None
                            st.rerun()

                if submit_button and wish_name and wish_desc:
                    # Convert uploaded images to base64
                    image_data = []
                    if uploaded_images:
                        for uploaded_file in uploaded_images:
                            bytes_data = uploaded_file.read()
                            base64_image = base64.b64encode(bytes_data).decode()
                            image_data.append({
                                "data": base64_image,
                                "type": uploaded_file.type
                            })
                    
                    if edit_mode:
                        # Update existing wish
                        for wish in st.session_state.data:
                            if wish['id'] == st.session_state.edit_wish_id:
                                wish.update({
                                    "wish_name": wish_name, "description": wish_desc, "link": wish_link,
                                    "price": wish_price, "buy_self": buy_option == "Ich kaufe es selbst",
                                    "others_can_buy": buy_option == "Andere dürfen es kaufen",
                                    "responsible_person": responsible_person if responsible_person else None,
                                })
                                # Update images only if new ones were uploaded
                                if image_data:
                                    wish["images"] = image_data
                                break
                        save_data(st.session_state.data)
                        st.success("Wunsch aktualisiert!")
                        st.session_state.edit_wish_id = None
                    else:
                        # Add new wish
                        new_wish = {
                            "id": str(uuid.uuid4()), "owner_user": st.session_state['username'],
                            "wish_name": wish_name, "link": wish_link, "description": wish_desc,
                            "price": wish_price, "note": "", "color": "", 
                            "buy_self": buy_option == "Ich kaufe es selbst",
                            "others_can_buy": buy_option == "Andere dürfen es kaufen",
                            "images": image_data, "responsible_person": responsible_person if responsible_person else None,
                            "claimed_by": None, "claimed_at": None, "purchased": False,
                        }
                        st.session_state.data.append(new_wish)
                        save_data(st.session_state.data)
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
                
                # Display images
                if wish.get('images'):
                    cols = st.columns(min(len(wish['images']), 3))
                    for idx, img in enumerate(wish['images']):
                        with cols[idx % 3]:
                            image_bytes = base64.b64decode(img['data'])
                            st.image(image_bytes, use_container_width=True)
                
                # Edit and Delete buttons
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button(f"✏️ Bearbeiten", key=f"edit_{wish['id']}"):
                        st.session_state.edit_wish_id = wish['id']
                        st.rerun()
                with col_delete:
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
                    actual_price = item.get("actual_price", 0)
                    st.success(f"✅ Schon besorgt ({actual_price:.2f}€)")
                else:
                    estimated_price = item.get("price", 0.0)
                    with st.form(key=f"purchase_form_{item['id']}"):
                        st.write(f"Geschätzter Preis: {estimated_price:.2f}€")
                        actual_price = st.number_input(
                            "Tatsächlicher Preis (€)", 
                            min_value=0.0, 
                            value=estimated_price,
                            format="%.2f",
                            key=f"price_input_{item['id']}"
                        )
                        if st.form_submit_button("✓ Als gekauft markieren"):
                            for w in st.session_state['data']:
                                if w['id'] == item['id']:
                                    w['purchased'] = True
                                    w['actual_price'] = actual_price
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
                    
                    # Display images
                    if wish.get('images'):
                        cols = st.columns(min(len(wish['images']), 3))
                        for idx, img in enumerate(wish['images']):
                            with cols[idx % 3]:
                                image_bytes = base64.b64decode(img['data'])
                                st.image(image_bytes, use_container_width=True)

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
                st.write(f"**Beschreibung:** {task['description']}")
                if task['link']:
                    st.write(f"[Link zum Produkt]({task['link']})")
                
                # Display images
                if task.get('images'):
                    cols = st.columns(min(len(task['images']), 3))
                    for idx, img in enumerate(task['images']):
                        with cols[idx % 3]:
                            image_bytes = base64.b64decode(img['data'])
                            st.image(image_bytes, use_container_width=True)
                
                # Check if already purchased by expert
                if task.get("claimed_by") == st.session_state['username'] and task.get("purchased"):
                    actual_price = task.get("actual_price", 0)
                    st.success(f"✅ Du hast dieses Geschenk besorgt ({actual_price:.2f}€)")
                # Check if expert has claimed it but not purchased yet
                elif task.get("claimed_by") == st.session_state['username']:
                    estimated_price = task.get("price", 0.0)
                    with st.form(key=f"expert_purchase_form_{task['id']}"):
                        st.write(f"Geschätzter Preis: {estimated_price:.2f}€")
                        actual_price = st.number_input(
                            "Tatsächlicher Preis (€)", 
                            min_value=0.0, 
                            value=estimated_price,
                            format="%.2f",
                            key=f"expert_price_input_{task['id']}"
                        )
                        if st.form_submit_button("✓ Als gekauft markieren"):
                            for w in st.session_state['data']:
                                if w['id'] == task['id']:
                                    w['purchased'] = True
                                    w['actual_price'] = actual_price
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()
                # Check if someone else has claimed it
                elif task.get("claimed_by") and task.get("claimed_by") != st.session_state['username']:
                    st.info(f"Wird bereits von {task['claimed_by']} besorgt.")
                # Not claimed yet - allow expert to claim
                else:
                    if st.button("Ich besorge das!", key=f"expert_claim_{task['id']}"):
                        for w in st.session_state['data']:
                            if w['id'] == task['id']:
                                w['claimed_by'] = st.session_state['username']
                                w['claimed_at'] = datetime.datetime.now().isoformat()
                                break
                        save_data(st.session_state['data'])
                        st.rerun()

        # --- Cost Summary Table ---
        st.header("💰 Meine Ausgaben")
        purchased_items = [
            w for w in st.session_state['data'] 
            if w.get("claimed_by") == st.session_state['username'] and w.get("purchased")
        ]

        if not purchased_items:
            st.info("Du hast noch keine Geschenke als gekauft markiert.")
        else:
            import pandas as pd
            
            table_data = []
            for item in purchased_items:
                table_data.append({
                    "Geschenk": item['wish_name'],
                    "Für": item['owner_user'],
                    "Geschätzter Preis": f"{item.get('price', 0.0):.2f}€",
                    "Tatsächlicher Preis": f"{item.get('actual_price', 0.0):.2f}€"
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            total_spent = sum(item.get('actual_price', 0.0) for item in purchased_items)
            st.markdown(f"### **Gesamtausgaben: {total_spent:.2f}€**")

        # --- Super User View: See Others' Spending ---
        if st.session_state['username'] in SUPER_USERS:
            st.header("👑 Admin: Ausgaben aller Benutzer")
            
            # Super users can see everyone's spending except purchases made FOR themselves
            # They CAN see the other super user's spending
            users_to_show = [u for u in ALL_USERS if u != st.session_state['username']]
            
            for user in users_to_show:
                # Get all purchases by this user, but exclude gifts that are FOR the current super user
                user_purchased = [
                    w for w in st.session_state['data'] 
                    if w.get("claimed_by") == user 
                    and w.get("purchased") 
                    and w.get("owner_user") != st.session_state['username']
                ]
                
                if user_purchased:
                    with st.expander(f"💰 {user}s Ausgaben"):
                        import pandas as pd
                        
                        table_data = []
                        for item in user_purchased:
                            table_data.append({
                                "Geschenk": item['wish_name'],
                                "Für": item['owner_user'],
                                "Geschätzter Preis": f"{item.get('price', 0.0):.2f}€",
                                "Tatsächlicher Preis": f"{item.get('actual_price', 0.0):.2f}€"
                            })
                        
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        
                        user_total = sum(item.get('actual_price', 0.0) for item in user_purchased)
                        st.markdown(f"**{user} Gesamt: {user_total:.2f}€**")
                else:
                    st.info(f"{user} hat noch keine sichtbaren Geschenke als gekauft markiert.")

# --- App Entry Point ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    main_app()
else:
    login_page()
