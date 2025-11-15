"""
Christmas Wishlist App - Main Application (Improved & Consolidated)
A beautiful, festive, multi-user Christmas wishlist app with authentication.
"""

import gradio as gr
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 1. Configuration Constants
# ==========================

# User credentials
USER_CREDENTIALS = {
    "Dieter": "dieter123",
    "Gudrun": "gudrun123",
    "Lukas": "lukas123",
    "Pia": "pia123",
    "Emmy": "emmy123",
    "Tim": "tim123"
}

# List of all users
ALL_USERS = list(USER_CREDENTIALS.keys())

# Data file path
DATA_FILE = Path("wunschliste.json")


# 2. Styles and Scripts
# =====================

CSS_STYLES = """
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&display=swap');
    body, .gradio-container {
        font-family: 'Fredoka', 'Lato', sans-serif;
        background: url('https://images.unsplash.com/photo-1519125323398-675f0ddb6308?auto=format&fit=crop&w=1500&q=80') no-repeat center center fixed;
        background-size: cover;
    }
    .gradio-container {
        background: rgba(255,255,255,0.85) !important; min-height: 100vh;
    }
    #main-title {
        text-align: center; color: #c8102e; font-size: 2.7em !important;
        font-weight: 700; letter-spacing: 2px;
        text-shadow: 2px 2px 8px #fff8, 0 2px 8px #c8102e22; margin-bottom: 0.5em;
    }
    .gradio-group {
        border: none !important; box-shadow: 0 8px 32px rgba(0,0,0,0.13) !important;
        border-radius: 18px !important; background: rgba(255,255,255,0.97);
        margin-bottom: 28px !important; padding: 18px !important;
    }
    .gradio-group h2 {
        color: #006a4e; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;
        margin-top: 0; font-weight: 700;
    }
    .gradio-button {
        border-radius: 10px !important; font-weight: 700 !important;
        font-size: 1.08em !important;
    }
    .snow {
        pointer-events: none; position: fixed; top: 0; left: 0;
        width: 100vw; height: 100vh; z-index: 9999;
    }
"""

JAVASCRIPT_CODE = """
<script>
// Helper function to find and click hidden Gradio buttons
function triggerGradio(inputId, buttonText, value) {
    const inputs = document.querySelectorAll('input[type="text"]');
    let targetInput = null;
    for (let inp of inputs) {
        if (inp.parentElement && inp.parentElement.querySelector('label')?.textContent === inputId) {
            targetInput = inp;
            break;
        }
    }
    if (!targetInput) {
        console.error('Gradio input with label "' + inputId + '" not found.');
        return;
    }
    targetInput.value = value;
    targetInput.dispatchEvent(new Event('input', { bubbles: true }));
    const buttons = document.querySelectorAll('button');
    let triggerButton = null;
    for (let btn of buttons) {
        if (btn.textContent.trim() === buttonText) {
            triggerButton = btn;
            break;
        }
    }
    if (!triggerButton) {
        console.error('Gradio button with text "' + buttonText + '" not found.');
        return;
    }
    setTimeout(function() { triggerButton.click(); }, 50);
}

// Define all functions in global scope immediately
function claimWish(wishId) {
    triggerGradio('wish_id', 'trigger', wishId);
}

function markPurchased(wishId) {
    triggerGradio('purchase_wish_id', 'mark_purchased_trigger', wishId);
}

function markUnpurchased(wishId) {
    triggerGradio('purchase_wish_id', 'mark_unpurchased_trigger', wishId);
}

function editWish(wishId) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    triggerGradio('edit_wish_id', 'edit_trigger', wishId);
}

function deleteWish(wishId) {
    if (confirm('Möchtest du diesen Wunsch wirklich löschen?')) {
        triggerGradio('delete_wish_id', 'delete_trigger', wishId);
    }
}

// Snow effect initialization
setTimeout(function() {
    const canvas = document.querySelector('.snow');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w = window.innerWidth, h = window.innerHeight;
    canvas.width = w; canvas.height = h;
    let flakes = [];
    for (let i = 0; i < 70; i++) {
        flakes.push({
            x: Math.random()*w, 
            y: Math.random()*h,
            r: 1.5 + Math.random()*3.5, 
            d: 1 + Math.random()*1.5
        });
    }
    function draw() {
        if (!ctx) return;
        ctx.clearRect(0,0,w,h);
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.beginPath();
        for (let i = 0; i < flakes.length; i++) {
            let f = flakes[i];
            ctx.moveTo(f.x, f.y);
            ctx.arc(f.x, f.y, f.r, 0, Math.PI*2, true);
        }
        ctx.fill();
        update();
    }
    let angle = 0;
    function update() {
        angle += 0.002;
        for (let i = 0; i < flakes.length; i++) {
            let f = flakes[i];
            f.y += Math.pow(f.d, 2) + 1;
            f.x += Math.sin(angle) * 1.2;
            if (f.y > h) { 
                f.x = Math.random()*w; 
                f.y = -5; 
            }
        }
    }
    setInterval(draw, 33);
    window.addEventListener('resize', function() {
        w = window.innerWidth; 
        h = window.innerHeight;
        if(canvas) { 
            canvas.width = w; 
            canvas.height = h; 
        }
    });
}, 500);
</script>
"""

