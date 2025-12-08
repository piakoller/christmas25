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
from typing import List, Dict, Any, Optional
from io import BytesIO
from PIL import Image

# Firebase imports (optional, only used if configured)
try:
    import firebase_admin  # type: ignore
    from firebase_admin import credentials, db  # type: ignore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# --- Configuration ---
USER_CREDENTIALS = {
    "Dieter": "dieter123", "Gudrun": "gudrun123", "Lukas": "lukas123",
    "Pia": "pia123", "Emmy": "emmy123", "Tim": "tim123"
}
ALL_USERS = list(USER_CREDENTIALS.keys())
SUPER_USERS = ["Dieter", "Gudrun"]
DATA_FILE = Path("wunschliste.json")
BUDGET_LIMIT = 1500.0  # Budget limit per user in euros

# --- Helper Functions ---
def navigate_to(page: str):
    """Navigate to a page and update URL for browser history support."""
    st.session_state['current_page'] = page
    st.query_params['page'] = page
    st.rerun()

# --- Data Persistence (Firebase Realtime Database preferred, fallback to local JSON) ---

def _init_firebase_from_secrets() -> Optional[Any]:
    """Initialize Firebase Realtime Database using service account provided in Streamlit secrets.
    Returns a database reference or None on failure.
    The service account JSON should be stored in Streamlit secrets as `firebase` (a dict).
    """
    if not FIREBASE_AVAILABLE:
        return None
    
    try:
        if not st.secrets.get("firebase"):
            return None
        if 'firebase_db' in st.session_state:
            return st.session_state['firebase_db']
        
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        # Avoid re-initializing the app
        try:
            firebase_admin.get_app()
        except Exception:
            firebase_admin.initialize_app(cred, {
                'databaseURL': f'https://{st.secrets["firebase"]["project_id"]}-default-rtdb.firebaseio.com'
            })
        database = db.reference('/')
        st.session_state['firebase_db'] = database
        return database
    except Exception as e:
        # Show error for debugging but don't crash
        st.sidebar.warning(f"Firebase connection failed: {str(e)}")
        return None


def load_data() -> List[Dict[str, Any]]:
    """Load wishlist data. Prefer Firebase Realtime Database when configured, otherwise use local JSON file."""
    # Try Firebase Realtime Database
    db_ref = _init_firebase_from_secrets()
    if db_ref:
        try:
            wishes_ref = db_ref.child('wishes')
            data = wishes_ref.get()
            if data:
                # Firebase returns a dict, convert to list
                if isinstance(data, dict):
                    return list(data.values())
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            # fall back to local file
            st.sidebar.warning(f"Firebase read failed: {str(e)}")
            pass

    # Fallback: local JSON file
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_data(data: List[Dict[str, Any]]):
    """Save wishlist data to Firebase Realtime Database when configured, otherwise to local JSON."""
    # Try Firebase Realtime Database
    db_ref = _init_firebase_from_secrets()
    if db_ref:
        try:
            wishes_ref = db_ref.child('wishes')
            # Convert list to dict with IDs as keys for better Firebase structure
            data_dict = {}
            for item in data:
                item_id = item.get('id', str(uuid.uuid4()))
                data_dict[item_id] = item
            # Set the entire wishes node
            wishes_ref.set(data_dict)
            return
        except Exception as e:
            # fall back to local file
            st.sidebar.warning(f"Firebase write failed: {str(e)}")
            pass

    # Fallback: write to local JSON file
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def migrate_meal_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate old meal structure to new structure if needed."""
    # Initialize new structures if they don't exist
    if 'meal_proposals' not in data:
        data['meal_proposals'] = []
    if 'day_assignments' not in data:
        data['day_assignments'] = {}
    
    # Ensure all existing proposals have a category field
    for dish in data.get('meal_proposals', []):
        if 'category' not in dish:
            dish['category'] = 'Hauptspeise'  # Default category for old dishes
    
    # Check if migration is needed (old structure exists and has data)
    if 'meals' in data and data['meals']:
        # Track which dishes we've already added (by name to avoid duplicates)
        seen_dishes = {}
        
        # First, check existing proposals to avoid duplicates
        for existing_dish in data['meal_proposals']:
            dish_name = existing_dish.get('name', '')
            if dish_name:
                seen_dishes[dish_name] = existing_dish['id']
        
        # Process old meal structure
        for day_date, day_data in data['meals'].items():
            if 'proposals' in day_data and day_data['proposals']:
                for proposal in day_data['proposals']:
                    dish_name = proposal.get('dish_name', '')
                    
                    # If we haven't seen this dish yet, add it to proposals
                    if dish_name and dish_name not in seen_dishes:
                        dish_id = str(uuid.uuid4())
                        new_dish = {
                            "id": dish_id,
                            "name": dish_name,
                            "category": "Hauptspeise",  # Default category for migrated dishes
                            "description": proposal.get('description', ''),
                            "proposed_by": proposal.get('proposed_by', ''),
                            "responsible": proposal.get('responsible', None),
                            "created_at": proposal.get('created_at', datetime.datetime.now().isoformat()),
                            "votes": []
                        }
                        
                        # Migrate votes
                        if 'votes' in day_data:
                            new_dish['votes'] = list(day_data['votes'].keys())
                        
                        data['meal_proposals'].append(new_dish)
                        seen_dishes[dish_name] = dish_id
                    
                    # Assign to day if it was the chosen/top proposal
                    if dish_name in seen_dishes and len(day_data.get('proposals', [])) > 0:
                        # Use the first proposal as the assignment (most relevant)
                        if day_date not in data['day_assignments']:
                            data['day_assignments'][day_date] = seen_dishes[dish_name]
    
    # Migrate old day_assignments structure (string dish_id) to new structure (dict with categories)
    for day_date, assignment in list(data.get('day_assignments', {}).items()):
        # Check if this is old format (string) instead of new format (dict)
        if isinstance(assignment, str):
            # Find the dish to get its category
            dish_id = assignment
            dish = next((d for d in data['meal_proposals'] if d['id'] == dish_id), None)
            category = dish.get('category', 'Hauptspeise') if dish else 'Hauptspeise'
            
            # Convert to new format
            data['day_assignments'][day_date] = {
                category: [dish_id]
            }
    
    return data


def load_planning_data() -> Dict[str, Any]:
    """Load planning data (meals, attendance) from Firebase or local file."""
    data_migrated = False
    db_ref = _init_firebase_from_secrets()
    if db_ref:
        try:
            planning_ref = db_ref.child('planning')
            data = planning_ref.get()
            if data:
                # Migrate old data structure if needed
                old_data = data.copy()
                data = migrate_meal_data(data)
                # Check if migration happened
                if 'meal_proposals' in data and 'meal_proposals' not in old_data:
                    data_migrated = True
                if data_migrated:
                    # Save migrated data back to Firebase
                    planning_ref.set(data)
                return data
            return {"meals": {}, "attendance": {}}
        except Exception as e:
            st.sidebar.warning(f"Firebase planning read failed: {str(e)}")
    
    # Fallback: local JSON
    planning_file = Path("planning.json")
    if planning_file.exists():
        try:
            with open(planning_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Migrate old data structure if needed
                old_data = data.copy()
                data = migrate_meal_data(data)
                # Check if migration happened
                if 'meal_proposals' in data and 'meal_proposals' not in old_data:
                    data_migrated = True
                if data_migrated:
                    # Save migrated data back to file
                    with open(planning_file, "w", encoding="utf-8") as fw:
                        json.dump(data, fw, indent=4, ensure_ascii=False)
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {"meals": {}, "attendance": {}}


def save_planning_data(data: Dict[str, Any]):
    """Save planning data to Firebase or local file."""
    db_ref = _init_firebase_from_secrets()
    if db_ref:
        try:
            planning_ref = db_ref.child('planning')
            planning_ref.set(data)
            return
        except Exception as e:
            st.sidebar.warning(f"Firebase planning write failed: {str(e)}")
    
    # Fallback: local JSON
    with open("planning.json", "w", encoding="utf-8") as f:
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
    
    # Load data into session state if not already present
    if 'data' not in st.session_state:
        st.session_state['data'] = load_data()
    if 'edit_wish_id' not in st.session_state:
        st.session_state['edit_wish_id'] = None
    if 'planning_data' not in st.session_state:
        st.session_state['planning_data'] = load_planning_data()
    # Sync with URL first (for browser back/forward button)
    try:
        if 'page' in st.query_params:
            url_page = st.query_params['page']
            if isinstance(url_page, list):
                url_page = url_page[0] if url_page else 'dashboard'
        else:
            url_page = None
    except Exception:
        url_page = None
    
    # Initialize or sync current_page
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = url_page if url_page else 'dashboard'
    elif url_page and url_page != st.session_state['current_page']:
        # URL changed (browser back/forward) - update session state
        st.session_state['current_page'] = url_page
    
    # Route to appropriate page
    if st.session_state['current_page'] == 'dashboard':
        dashboard_page()
    elif st.session_state['current_page'] == 'countdown':
        countdown_page()
    elif st.session_state['current_page'] == 'wishlist':
        wishlist_page()
    elif st.session_state['current_page'] == 'meals':
        meal_planning_page()
    elif st.session_state['current_page'] == 'attendance':
        attendance_page()
    elif st.session_state['current_page'] == 'advent':
        advent_calendar_page()


def dashboard_page():
    """Display the main dashboard with tile navigation."""
    
    # Custom CSS for beautiful cards
    st.markdown("""
    <style>
    /* Page background with subtle pattern */
    .main .block-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #e8f5e9 100%) !important;
        padding: 2rem !important;
    }
    
    /* Card styling */
    .tile-card {
        background: white;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .tile-card h2 {
        font-size: 3em;
        margin: 10px 0;
    }
    
    .tile-card p {
        font-size: 1.2em;
        color: #666;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Styled welcome header
    st.markdown(f"""
        <h1 style='text-align: center; 
                   color: #2E7D32; 
                   font-size: 3em;
                   text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
                   margin-bottom: 30px;'>
            🎄 Willkommen, {st.session_state['username']}! 🎄
        </h1>
    """, unsafe_allow_html=True)
    
    # Calculate Christmas countdown
    today = datetime.date.today()
    christmas = datetime.date(today.year, 12, 24)
    if today > christmas:
        christmas = datetime.date(today.year + 1, 12, 24)
    days_until_christmas = (christmas - today).days
    
    # First row: Christmas Countdown (large centered card)
    col_spacer1, col_countdown, col_spacer2 = st.columns([1, 2, 1])
    with col_countdown:
        st.markdown(f"""
        <div class="tile-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; min-height: 300px;">
            <h2 style="font-size: 4em; color: white;">🎅</h2>
            <h1 style="font-size: 5em; margin: 20px 0; color: white;">{days_until_christmas}</h1>
            <p style="font-size: 1.5em; color: white;">{'Tage bis Heiligabend!' if days_until_christmas != 1 else 'Tag bis Heiligabend!'}</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🎄 Zum Countdown", key="countdown_btn", use_container_width=True):
            navigate_to('countdown')
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Second row: 4 tiles
    col1, col2, col3, col4 = st.columns(4)
    
    # Tile 1: Wunschliste
    with col1:
        st.markdown("""
        <div class="tile-card" style="background: linear-gradient(135deg, #D22B2B 0%, #FF6B9D 100%); color: white;">
            <h2 style="color: white;">🎁</h2>
            <p style="font-size: 1.3em; font-weight: bold; color: white;">Wunschliste</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📝 Zur Wunschliste", key="wishlist_btn", use_container_width=True):
            navigate_to('wishlist')
            st.rerun()
    
    # Tile 2: Essensplanung
    with col2:
        st.markdown("""
        <div class="tile-card" style="background: linear-gradient(135deg, #2E7D32 0%, #66BB6A 100%); color: white;">
            <h2 style="color: white;">🍽️</h2>
            <p style="font-size: 1.3em; font-weight: bold; color: white;">Essensplanung</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🍴 Zur Essensplanung", key="meals_btn", use_container_width=True):
            navigate_to('meals')
            st.rerun()
    
    # Tile 3: Wer kommt wann?
    with col3:
        st.markdown("""
        <div class="tile-card" style="background: linear-gradient(135deg, #1565C0 0%, #42A5F5 100%); color: white;">
            <h2 style="color: white;">📅</h2>
            <p style="font-size: 1.3em; font-weight: bold; color: white;">Wer kommt wann?</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👥 Zur Anwesenheit", key="attendance_btn", use_container_width=True):
            navigate_to('attendance')
            st.rerun()
    
    # Tile 4: Adventskalender
    with col4:
        st.markdown("""
        <div class="tile-card" style="background: linear-gradient(135deg, #F57C00 0%, #FFB74D 100%); color: white;">
            <h2 style="color: white;">🎄</h2>
            <p style="font-size: 1.3em; font-weight: bold; color: white;">Adventskalender</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🎅 Zum Kalender", key="advent_btn", use_container_width=True):
            navigate_to('advent')
            st.rerun()


def countdown_page():
    """Display detailed Christmas countdown page."""
    if st.button("⬅️ Zurück zur Übersicht"):
        navigate_to('dashboard')
        st.rerun()
    
    st.title("� Countdown bis Heiligabend 🎄")
    
    today = datetime.date.today()
    christmas = datetime.date(today.year, 12, 24)
    if today > christmas:
        christmas = datetime.date(today.year + 1, 12, 24)
    days_until_christmas = (christmas - today).days
    
    st.markdown(f"""
    <div style='text-align: center; padding: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 15px; margin: 30px 0;'>
        <h1 style='color: white; font-size: 6em; margin: 0;'>🎅 {days_until_christmas} 🎄</h1>
        <h2 style='color: white; margin: 20px 0 0 0; font-size: 2em;'>
            {'Tage bis Heiligabend!' if days_until_christmas != 1 else 'Tag bis Heiligabend!'}
        </h2>
        <p style='color: white; margin-top: 20px; font-size: 1.2em;'>
            {christmas.strftime('%A, %d. %B %Y')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Additional countdown information
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hours_until = days_until_christmas * 24
        st.metric("Stunden", f"{hours_until:,}")
    
    with col2:
        minutes_until = days_until_christmas * 24 * 60
        st.metric("Minuten", f"{minutes_until:,}")
    
    with col3:
        seconds_until = days_until_christmas * 24 * 60 * 60
        st.metric("Sekunden", f"{seconds_until:,}")
    
    st.markdown("---")
    st.markdown("### 🎄 Die schönste Zeit des Jahres steht bevor!")
    st.write("Nutze die Wunschliste, um deine Geschenkwünsche zu teilen und die Planung für die Feiertage zu koordinieren.")


def wishlist_page():
    """Display the wishlist page."""
    
    if st.button("⬅️ Zurück zur Übersicht"):
        navigate_to('dashboard')
        st.rerun()
    
    st.title("🎁 Wunschliste")

    # Define columns for layout
    col1, col2 = st.columns(2)

    # --- Column 1: My Wishes & My Gifts ---
    with col1:
        # --- Add/Edit Wish Form ---
        with st.expander("📝 Wunsch hinzufügen / Bearbeiten", expanded=True):
            
            edit_mode = st.session_state.edit_wish_id is not None
            wish_to_edit = next((w for w in st.session_state.data if w['id'] == st.session_state.edit_wish_id), None) if edit_mode else None
            is_suggestion = (wish_to_edit and wish_to_edit.get('type') == 'suggestion') if wish_to_edit else False

            with st.form("wish_form"):
                if is_suggestion:
                    st.subheader("Geschenkvorschlag bearbeiten")
                else:
                    st.subheader("Neuen Wunsch hinzufügen" if not edit_mode else "Wunsch bearbeiten")
                
                if is_suggestion and wish_to_edit:
                    # Editing a suggestion - show suggestion fields
                    wish_name = st.text_input("Geschenkidee", value=wish_to_edit.get("wish_name", ""))
                    wish_desc = st.text_area("Beschreibung / Warum ist das eine gute Idee?", value=wish_to_edit.get("description", ""))
                    wish_link = st.text_input("Link (optional)", value=wish_to_edit.get("link", ""))
                    wish_price = st.number_input("Ungefährer Preis (€)", min_value=0.0, value=wish_to_edit.get("price", 0.0), format="%.2f")
                    
                    # Show who the suggestion is for
                    st.info(f"Vorschlag für: {wish_to_edit.get('suggested_for', 'Unbekannt')}")
                    
                    # No image upload or buy options for suggestions
                    uploaded_images = None
                    buy_option = None
                    responsible_person = None
                else:
                    # Regular wish form
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

                if submit_button:
                    # Validate inputs
                    if not wish_name:
                        st.error("❌ Bitte gib einen Namen für deinen Wunsch ein!")
                        st.stop()
                    if not wish_desc:
                        st.error("❌ Bitte füge eine Beschreibung hinzu!")
                        st.stop()
                    
                    # Check budget limit when adding new wish (not when editing)
                    if not edit_mode:
                        current_wishes = [w for w in st.session_state['data'] if w.get("owner_user") == st.session_state['username']]
                        current_total = sum(w.get("actual_price", 0.0) if w.get("purchased") else w.get("price", 0.0) for w in current_wishes)
                        
                        if current_total + wish_price > BUDGET_LIMIT:
                            remaining = BUDGET_LIMIT - current_total
                            st.error(f"⚠️ Dieser Wunsch würde dein Budget von {BUDGET_LIMIT:.2f}€ überschreiten! Du hast noch {remaining:.2f}€ verfügbar.")
                            st.stop()
                    
                    # Convert uploaded images to base64 with compression
                    image_data = []
                    if uploaded_images:
                        try:
                            for uploaded_file in uploaded_images:
                                # Open and compress the image
                                img = Image.open(uploaded_file)
                                
                                # Resize if too large (max 800px width)
                                max_width = 800
                                if img.width > max_width:
                                    ratio = max_width / img.width
                                    new_height = int(img.height * ratio)
                                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                                
                                # Convert to RGB if necessary
                                if img.mode in ('RGBA', 'LA', 'P'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    if img.mode == 'P':
                                        img = img.convert('RGBA')
                                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                    img = background
                                
                                # Save to bytes with compression
                                buffer = BytesIO()
                                img.save(buffer, format='JPEG', quality=85, optimize=True)
                                buffer.seek(0)
                                
                                # Convert to base64
                                base64_image = base64.b64encode(buffer.read()).decode()
                                image_data.append({
                                    "data": base64_image,
                                    "type": "image/jpeg"
                                })
                        except Exception as e:
                            st.error(f"Fehler beim Hochladen der Bilder: {str(e)}")
                            st.stop()
                    
                    if edit_mode:
                        # Update existing wish or suggestion
                        for wish in st.session_state.data:
                            if wish['id'] == st.session_state.edit_wish_id:
                                if is_suggestion:
                                    # Update suggestion - keep suggestion-specific fields
                                    wish.update({
                                        "wish_name": wish_name, 
                                        "description": wish_desc, 
                                        "link": wish_link,
                                        "price": wish_price,
                                        # Keep original suggestion fields
                                        "type": "suggestion",
                                        "suggested_by": wish.get("suggested_by"),
                                        "suggested_for": wish.get("suggested_for")
                                    })
                                else:
                                    # Update regular wish
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
        
        # Calculate budget usage
        my_wishes = [w for w in st.session_state['data'] if w.get("owner_user") == st.session_state['username']]
        
        # Calculate total value of wishes (use actual_price if purchased, otherwise estimated price)
        total_wished = 0.0
        for wish in my_wishes:
            if wish.get("purchased"):
                total_wished += wish.get("actual_price", 0.0)
            else:
                total_wished += wish.get("price", 0.0)
        
        budget_remaining = BUDGET_LIMIT - total_wished
        budget_percentage = (total_wished / BUDGET_LIMIT) * 100 if BUDGET_LIMIT > 0 else 0
        
        # Display budget indicator
        if budget_percentage > 100:
            budget_color = "#ff4444"
            budget_emoji = "⚠️"
        elif budget_percentage > 80:
            budget_color = "#ff9800"
            budget_emoji = "⚡"
        else:
            budget_color = "#4caf50"
            budget_emoji = "✅"
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, {budget_color}22 0%, {budget_color}44 100%); 
                    border-left: 4px solid {budget_color}; 
                    padding: 15px; 
                    border-radius: 8px; 
                    margin-bottom: 20px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='margin: 0; color: #333;'>{budget_emoji} Dein Budget</h3>
                    <p style='margin: 5px 0 0 0; color: #666;'>Wünsche im Wert von {total_wished:.2f}€ / {BUDGET_LIMIT:.2f}€</p>
                </div>
                <div style='text-align: right;'>
                    <h2 style='margin: 0; color: {budget_color};'>{budget_remaining:.2f}€</h2>
                    <p style='margin: 5px 0 0 0; color: #666;'>noch verfügbar</p>
                </div>
            </div>
            <div style='background: #ddd; height: 20px; border-radius: 10px; margin-top: 10px; overflow: hidden;'>
                <div style='background: {budget_color}; height: 100%; width: {min(budget_percentage, 100):.1f}%; 
                            transition: width 0.3s ease;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if not my_wishes:
            st.info("Du hast noch keine Wünsche hinzugefügt.")
        
        for wish in my_wishes:
            status = ""
            if wish.get("purchased") and wish.get("buy_self"):
                status = f"✅ Schon besorgt ({wish.get('actual_price', 0):.2f}€)"
            elif wish.get("claimed_by"):
                status = "🎁 Wird besorgt!"
            elif wish.get("buy_self"):
                status = "🛍️ Kaufe ich selbst"

            with st.container(border=True):
                price_display = f"({wish['price']:.2f}€)" if wish.get('price') else ""
                st.subheader(f"{wish['wish_name']} {price_display} {status}")
                st.write(wish['description'])
                if wish['link']:
                    st.write(f"[Link zum Produkt]({wish['link']})")
                
                # Display images
                if wish.get('images') and isinstance(wish.get('images'), list) and len(wish.get('images', [])) > 0:
                    try:
                        # Filter out non-dict items (old format compatibility)
                        valid_images = [img for img in wish.get('images', []) if isinstance(img, dict) and 'data' in img]
                        if valid_images:
                            cols = st.columns(min(len(valid_images), 3))
                            for idx, img in enumerate(valid_images):
                                with cols[idx % 3]:
                                    image_bytes = base64.b64decode(img['data'])
                                    st.image(image_bytes, use_container_width=True)
                    except Exception as e:
                        pass  # Silently skip if image decoding fails
                
                # If buy_self and not purchased yet, show purchase form
                if wish.get("buy_self") and not wish.get("purchased"):
                    with st.form(key=f"self_purchase_{wish['id']}"):
                        estimated_price = wish.get("price", 0.0)
                        st.write(f"💰 Geschätzter Preis: {estimated_price:.2f}€")
                        actual_price = st.number_input(
                            "Tatsächlicher Preis (€)", 
                            min_value=0.0, 
                            value=estimated_price,
                            format="%.2f",
                            key=f"self_price_{wish['id']}"
                        )
                        if st.form_submit_button("✓ Als gekauft markieren"):
                            for w in st.session_state['data']:
                                if w['id'] == wish['id']:
                                    w['purchased'] = True
                                    w['actual_price'] = actual_price
                                    w['claimed_by'] = st.session_state['username']
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()
                
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
                # For suggestions, use suggested_for instead of owner_user
                recipient = item.get('suggested_for') if item.get('type') == 'suggestion' else item.get('owner_user')
                st.subheader(f"{item.get('wish_name', 'Unbekannt')} (für {recipient or 'Unbekannt'})")
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
                                    if 'reimbursed' not in w:
                                        w['reimbursed'] = False
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()

    # --- Column 2: Others' Wishlists ---
    with col2:
        st.header("🎁 Wunschlisten der Anderen")
        other_wishes = [
            w for w in st.session_state['data'] 
            if w.get("owner_user") != st.session_state['username'] and w.get("others_can_buy")
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
                    if wish.get('images') and isinstance(wish['images'], list) and len(wish['images']) > 0:
                        try:
                            # Filter out non-dict items (old format compatibility)
                            valid_images = [img for img in wish['images'] if isinstance(img, dict) and 'data' in img]
                            if valid_images:
                                cols = st.columns(min(len(valid_images), 3))
                                for idx, img in enumerate(valid_images):
                                    with cols[idx % 3]:
                                        image_bytes = base64.b64decode(img['data'])
                                        st.image(image_bytes, use_container_width=True)
                        except Exception as e:
                            pass  # Silently skip if image decoding fails

                    if wish.get("claimed_by") is None:
                        if st.button("Ich besorge das!", key=f"claim_{wish['id']}"):
                            for w in st.session_state['data']:
                                if w['id'] == wish['id']:
                                    w['claimed_by'] = st.session_state['username']
                                    w['claimed_at'] = datetime.datetime.now().isoformat()
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()
                    elif wish.get("claimed_by") == st.session_state['username']:
                        st.success("Du besorgst das.")
                    else:
                        st.warning(f"Wird bereits von {wish.get('claimed_by')} besorgt.")

        # --- Gift Suggestions for Others ---
        st.header("💡 Geschenkvorschlag machen")
        with st.expander("Einen geheimen Geschenkvorschlag für jemanden machen"):
            with st.form("suggestion_form"):
                st.info("💡 Dein Vorschlag wird nur für andere sichtbar sein, nicht für die Person selbst!")
                suggestion_for = st.selectbox("Für wen?", [u for u in ALL_USERS if u != st.session_state['username']])
                suggestion_name = st.text_input("Geschenkidee")
                suggestion_desc = st.text_area("Beschreibung / Warum ist das eine gute Idee?")
                suggestion_link = st.text_input("Link (optional)")
                suggestion_price = st.number_input("Ungefährer Preis (€)", min_value=0.0, format="%.2f")
                
                if st.form_submit_button("💡 Vorschlag speichern"):
                    if suggestion_name and suggestion_desc:
                        new_suggestion = {
                            "id": str(uuid.uuid4()),
                            "type": "suggestion",
                            "suggested_by": st.session_state['username'],
                            "suggested_for": suggestion_for,
                            "wish_name": suggestion_name,
                            "description": suggestion_desc,
                            "link": suggestion_link,
                            "price": suggestion_price,
                            "images": [],
                            "created_at": datetime.datetime.now().isoformat(),
                            "claimed_by": None,
                            "claimed_at": None,
                            "purchased": False,
                            "actual_price": None
                        }
                        st.session_state.data.append(new_suggestion)
                        save_data(st.session_state.data)
                        st.success(f"Geheimer Vorschlag für {suggestion_for} gespeichert!")
                        st.rerun()

        # --- Display Suggestions visible to me (but NOT for me) ---
        st.header("🎁 Geschenkvorschläge von anderen")
        st.write("Hier siehst du Geschenkideen, die andere für deine Freunde/Familie vorgeschlagen haben.")
        
        # Show suggestions FOR other people (not for the current user)
        visible_suggestions = [
            w for w in st.session_state['data'] 
            if w.get("type") == "suggestion" 
            and w.get("suggested_for") != st.session_state['username']  # NOT for me
        ]
        
        if not visible_suggestions:
            st.info("Es gibt derzeit keine Geschenkvorschläge.")
        else:
            # Group by person
            suggestions_by_person = {}
            for suggestion in visible_suggestions:
                person = suggestion['suggested_for']
                if person not in suggestions_by_person:
                    suggestions_by_person[person] = []
                suggestions_by_person[person].append(suggestion)
            
            for person, suggestions in suggestions_by_person.items():
                st.subheader(f"Vorschläge für {person}")
                for suggestion in suggestions:
                    with st.container(border=True):
                        price_display = f"({suggestion.get('price', 0.0):.2f}€)" if suggestion.get('price') else ""
                        st.write(f"**{suggestion.get('wish_name', 'Unbekannt')}** {price_display}")
                        st.write(f"*Vorgeschlagen von {suggestion.get('suggested_by', 'Unbekannt')}*")
                        st.write(suggestion.get('description', ''))
                        if suggestion.get('link'):
                            st.write(f"[Link]({suggestion.get('link')})")
                        
                        # Check if already claimed/purchased
                        if suggestion.get("purchased"):
                            actual_price = suggestion.get("actual_price", 0)
                            claimed_by = suggestion.get("claimed_by", "jemand")
                            st.success(f"✅ Wurde bereits von {claimed_by} besorgt ({actual_price:.2f}€)")
                        elif suggestion.get("claimed_by"):
                            if suggestion["claimed_by"] == st.session_state['username']:
                                # I claimed it - show purchase form
                                estimated_price = suggestion.get("price", 0.0)
                                with st.form(key=f"purchase_suggestion_{suggestion['id']}"):
                                    st.write(f"Geschätzter Preis: {estimated_price:.2f}€")
                                    actual_price = st.number_input(
                                        "Tatsächlicher Preis (€)", 
                                        min_value=0.0, 
                                        value=estimated_price,
                                        format="%.2f",
                                        key=f"sugg_price_{suggestion['id']}"
                                    )
                                    if st.form_submit_button("✓ Als gekauft markieren"):
                                        for w in st.session_state['data']:
                                            if w['id'] == suggestion['id']:
                                                w['purchased'] = True
                                                w['actual_price'] = actual_price
                                                break
                                        save_data(st.session_state['data'])
                                        st.rerun()
                            else:
                                st.warning(f"Wird bereits von {suggestion['claimed_by']} besorgt.")
                        else:
                            # Available to claim
                            if st.button("Ich besorge das!", key=f"claim_sugg_{suggestion['id']}"):
                                for w in st.session_state['data']:
                                    if w['id'] == suggestion['id']:
                                        w['claimed_by'] = st.session_state['username']
                                        w['claimed_at'] = datetime.datetime.now().isoformat()
                                        break
                                save_data(st.session_state['data'])
                                st.rerun()
                        
                        # Edit and Delete buttons for the person who made the suggestion
                        if suggestion.get('suggested_by') == st.session_state['username']:
                            col_edit_sugg, col_delete_sugg = st.columns(2)
                            with col_edit_sugg:
                                if st.button(f"✏️ Bearbeiten", key=f"edit_sugg_{suggestion['id']}"):
                                    st.session_state.edit_wish_id = suggestion['id']
                                    st.rerun()
                            with col_delete_sugg:
                                if st.button(f"🗑️ Löschen", key=f"del_sugg_{suggestion['id']}"):
                                    st.session_state['data'] = [w for w in st.session_state['data'] if w['id'] != suggestion['id']]
                                    save_data(st.session_state['data'])
                                    st.rerun()

        # --- Display My Expert Assignments ---
        st.header("👨‍🏫 Meine Expertenaufträge")
        my_expert_tasks = [w for w in st.session_state['data'] if w.get("responsible_person") == st.session_state['username']]

        if not my_expert_tasks:
            st.info("Dir wurden keine Expertenaufträge zugewiesen.")
        
        for task in my_expert_tasks:
            with st.container(border=True):
                st.subheader(f"{task.get('wish_name', 'Unbekannt')} (für {task.get('owner_user', 'Unbekannt')})")
                st.write(f"**Beschreibung:** {task.get('description', '')}")
                if task.get('link'):
                    st.write(f"[Link zum Produkt]({task.get('link')})")
                
                # Display images
                if task.get('images') and isinstance(task['images'], list) and len(task['images']) > 0:
                    try:
                        # Filter out non-dict items (old format compatibility)
                        valid_images = [img for img in task['images'] if isinstance(img, dict) and 'data' in img]
                        if valid_images:
                            cols = st.columns(min(len(valid_images), 3))
                            for idx, img in enumerate(valid_images):
                                with cols[idx % 3]:
                                    image_bytes = base64.b64decode(img['data'])
                                    st.image(image_bytes, use_container_width=True)
                    except Exception as e:
                        pass  # Silently skip if image decoding fails
                
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
                reimbursed_status = "✅ Ja" if item.get('reimbursed', False) else "❌ Nein"
                # For suggestions, use suggested_for instead of owner_user
                recipient = item.get('suggested_for') if item.get('type') == 'suggestion' else item.get('owner_user')
                table_data.append({
                    "Geschenk": item.get('wish_name', 'Unbekannt'),
                    "Für": recipient or 'Unbekannt',
                    "Geschätzter Preis": f"{item.get('price', 0.0):.2f}€",
                    "Tatsächlicher Preis": f"{item.get('actual_price', 0.0):.2f}€",
                    "Erstattet": reimbursed_status
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            total_spent = sum(item.get('actual_price', 0.0) for item in purchased_items)
            total_reimbursed = sum(item.get('actual_price', 0.0) for item in purchased_items if item.get('reimbursed', False))
            total_outstanding = total_spent - total_reimbursed
            
            st.markdown(f"### **Gesamtausgaben: {total_spent:.2f}€**")
            st.markdown(f"**Erstattet: {total_reimbursed:.2f}€**")
            st.markdown(f"**Noch offen: {total_outstanding:.2f}€**")
            
            # Allow marking items as reimbursed
            st.subheader("Erstattung markieren")
            for item in purchased_items:
                if not item.get('reimbursed', False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{item.get('wish_name', 'Unbekannt')} ({item.get('actual_price', 0.0):.2f}€)")
                    with col2:
                        if st.button("✓ Erstattet", key=f"reimburse_{item['id']}"):
                            for w in st.session_state['data']:
                                if w['id'] == item['id']:
                                    w['reimbursed'] = True
                                    break
                            save_data(st.session_state['data'])
                            st.rerun()

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
                            reimbursed_status = "✅ Ja" if item.get('reimbursed', False) else "❌ Nein"
                            table_data.append({
                                "Geschenk": item.get('wish_name', 'Unbekannt'),
                                "Für": item.get('owner_user', 'Unbekannt'),
                                "Geschätzter Preis": f"{item.get('price', 0.0):.2f}€",
                                "Tatsächlicher Preis": f"{item.get('actual_price', 0.0):.2f}€",
                                "Erstattet": reimbursed_status
                            })
                        
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        
                        user_total = sum(item.get('actual_price', 0.0) for item in user_purchased)
                        user_reimbursed = sum(item.get('actual_price', 0.0) for item in user_purchased if item.get('reimbursed', False))
                        user_outstanding = user_total - user_reimbursed
                        
                        st.markdown(f"**{user} Gesamt: {user_total:.2f}€**")
                        st.markdown(f"**Erstattet: {user_reimbursed:.2f}€**")
                        st.markdown(f"**Noch offen: {user_outstanding:.2f}€**")
                else:
                    st.info(f"{user} hat noch keine sichtbaren Geschenke als gekauft markiert.")


def meal_planning_page():
    """Display the meal planning page with dish proposals and day assignments."""
    
    if st.button("⬅️ Zurück zur Übersicht"):
        navigate_to('dashboard')
        st.rerun()
    
    st.title("🍽️ Essensplanung für die Weihnachtsfeiertage")
    
    # Initialize meal planning data structure
    if 'meal_proposals' not in st.session_state.planning_data:
        st.session_state.planning_data['meal_proposals'] = []
    if 'day_assignments' not in st.session_state.planning_data:
        # New structure: day_assignments[date][category] = [dish_ids]
        st.session_state.planning_data['day_assignments'] = {}
    
    # Define categories with emojis
    categories = {
        "Vorspeise": "🥗",
        "Hauptspeise": "🍖",
        "Nachspeise": "🍰",
        "Snacks": "🥨"
    }
    
    # Define the days
    days = [
        {"date": "2025-12-23", "name": "23. Dezember", "emoji": "🎄"},
        {"date": "2025-12-24", "name": "Heiligabend (24.12.)", "emoji": "🎄"},
        {"date": "2025-12-25", "name": "1. Weihnachtstag (25.12.)", "emoji": "🎅"},
        {"date": "2025-12-26", "name": "2. Weihnachtstag (26.12.)", "emoji": "🎁"}
    ]
    
    # Two columns layout
    col_proposals, col_schedule = st.columns([1, 1])
    
    # Left column: Dish proposals
    with col_proposals:
        st.header("🍴 Gerichtsvorschläge")
        
        # Add new dish proposal
        with st.expander("➕ Neues Gericht vorschlagen", expanded=False):
            with st.form("new_dish_form"):
                dish_name = st.text_input("Gericht (z.B. Gans, Raclette, Fondue...)")
                category = st.selectbox("Kategorie", list(categories.keys()))
                dish_desc = st.text_area("Beschreibung / Notizen", placeholder="z.B. Zutaten, Zubereitungshinweise...")
                responsible = st.selectbox("Wer kümmert sich?", [""] + ALL_USERS)
                
                if st.form_submit_button("💾 Vorschlag speichern"):
                    if dish_name:
                        new_dish = {
                            "id": str(uuid.uuid4()),
                            "name": dish_name,
                            "category": category,
                            "description": dish_desc,
                            "proposed_by": st.session_state['username'],
                            "responsible": responsible if responsible else None,
                            "created_at": datetime.datetime.now().isoformat(),
                            "votes": []
                        }
                        st.session_state.planning_data['meal_proposals'].append(new_dish)
                        save_planning_data(st.session_state.planning_data)
                        st.success(f"✓ {category} '{dish_name}' hinzugefügt!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Bitte gib einen Gerichtsnamen ein!")
        
        # Display all dish proposals grouped by category
        if not st.session_state.planning_data['meal_proposals']:
            st.info("Noch keine Gerichtsvorschläge vorhanden.")
        else:
            st.write("**Alle Gerichtsvorschläge:**")
            st.caption("👍 Stimme für deine Favoriten ab!")
            
            # Group dishes by category
            for cat_name, cat_emoji in categories.items():
                dishes_in_category = [d for d in st.session_state.planning_data['meal_proposals'] if d.get('category') == cat_name]
                
                if dishes_in_category:
                    st.markdown(f"### {cat_emoji} {cat_name}")
                    
                    for dish in dishes_in_category:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"**{dish['name']}**")
                                if dish.get('description'):
                                    st.write(f"_{dish['description']}_")
                                st.caption(f"Vorgeschlagen von {dish['proposed_by']}")
                                if dish.get('responsible'):
                                    st.caption(f"👨‍🍳 Verantwortlich: {dish['responsible']}")
                            
                            with col2:
                                # Vote count
                                votes = dish.get('votes', [])
                                vote_count = len(votes)
                                st.metric("👍", vote_count)
                                if votes:
                                    st.caption(f"{', '.join(votes)}")
                                
                                # Vote button
                                user_voted = st.session_state['username'] in votes
                                if user_voted:
                                    if st.button("❌", key=f"unvote_dish_{dish['id']}", help="Stimme zurückziehen"):
                                        # Find the dish in the original list and update it
                                        for d in st.session_state.planning_data['meal_proposals']:
                                            if d['id'] == dish['id']:
                                                if 'votes' not in d:
                                                    d['votes'] = []
                                                if isinstance(d['votes'], list) and st.session_state['username'] in d['votes']:
                                                    d['votes'].remove(st.session_state['username'])
                                                break
                                        save_planning_data(st.session_state.planning_data)
                                        st.rerun()
                                else:
                                    if st.button("👍", key=f"vote_dish_{dish['id']}", help="Dafür stimmen"):
                                        # Find the dish in the original list and update it
                                        for d in st.session_state.planning_data['meal_proposals']:
                                            if d['id'] == dish['id']:
                                                if 'votes' not in d:
                                                    d['votes'] = []
                                                if not isinstance(d['votes'], list):
                                                    d['votes'] = list(d['votes']) if d['votes'] else []
                                                if st.session_state['username'] not in d['votes']:
                                                    d['votes'].append(st.session_state['username'])
                                                break
                                        save_planning_data(st.session_state.planning_data)
                                        st.rerun()
                        
                        # Delete button for creator
                        if dish['proposed_by'] == st.session_state['username']:
                            if st.button("🗑️", key=f"del_dish_{dish['id']}", help="Löschen"):
                                st.session_state.planning_data['meal_proposals'] = [
                                    d for d in st.session_state.planning_data['meal_proposals'] 
                                    if d['id'] != dish['id']
                                ]
                                # Remove from day assignments
                                for day_date in st.session_state.planning_data['day_assignments']:
                                    if st.session_state.planning_data['day_assignments'][day_date] == dish['id']:
                                        st.session_state.planning_data['day_assignments'][day_date] = None
                                save_planning_data(st.session_state.planning_data)
                                st.rerun()
    
    # Right column: Day schedule
    with col_schedule:
        st.header("📅 Wann gibt es was?")
        st.write("Ordne die Gerichte nach Kategorien den Tagen zu:")
        
        for day in days:
            st.subheader(f"{day['emoji']} {day['name']}")
            
            day_key = day['date']
            
            # Initialize day structure if not exists
            if day_key not in st.session_state.planning_data['day_assignments']:
                st.session_state.planning_data['day_assignments'][day_key] = {}
            
            # For each category
            for cat_name, cat_emoji in categories.items():
                st.markdown(f"**{cat_emoji} {cat_name}:**")
                
                # Get assigned dishes for this category
                assigned_dishes = st.session_state.planning_data['day_assignments'][day_key].get(cat_name, [])
                
                # Display assigned dishes
                if assigned_dishes:
                    for dish_id in assigned_dishes:
                        # Find dish details
                        dish = next((d for d in st.session_state.planning_data['meal_proposals'] if d['id'] == dish_id), None)
                        if dish:
                            col_dish, col_remove = st.columns([4, 1])
                            with col_dish:
                                st.write(f"✅ {dish['name']}")
                                if dish.get('responsible'):
                                    st.caption(f"👨‍🍳 {dish['responsible']}")
                            with col_remove:
                                if st.button("❌", key=f"remove_{day_key}_{cat_name}_{dish_id}"):
                                    assigned_dishes.remove(dish_id)
                                    save_planning_data(st.session_state.planning_data)
                                    st.rerun()
                
                # Add new dish to category
                dishes_for_category = [d for d in st.session_state.planning_data['meal_proposals'] if d.get('category') == cat_name]
                
                if dishes_for_category:
                    dish_names = ["➕ Hinzufügen..."] + [d['name'] for d in dishes_for_category]
                    selected = st.selectbox(
                        f"Gericht hinzufügen",
                        dish_names,
                        key=f"add_{day_key}_{cat_name}",
                        label_visibility="collapsed"
                    )
                    
                    if selected != "➕ Hinzufügen...":
                        # Find selected dish
                        selected_dish = next((d for d in dishes_for_category if d['name'] == selected), None)
                        if selected_dish:
                            # Add to assignments
                            if cat_name not in st.session_state.planning_data['day_assignments'][day_key]:
                                st.session_state.planning_data['day_assignments'][day_key][cat_name] = []
                            
                            if selected_dish['id'] not in st.session_state.planning_data['day_assignments'][day_key][cat_name]:
                                st.session_state.planning_data['day_assignments'][day_key][cat_name].append(selected_dish['id'])
                                save_planning_data(st.session_state.planning_data)
                                st.rerun()
                else:
                    st.caption(f"_Keine {cat_name}-Vorschläge vorhanden_")
                
                st.write("")  # Spacing
            
            st.divider()


def attendance_page():
    """Display the attendance tracking page."""
    
    if st.button("⬅️ Zurück zur Übersicht"):
        navigate_to('dashboard')
        st.rerun()
    
    st.title("📅 Wer kommt wann?")
    
    st.write("Hier könnt ihr eintragen, wer an welchen Tagen dabei ist.")
    
    # Define the days
    days = [
        {"date": "2025-12-23", "name": "23. Dezember (Montag)"},
        {"date": "2025-12-24", "name": "24. Dezember (Heiligabend)"},
        {"date": "2025-12-25", "name": "25. Dezember (1. Weihnachtstag)"},
        {"date": "2025-12-26", "name": "26. Dezember (2. Weihnachtstag)"}
    ]
    
    # Initialize attendance data
    if 'attendance' not in st.session_state.planning_data:
        st.session_state.planning_data['attendance'] = {}
    
    # Check if user has already submitted attendance
    user_has_submitted = st.session_state['username'] in st.session_state.planning_data['attendance']
    
    # User's own attendance form
    if user_has_submitted:
        # Show edit button instead of form
        st.subheader(f"✅ Deine Anwesenheit wurde gespeichert")
        if st.button("✏️ Anwesenheit bearbeiten"):
            # Clear the user's data to show form again
            if 'edit_attendance' not in st.session_state:
                st.session_state['edit_attendance'] = False
            st.session_state['edit_attendance'] = not st.session_state.get('edit_attendance', False)
            st.rerun()
    
    # Show form if user hasn't submitted OR is editing
    if not user_has_submitted or st.session_state.get('edit_attendance', False):
        st.subheader(f"📝 Deine Anwesenheit, {st.session_state['username']}")
        
        with st.form("attendance_form"):
            st.write("An welchen Tagen bist du dabei?")
            
            user_attendance = {}
            for day in days:
                st.write(f"**{day['name']}**")
                
                # Get existing data
                existing_days = st.session_state.planning_data['attendance'].get(st.session_state['username'], {}).get('days', {})
                existing = existing_days.get(day['date'], {})
                
                col1, col2, col3, col4 = st.columns(4)
                
                # Radio button for present/unsure/none selection
                with col1:
                    attendance_status = st.radio(
                        "Status",
                        ["Nicht dabei", "Anwesend", "Noch unsicher"],
                        index=2 if existing.get('unsure') else (1 if existing.get('present') else 0),
                        key=f"status_{day['date']}",
                        label_visibility="collapsed",
                        horizontal=False
                    )
                    present = attendance_status == "Anwesend"
                    unsure = attendance_status == "Noch unsicher"
                
                with col2:
                    # Show status emoji
                    if present:
                        st.write("✅")
                    elif unsure:
                        st.write("❓")
                    else:
                        st.write("❌")
                
                with col3:
                    with_partner = st.checkbox("+ Partner", value=existing.get('with_partner', False), key=f"partner_{day['date']}", disabled=not present)
                
                with col4:
                    overnight = st.checkbox("Übernachtung", value=existing.get('overnight', False), key=f"overnight_{day['date']}", disabled=not present)
                
                user_attendance[day['date']] = {
                    "present": present,
                    "unsure": unsure,
                    "with_partner": with_partner if present else False,
                    "overnight": overnight if present else False
                }
            
            notes = st.text_area("Besondere Hinweise (Allergien, Diät-Wünsche, etc.)", 
                                 value=st.session_state.planning_data['attendance'].get(st.session_state['username'], {}).get('notes', ''))
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                submit_button = st.form_submit_button("💾 Speichern")
            with col_cancel:
                if user_has_submitted:  # Only show cancel if editing
                    cancel_button = st.form_submit_button("❌ Abbrechen")
                    if cancel_button:
                        st.session_state['edit_attendance'] = False
                        st.rerun()
            
            if submit_button:
                st.session_state.planning_data['attendance'][st.session_state['username']] = {
                    "days": user_attendance,
                    "notes": notes,
                    "updated_at": datetime.datetime.now().isoformat()
                }
                save_planning_data(st.session_state.planning_data)
                st.session_state['edit_attendance'] = False
                st.success("✓ Deine Anwesenheit wurde gespeichert!")
                st.rerun()
    
    st.divider()
    
    # Overview of everyone's attendance
    st.subheader("👥 Übersicht: Wer ist wann dabei?")
    
    if not st.session_state.planning_data['attendance']:
        st.info("Noch niemand hat seine Anwesenheit eingetragen.")
    else:
        import pandas as pd
        
        for day in days:
            st.write(f"**{day['name']}**")
            
            attendees = []
            unsure_attendees = []
            
            for user, data in st.session_state.planning_data['attendance'].items():
                day_data = data.get('days', {}).get(day['date'], {})
                if day_data.get('present'):
                    if day_data.get('unsure'):
                        unsure_attendees.append(f"{user} ❓")
                    else:
                        partner_info = " (+Partner)" if day_data.get('with_partner') else ""
                        overnight_info = " 🌙" if day_data.get('overnight') else ""
                        attendees.append(f"{user}{partner_info}{overnight_info}")
            
            if attendees or unsure_attendees:
                for attendee in attendees:
                    st.write(f"✓ {attendee}")
                for unsure in unsure_attendees:
                    st.write(f"❓ {unsure}")
            else:
                st.caption("Noch niemand angemeldet für diesen Tag")
            
            st.write("")
        
        # Special notes
        st.write("**📋 Besondere Hinweise:**")
        for user, data in st.session_state.planning_data['attendance'].items():
            if data.get('notes'):
                st.write(f"**{user}:** {data['notes']}")


def advent_calendar_page():
    """Display the advent calendar page."""
    
    if st.button("⬅️ Zurück zur Übersicht"):
        navigate_to('dashboard')
        st.rerun()
    
    st.title("🎄 Adventskalender")
    
    # Get all image files from the images folder
    images_folder = Path("images")
    if images_folder.exists():
        image_files = [f.name for f in images_folder.iterdir() 
                      if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png'] 
                      and not f.name.endswith('.~tmp')]
        # Sort alphabetically for consistent ordering across all users
        image_files.sort()
    else:
        image_files = []
    
    # Create a consistent random mapping of days to images using a fixed seed
    # This ensures ALL users see the same image for the same day
    import random
    rng = random.Random(2025)  # Use separate Random instance with fixed seed
    if len(image_files) >= 24:
        shuffled_images = image_files.copy()
        rng.shuffle(shuffled_images)  # Shuffle with fixed seed
        day_to_image = {day: shuffled_images[day-1] for day in range(1, 25)}
    else:
        day_to_image = {}
    
    # Year-based photo captions with funny descriptions
    year_captions = {
        "2005": "Mama mit den Mädels",
        "2006": "Emmy's Reaktion auf Omas Geschenk: 'Danke... aber nein danke!'",
        "2007": "Lukas hatte damals schon mehr Style als heute!",
        "2008": "Familien-Orchester in Action - Emmy sorgt für die 'besondere' Note!",
        "2008-2": "Emmy kann nicht warten: Winteroutfit-Test im Wohnzimmer!",
        "2009": "Lukas als Chef am Schneidebrett - hoffentlich nur das Essen!",
        "2009-2": "Emmy als Engel - zumindest optisch! 😇",
        "2010": "Die Mädels rocken Weihnachten - unplugged!",
        "2011": "Hühott! Tim's Freude war SO groß, er vergaß die Hos'!",
        "2011-2": "Neues Ski-Equipment? Ab auf die Couch-Piste!",
        "2012": "Houston, wir haben einen Start: Tim's erster Flug!",
        "2012-2": "Klein-Tim der Handwerker - die Werkbank hat (fast) überlebt! 🔨",
        "2013": "Krisenzeiten 2013: Immerhin eine Rolle pro Person! 🧻",
        "2014": "Daddy war Selfie-König bevor es cool war!",
        "2015": "Es ist Krieg! Das große Nerf-Battle beginnt! 🎯",
        "2016": "Aloha! Weihnachten trifft Hawaii-Style! 🌺",
        "2017": "Tim + Autos = wahre Liebe! Vroom vroom! 🚗",
        "2018": "Endlich! Tim darf auch ins Familien-Orchester!",
        "2019": "Illinois repräsentiert! U-S-A! U-S-A!",
        "2020": "Emmy's skeptischer Blick: 'Daddy, bitte nicht die Finger!'",
        "2021": "Prost auf ein weiteres verrücktes Jahr! 🥂",
        "2022": "Hola desde Business Class - Weihnachten mit Stil! ✈️",
        "2023": "Team Weihnachten bereit zum Anpfiff - äh, Auspacken! ⚽",
        "2024": "Frohe Weihnachten 2024 - Und das Abenteuer geht weiter! 🎄"
    }
    
    # Calculate current day
    today = datetime.date.today()
    december_1st = datetime.date(today.year, 12, 1)
    
    # Check if we're in December
    if today.month == 12 and today.day <= 24:
        current_day = today.day
        st.write(f"Heute ist der {today.day}. Dezember!")
    else:
        current_day = 0  # Outside of advent calendar period
        days_until = (december_1st - today).days if december_1st > today else 0
        if days_until > 0:
            st.info(f"Der Adventskalender beginnt am 1. Dezember! Noch {days_until} Tage!")
    
    st.write("### 🎁 24 Türchen bis Heiligabend")
    st.write("✨ Jeden Tag ein Weihnachtsfoto aus vergangenen Jahren!")
    
    # Load user-specific opened doors from planning data
    if 'advent_doors' not in st.session_state.planning_data:
        st.session_state.planning_data['advent_doors'] = {}
    
    current_user = st.session_state['username']
    if current_user not in st.session_state.planning_data['advent_doors']:
        st.session_state.planning_data['advent_doors'][current_user] = []
    
    # Initialize session state for opened doors (for this user)
    if 'opened_doors' not in st.session_state:
        st.session_state['opened_doors'] = set(st.session_state.planning_data['advent_doors'][current_user])
    
    # Create 4 rows with 6 doors each
    for row in range(4):
        cols = st.columns(6)
        for col_idx, col in enumerate(cols):
            day = row * 6 + col_idx + 1
            with col:
                # Always calculate door_date for display purposes
                door_date = datetime.date(today.year, 12, day)
                
                # Check if door can be opened (must be December and we've reached this day)
                can_open = today >= door_date and today.month == 12
                
                is_opened = day in st.session_state['opened_doors']
                
                if can_open:
                    if st.button(f"{'📖' if is_opened else '🎁'} {day}", 
                               key=f"door_{day}", 
                               use_container_width=True,
                               type="primary" if is_opened else "secondary"):
                        st.session_state['opened_doors'].add(day)
                        # Save to planning data (persistent storage)
                        st.session_state.planning_data['advent_doors'][current_user] = list(st.session_state['opened_doors'])
                        save_planning_data(st.session_state.planning_data)
                        st.rerun()
                else:
                    st.button(f"🔒 {day}", key=f"door_{day}_locked", 
                            use_container_width=True, disabled=True)
    
    st.markdown("---")
    
    # Display opened doors with their images
    if st.session_state['opened_doors']:
        st.subheader("🎄 Geöffnete Türchen")
        
        # Sort opened doors
        opened_sorted = sorted(st.session_state['opened_doors'], reverse=True)
        
        # Display images in a grid (3 columns)
        cols_per_row = 3
        for idx, day in enumerate(opened_sorted):
            if idx % cols_per_row == 0:
                cols = st.columns(cols_per_row)
            
            if day in day_to_image:
                image_path = images_folder / day_to_image[day]
                
                with cols[idx % cols_per_row]:
                    try:
                        # Extract year from filename if possible
                        filename = day_to_image[day]
                        year_match = filename.split('.')[0].split('-')[0]
                        try:
                            year = int(year_match)
                            caption = f"🎄 Türchen {day} - Weihnachten {year}"
                        except:
                            caption = f"🎄 Türchen {day}"
                        
                        # Check if image file exists
                        if image_path.exists():
                            # Open image with PIL first to ensure it's valid
                            img = Image.open(image_path)
                            # Display image - use_container_width allows fullscreen expansion
                            st.image(img, caption=caption, use_container_width=True)
                            
                            # Display year-specific funny caption
                            # Extract year from filename (e.g., "2005", "2008-2", "2009-2")
                            year_key = Path(filename).stem  # Gets filename without extension
                            if year_key in year_captions:
                                st.markdown(f"*{year_captions[year_key]}*")
                            
                            # Initialize comments structure in planning_data
                            if 'advent_comments' not in st.session_state.planning_data:
                                st.session_state.planning_data['advent_comments'] = {}
                            
                            if str(day) not in st.session_state.planning_data['advent_comments']:
                                st.session_state.planning_data['advent_comments'][str(day)] = []
                            
                            # Display existing comments
                            comments = st.session_state.planning_data['advent_comments'][str(day)]
                            if comments:
                                st.markdown("---")
                                st.markdown("**💬 Kommentare:**")
                                for comment in comments:
                                    comment_user = comment.get('user', 'Unbekannt')
                                    comment_text = comment.get('text', '')
                                    comment_time = comment.get('timestamp', '')
                                    
                                    # Format timestamp
                                    try:
                                        dt = datetime.datetime.fromisoformat(comment_time)
                                        time_str = dt.strftime('%d.%m. %H:%M')
                                    except:
                                        time_str = ''
                                    
                                    st.markdown(f"**{comment_user}** {f'({time_str})' if time_str else ''}")
                                    st.markdown(f"> {comment_text}")
                            
                            # Add new comment form
                            st.markdown("---")
                            with st.form(key=f"comment_form_{day}"):
                                new_comment = st.text_area(
                                    "💬 Kommentar hinzufügen:",
                                    placeholder="Teile deine Gedanken zu diesem Foto...",
                                    key=f"comment_input_{day}",
                                    max_chars=500
                                )
                                if st.form_submit_button("📤 Kommentar posten"):
                                    if new_comment and new_comment.strip():
                                        comment_data = {
                                            "user": st.session_state['username'],
                                            "text": new_comment.strip(),
                                            "timestamp": datetime.datetime.now().isoformat()
                                        }
                                        st.session_state.planning_data['advent_comments'][str(day)].append(comment_data)
                                        save_planning_data(st.session_state.planning_data)
                                        st.success("✅ Kommentar wurde gepostet!")
                                        st.rerun()
                                    else:
                                        st.warning("⚠️ Bitte gib einen Kommentar ein!")
                        else:
                            st.warning(f"Bild nicht gefunden: {filename}")
                        
                    except Exception as e:
                        st.error(f"Bild konnte nicht geladen werden: {str(e)}")
    else:
        st.info("💡 **Hinweis:** Öffne ein Türchen, um ein Weihnachtsfoto zu sehen! Ab dem 1. Dezember wird jeden Tag ein neues Türchen freigeschaltet.")
    
    # Show hint if not in December yet
    if today.month != 12:
        st.warning("🎅 Der Adventskalender startet am 1. Dezember!")
        days_until_december = (datetime.date(today.year, 12, 1) - today).days
        if days_until_december > 0:
            st.write(f"Noch **{days_until_december} Tage** bis zum Start!")

# --- App Entry Point ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    main_app()
else:
    login_page()