# 3. Backend Logic Functions
# ========================

# Helper functions for data persistence
def load_data() -> List[Dict[str, Any]]:
    """Loads the wish list data from the JSON file."""
    if not DATA_FILE.exists():
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            # Handle empty file case
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data: List[Dict[str, Any]]):
    """Saves the wish list data to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# User and UI functions
def get_other_users(request: gr.Request) -> List[str]:
    """Returns a list of all users except the current one."""
    current_user = request.username
    return [user for user in ALL_USERS if user != current_user]

# Wish manipulation functions
def add_wish(state, name, link, desc, note, color, buy_option, images, responsible_person, request: gr.Request):
    """Adds a new wish to the list."""
    current_user = request.username
    is_for_others = buy_option == "Andere dürfen es kaufen"
    if not name or not desc:
        raise gr.Error("Bitte gib mindestens einen Namen und eine Beschreibung für deinen Wunsch an.")
    if is_for_others and not images:
        raise gr.Error("Bitte lade Bilder hoch, damit andere wissen, was sie kaufen sollen.")

    new_wish = {
        "id": str(uuid.uuid4()), "owner_user": current_user, "wish_name": name,
        "link": link, "description": desc, "note": note, "color": color,
        "buy_self": not is_for_others, "others_can_buy": is_for_others,
        "images": [str(p) for p in images] if images else [],
        "responsible_person": responsible_person, "claimed_by": None,
        "claimed_at": None, "purchased": False,
    }
    state.append(new_wish)
    save_data(state)
    gr.Info(f"Wunsch '{name}' hinzugefügt!")
    return state, render_my_wishlist(state, request)

def update_wish(wish_id, state, name, link, desc, note, color, buy_option, images, responsible_person, request: gr.Request):
    """Updates an existing wish."""
    current_user = request.username
    is_for_others = buy_option == "Andere dürfen es kaufen"
    
    for wish in state:
        if wish["id"] == wish_id and wish["owner_user"] == current_user:
            wish.update({
                "wish_name": name, "link": link, "description": desc, "note": note,
                "color": color, "buy_self": not is_for_others, "others_can_buy": is_for_others,
                "responsible_person": responsible_person
            })
            if images: wish["images"] = [str(p) for p in images]
            break
    
    save_data(state)
    gr.Info(f"Wunsch '{name}' aktualisiert!")
    return state, render_my_wishlist(state, request)

def delete_wish(wish_id, state, request: gr.Request):
    """Deletes a wish from the list."""
    current_user = request.username
    original_len = len(state)
    state[:] = [w for w in state if not (w["id"] == wish_id and w["owner_user"] == current_user)]
    if len(state) < original_len:
        save_data(state)
        gr.Info("Wunsch gelöscht!")
    return state, render_my_wishlist(state, request)

def get_wish_data(wish_id, state, request: gr.Request):
    """Gets the data for a specific wish to populate the edit form."""
    for wish in state:
        if wish["id"] == wish_id and wish["owner_user"] == request.username:
            return (
                gr.update(value=wish["wish_name"]), gr.update(value=wish["link"]),
                gr.update(value=wish["description"]), gr.update(value=wish["note"]),
                gr.update(value=wish["color"]),
                gr.update(value="Ich kaufe es selbst" if wish["buy_self"] else "Andere dürfen es kaufen"),
                gr.update(value=wish.get("responsible_person")),
                gr.update(value=wish["id"]), # Set the current_edit_wish_id
                gr.update(value="Wunsch speichern", variant="secondary") # Change button text
            )
    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(value=""), gr.update(value="Wunsch hinzufügen", variant="primary")

def claim_wish(wish_id, state, request: gr.Request):
    """Claims a wish for the current user."""
    current_user = request.username
    for wish in state:
        if wish["id"] == wish_id and wish["claimed_by"] is None:
            wish["claimed_by"] = current_user
            wish["claimed_at"] = datetime.datetime.now().isoformat()
            save_data(state)
            gr.Info(f"Du hast '{wish['wish_name']}' für {wish['owner_user']} reserviert!")
            break
    return state

def mark_as_purchased(wish_id, state, request: gr.Request):
    """Marks a wish as purchased."""
    for wish in state:
        if wish["id"] == wish_id and wish["claimed_by"] == request.username:
            wish["purchased"] = True
            save_data(state)
            gr.Info(f"'{wish['wish_name']}' als gekauft markiert.")
            break
    return state, render_my_claimed_items(state, request)

def mark_as_unpurchased(wish_id, state, request: gr.Request):
    """Marks a wish as not purchased (undo)."""
    for wish in state:
        if wish["id"] == wish_id and wish["claimed_by"] == request.username:
            wish["purchased"] = False
            save_data(state)
            break
    return state, render_my_claimed_items(state, request)

# HTML Rendering functions
def render_my_wishlist(data, request: gr.Request) -> gr.HTML:
    """Renders the wish list for the currently logged-in user with edit/delete buttons."""
    my_wishes = [w for w in data if w["owner_user"] == request.username]
    if not my_wishes:
        return gr.HTML("<p style='text-align:center; color:#666;'>Du hast noch keine Wünsche hinzugefügt.</p>")
    
    html = "<div>"
    for wish in my_wishes:
        status = "🎁 <strong>Wird besorgt!</strong>" if wish["claimed_by"] else "🛍️ <em>Kaufe ich selbst</em>" if wish["buy_self"] else ""
        html += f"""
        <div style='border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; background-color: #fff;'>
            <h3>{wish['wish_name']} {status}</h3>
            <p><b>Beschreibung:</b> {wish['description']}</p>
            {'<p><b>Bilder:</b></p>' + ''.join([f"<img src='/file={p}' style='width:100px; border-radius:5px; margin-right:5px;' />" for p in wish['images']]) if wish['images'] else ''}
            <div style='margin-top: 10px; display: flex; gap: 10px;'>
                <button onclick='editWish("{wish['id']}")'>✏️ Bearbeiten</button>
                <button onclick='deleteWish("{wish['id']}")'>🗑️ Löschen</button>
            </div>
        </div>
        """
    html += "</div>"
    return gr.HTML(html)

def render_others_wishlist_with_claim_buttons(state, request: gr.Request) -> gr.HTML:
    """Renders all other users' wishlists with claim buttons."""
    other_wishes = [w for w in state if w["owner_user"] != request.username and w["others_can_buy"]]
    if not other_wishes:
        return gr.HTML("<p style='text-align:center; color:#666;'>Es gibt derzeit keine Wünsche von anderen.</p>")
    
    wishes_by_owner = {}
    for wish in other_wishes:
        owner = wish["owner_user"]
        if owner not in wishes_by_owner:
            wishes_by_owner[owner] = []
        wishes_by_owner[owner].append(wish)
    
    html = ""
    for owner, wishes in wishes_by_owner.items():
        if not wishes: continue
        html += f"<h2>🎁 Wünsche von {owner}</h2>"
        for wish in wishes:
            claim_html = f"<button onclick='claimWish(\"{wish['id']}\")'>Ich besorge das!</button>"
            if wish["claimed_by"] == request.username:
                claim_html = "<p style='color: green; font-weight: bold;'>✅ Du besorgst das.</p>"
            elif wish["claimed_by"]:
                claim_html = f"<p style='color: #666;'>🎁 Wird bereits von {wish['claimed_by']} besorgt.</p>"
            
            html += f"""
            <div style='border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px;'>
                <h3>{wish['wish_name']}</h3>
                <p><b>Beschreibung:</b> {wish['description']}</p>
                 {'<p><b>Bilder:</b></p>' + ''.join([f"<img src='/file={p}' style='width:150px; border-radius:5px; margin-right:5px;' />" for p in wish['images']]) if wish['images'] else ''}
                <div style='margin-top: 10px;'>{claim_html}</div>
            </div>
            """
    return gr.HTML(html)

def render_my_claimed_items(data, request: gr.Request) -> gr.HTML:
    """Renders items the current user has claimed."""
    claimed_items = [w for w in data if w.get("claimed_by") == request.username]
    if not claimed_items:
        return gr.HTML("<p style='text-align:center; color:#666;'>Du hast noch keine Geschenke reserviert.</p>")
        
    to_buy_html = "".join([f"""
        <div style='background-color: #fff8f0; border:1px solid #ddd; padding:15px; margin:10px 0; border-radius:8px;'>
            <h4>{item['wish_name']} (für {item['owner_user']})</h4>
            <button onclick='markPurchased("{item['id']}")'>✓ Als gekauft markieren</button>
        </div>""" for item in claimed_items if not item.get("purchased")])
        
    bought_html = "".join([f"""
        <div style='background-color: #f0fff4; border:1px solid #51cf66; padding:15px; margin:10px 0; border-radius:8px;'>
            <h4>{item['wish_name']} (für {item['owner_user']})</h4>
            <p style='color:#51cf66; font-weight:bold;'>✅ Gekauft</p>
            <button onclick='markUnpurchased("{item['id']}")'>↶ Rückgängig machen</button>
        </div>""" for item in claimed_items if item.get("purchased")])

    return gr.HTML(f"""
        <h2>📋 Meine Besorgungen</h2>
        <h3 style='color: #ff6b6b;'>🛒 Noch zu besorgen</h3>
        {to_buy_html or "<p>Alles erledigt! 🎉</p>"}
        <hr style='margin: 30px 0;'>
        <h3 style='color: #51cf66;'>✅ Schon besorgt</h3>
        {bought_html or "<p>Noch nichts gekauft.</p>"}
    """)

def render_my_expert_assignments(data, request: gr.Request) -> gr.Markdown:
     # This can remain as Markdown if preferred
    return gr.Markdown("Experten-Ansicht wird geladen...")


# 4. UI Layout (Gradio Blocks)
# ============================
with gr.Blocks(title="Gemeinsame Weihnachts-Wunschliste", theme="soft") as demo:
    
    app_state = gr.State(value=load_data())

    # Injiziere CSS, JS und das Schnee-Canvas - JS MUSS ZUERST kommen!
    gr.HTML(JAVASCRIPT_CODE)
    gr.HTML(f"<style>{CSS_STYLES}</style>")
    gr.HTML("<canvas class='snow'></canvas>")

    # --- Hidden Components for Triggers ---
    with gr.Row(visible=False):
        claim_wish_id_input = gr.Textbox(label="wish_id")
        claim_wish_trigger_btn = gr.Button("trigger")
        mark_purchased_id_input = gr.Textbox(label="purchase_wish_id")
        mark_purchased_trigger_btn = gr.Button("mark_purchased_trigger")
        mark_unpurchased_trigger_btn = gr.Button("mark_unpurchased_trigger")
        edit_wish_id_input = gr.Textbox(label="edit_wish_id")
        edit_trigger_btn = gr.Button("edit_trigger")
        delete_wish_id_input = gr.Textbox(label="delete_wish_id")
        delete_trigger_btn = gr.Button("delete_trigger")
        current_edit_wish_id = gr.Textbox(label="current_edit_id")

    # --- UI Structure ---
    gr.Markdown("# 🎄 Gemeinsame Weihnachts-Wunschliste 🎄", elem_id="main-title")
    
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("## 📝 Meine Wunschliste")
                with gr.Accordion("Neuen Wunsch hinzufügen / Bearbeiten", open=True) as form_accordion:
                    wish_name = gr.Textbox(label="Was wünschst du dir?")
                    wish_link = gr.Textbox(label="Link (optional)")
                    wish_desc = gr.Textbox(label="Beschreibung")
                    wish_note = gr.Textbox(label="Notiz (z.B. Größe)")
                    wish_color = gr.Textbox(label="Farbe (optional)")
                    buy_option = gr.Radio(["Ich kaufe es selbst", "Andere dürfen es kaufen"], value="Andere dürfen es kaufen", label="Wer soll es besorgen?")
                    image_upload = gr.File(label="Bilder hochladen", file_count="multiple", interactive=True)
                    other_users_dd_add = gr.Dropdown(label="Experte", allow_custom_value=False)
                    add_wish_btn = gr.Button("Wunsch hinzufügen", variant="primary")
                
                my_wishlist_display = gr.HTML("Lade deine Wünsche...")

            with gr.Group():
                 my_claimed_items_display = gr.HTML("Lade deine Besorgungen...")

        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("## 🎁 Wunschlisten der Anderen")
                others_wishlist_display = gr.HTML("Lade Wunschlisten...")
            with gr.Group():
                gr.Markdown("## 👨‍🏫 Meine Expertenaufträge")
                my_expert_assignments_display = gr.Markdown("Lade deine Expertenaufträge...")

    # 5. Event Logic
    # ==============
    def on_load(request: gr.Request):
        # Lade die Daten bei jedem Neuladen der Seite frisch.
        state = load_data()
        other_users = get_other_users(request)
        return (
            state,
            render_my_wishlist(state, request),
            render_others_wishlist_with_claim_buttons(state, request),
            render_my_claimed_items(state, request),
            render_my_expert_assignments(state, request),
            gr.update(choices=other_users),
        )

    demo.load(
        on_load,
        inputs=None, # Läuft beim Laden der Seite
        outputs=[app_state, my_wishlist_display, others_wishlist_display, my_claimed_items_display, my_expert_assignments_display, other_users_dd_add]
    )

    def handle_add_or_update(state, name, link, desc, note, color, buy_option, images, responsible_person, edit_id, request: gr.Request):
        if edit_id: # If an ID is present, we are updating
            new_state, updated_view = update_wish(edit_id, state, name, link, desc, note, color, buy_option, images, responsible_person, request)
        else: # Otherwise, we are adding a new wish
            new_state, updated_view = add_wish(state, name, link, desc, note, color, buy_option, images, responsible_person, request)
        
        # Reset form fields after action
        return new_state, updated_view, "", "", "", "", "", "Andere dürfen es kaufen", None, None, "", "Wunsch hinzufügen", "primary"

    add_wish_btn.click(
        handle_add_or_update,
        [app_state, wish_name, wish_link, wish_desc, wish_note, wish_color, buy_option, image_upload, other_users_dd_add, current_edit_wish_id],
        [app_state, my_wishlist_display, wish_name, wish_link, wish_desc, wish_note, wish_color, buy_option, image_upload, other_users_dd_add, current_edit_wish_id, add_wish_btn]
    )

    edit_trigger_btn.click(
        get_wish_data,
        [edit_wish_id_input, app_state],
        [wish_name, wish_link, wish_desc, wish_note, wish_color, buy_option, other_users_dd_add, current_edit_wish_id, add_wish_btn]
    )

    delete_trigger_btn.click(
        delete_wish,
        [delete_wish_id_input, app_state],
        [app_state, my_wishlist_display]
    )

    def handle_claim_and_refresh(wish_id, state, request: gr.Request):
        new_state = claim_wish(wish_id, state, request)
        return new_state, render_others_wishlist_with_claim_buttons(new_state, request), render_my_claimed_items(new_state, request)

    claim_wish_trigger_btn.click(
        handle_claim_and_refresh,
        [claim_wish_id_input, app_state],
        [app_state, others_wishlist_display, my_claimed_items_display]
    )

    mark_purchased_trigger_btn.click(mark_as_purchased, [mark_purchased_id_input, app_state], [app_state, my_claimed_items_display])
    mark_unpurchased_trigger_btn.click(mark_as_unpurchased, [mark_purchased_id_input, app_state], [app_state, my_claimed_items_display])


# 6. Launch the App
# =================
if __name__ == "__main__":
    demo.launch(auth=list(USER_CREDENTIALS.items()))