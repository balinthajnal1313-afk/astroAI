import customtkinter as ctk
import threading
import ollama
import json
import os
import re
import sympy as sp
import hashlib
import secrets

from tkinter import filedialog, messagebox
from pypdf import PdfReader
from web_search import search_web


# =========================================================
# BEÁLLÍTÁSOK
# =========================================================

MODEL = "qwen3:4b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# SZÍNEK
# =========================================================

BG = "#080B12"
SIDEBAR = "#0D111B"
PANEL = "#111722"
PANEL_2 = "#151C29"

TEXT = "#F1F5F9"
TEXT_MUTED = "#7F8A9D"

ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"

USER_BUBBLE = "#1D4ED8"
AI_BUBBLE = "#151C29"

BORDER = "#202938"
DANGER = "#7F1D1D"
DANGER_HOVER = "#991B1B"
SUCCESS = "#4ADE80"


# =========================================================
# JSON SEGÉDFÜGGVÉNYEK
# =========================================================

def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print("JSON mentési hiba:", e)
        return False


# =========================================================
# FIÓKRENDSZER
# =========================================================

def normalize_email(email):
    return email.strip().lower()


def valid_email(email):
    return bool(
        re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email.strip()
        )
    )


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000
    )

    return (
        salt.hex(),
        password_hash.hex()
    )


def verify_password(password, salt_hex, stored_hash_hex):
    try:
        salt = bytes.fromhex(salt_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200_000
        ).hex()

        return secrets.compare_digest(
            password_hash,
            stored_hash_hex
        )
    except Exception:
        return False


def load_users():
    return load_json(USERS_FILE, {})


def save_users(users):
    return save_json(USERS_FILE, users)


def user_folder(email):
    safe = hashlib.sha256(
        normalize_email(email).encode("utf-8")
    ).hexdigest()[:24]

    folder = os.path.join(
        DATA_DIR,
        "users",
        safe
    )

    os.makedirs(folder, exist_ok=True)
    return folder


def user_knowledge_file(email):
    return os.path.join(
        user_folder(email),
        "pdf_knowledge.json"
    )


def user_language_file(email):
    return os.path.join(
        user_folder(email),
        "language_memory.json"
    )


def create_account(email, password, username):
    email = normalize_email(email)
    username = username.strip()

    if not valid_email(email):
        return False, "Érvénytelen e-mail-cím."

    if len(password) < 6:
        return False, "A jelszónak legalább 6 karakteresnek kell lennie."

    if len(username) < 2:
        return False, "A felhasználónév legalább 2 karakter legyen."

    users = load_users()

    if email in users:
        return False, "Ezzel az e-mail-címmel már van fiók."

    salt, password_hash = hash_password(password)

    users[email] = {
        "email": email,
        "username": username,
        "salt": salt,
        "password_hash": password_hash
    }

    if not save_users(users):
        return False, "Nem sikerült elmenteni a fiókot."

    user_folder(email)

    return True, "A fiók sikeresen létrejött."


def authenticate(email, password):
    email = normalize_email(email)
    users = load_users()

    user = users.get(email)

    if not user:
        return None

    if not verify_password(
        password,
        user.get("salt", ""),
        user.get("password_hash", "")
    ):
        return None

    return user


def save_session(email):
    return save_json(
        SESSION_FILE,
        {
            "email": normalize_email(email)
        }
    )


def load_session():
    session = load_json(SESSION_FILE, {})

    if not isinstance(session, dict):
        return None

    email = session.get("email")

    if not email:
        return None

    users = load_users()

    if email not in users:
        return None

    return email


def clear_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass


# =========================================================
# PDF ÉS NYELVI MEMÓRIA
# =========================================================

def load_knowledge(email):
    return load_json(
        user_knowledge_file(email),
        []
    )


def save_knowledge(email, knowledge):
    clean_knowledge = []

    for item in knowledge:
        clean_knowledge.append({
            "source": item.get("source", ""),
            "text": item.get("text", "")
        })

    save_json(
        user_knowledge_file(email),
        clean_knowledge
    )


def load_language_memory(email):
    return load_json(
        user_language_file(email),
        []
    )


def save_language_memory(email, memory):
    save_json(
        user_language_file(email),
        memory
    )


# =========================================================
# STOP WORDS
# =========================================================

STOP_WORDS = {
    "a", "az", "egy", "és", "is", "hogy", "ha", "de", "vagy",
    "nem", "mi", "mit", "mikor", "hol", "ki", "van", "volt",
    "lesz", "ez", "azt", "ennek", "arra", "erről", "ebben",
    "meg", "már", "csak", "te", "én"
}


# =========================================================
# TOKENIZÁLÁS
# =========================================================

def tokenize(text):
    words = re.findall(
        r"[a-záéíóöőúüű0-9]+",
        text.lower()
    )

    return [
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 2
    ]


# =========================================================
# KÖSZÖNÉS
# =========================================================

def is_greeting(text):
    cleaned = re.sub(
        r"[!?.,:;]+$",
        "",
        text.lower().strip()
    ).strip()

    greetings = {
        "szia",
        "sziaszt",
        "sziasztok",
        "csá",
        "csáó",
        "csao",
        "hello",
        "helló",
        "hali",
        "üdv",
        "jó reggelt",
        "jó estét",
        "jó éjszakát",
        "jó napot"
    }

    return cleaned in greetings


def greeting_response(text):
    cleaned = re.sub(
        r"[!?.,:;]+$",
        "",
        text.lower().strip()
    )

    if "jó reggelt" in cleaned:
        return "Jó reggelt! ☀️"

    if "jó estét" in cleaned:
        return "Jó estét! 🌙"

    if "jó éjszakát" in cleaned:
        return "Jó éjszakát! 🌙"

    if "jó napot" in cleaned:
        return "Jó napot! 😊"

    return "Szia! 😊"


# =========================================================
# PDF KERESÉS
# =========================================================

def search_pdf_knowledge(question, knowledge):
    question_words = set(tokenize(question))

    if not question_words:
        return []

    results = []

    for item in knowledge:
        text = item.get("text", "")

        text_words = item.get("_token_cache")
        if text_words is None:
            text_words = set(tokenize(text))
            item["_token_cache"] = text_words

        common_words = question_words & text_words

        if common_words:
            score = len(common_words)
            results.append((score, item))

    results.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return [
        item
        for score, item in results[:5]
    ]


# =========================================================
# PDF SZÖVEG
# =========================================================

def extract_pdf_text(path):
    reader = PdfReader(path)
    pages = []

    for page in reader.pages:
        try:
            text = page.extract_text()

            if text:
                pages.append(text)

        except Exception:
            pass

    return "\n".join(pages)


# =========================================================
# PDF DARABOLÁS
# =========================================================

def split_text(text, chunk_size=1200):
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            last_period = chunk.rfind(".")

            if last_period > chunk_size * 0.6:
                end = start + last_period + 1
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end

    return chunks


# =========================================================
# MATEK
# =========================================================

def looks_like_math(text):
    lower = text.lower().strip()

    math_words = [
        "mennyi",
        "számold ki",
        "számítsd ki",
        "számol",
        "százalék",
        "egyenlet",
        "négyzetgyök",
        "gyök",
        "négyzet"
    ]

    if any(word in lower for word in math_words):
        return True

    if re.search(
        r"\d+\s*[\+\-\*/×x÷/:]\s*\d+",
        text
    ):
        return True

    if re.search(r"\d+\s*%", text):
        return True

    if "√" in text:
        return True

    return False


def extract_math_expression(text):
    expression = text.strip()

    patterns = [
        r"mennyi\s+",
        r"számold\s+ki\s+",
        r"számítsd\s+ki\s+"
    ]

    for pattern in patterns:
        expression = re.sub(
            pattern,
            "",
            expression,
            flags=re.IGNORECASE
        )

    return expression.strip(" ?.")


def calculate_math(text):
    expression = extract_math_expression(text)

    expression = expression.replace("×", "*")
    expression = expression.replace("x", "*")
    expression = expression.replace("X", "*")
    expression = expression.replace("÷", "/")
    expression = expression.replace("^", "**")

    expression = re.sub(
        r"√\s*(\d+(?:\.\d+)?)",
        r"sqrt(\1)",
        expression
    )

    expression = re.sub(
        r"(?<=\d),(?=\d)",
        ".",
        expression
    )

    percentage_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*%",
        expression
    )

    if percentage_match:
        number = float(percentage_match.group(1))
        return str(number / 100)

    if not re.fullmatch(
        r"[0-9a-zA-Z_+\-*/().\s*]+",
        expression
    ):
        return None

    try:
        result = sp.sympify(
            expression,
            locals={"sqrt": sp.sqrt}
        )

        result = sp.simplify(result)
        return str(result)

    except Exception:
        return None


# =========================================================
# NYELVI TANULÁS
# =========================================================

def add_language_learning(
    memory,
    user_message,
    ai_answer
):
    if not user_message or not ai_answer:
        return memory

    if len(ai_answer.strip()) < 8:
        return memory

    for item in memory:
        if (
            item.get("user", "").strip().lower()
            == user_message.strip().lower()
            and
            item.get("answer", "").strip().lower()
            == ai_answer.strip().lower()
        ):
            return memory

    memory.append({
        "user": user_message.strip(),
        "answer": ai_answer.strip()
    })

    if len(memory) > 100:
        memory = memory[-100:]

    return memory


def build_language_context(memory):
    if not memory:
        return ""

    recent = memory[-8:]

    context = """
NYELVI TANULÁSI MEMÓRIA:

Az alábbi korábbi válaszokból tanulhatsz.
Ezeket nem kell szó szerint lemásolnod.
A céljuk, hogy segítsenek természetes,
helyes magyar nyelven válaszolni.

"""

    for index, item in enumerate(recent, 1):
        context += (
            f"\nPélda {index}:\n"
            f"Felhasználó: {item.get('user', '')}\n"
            f"AstroAI: {item.get('answer', '')}\n"
        )

    return context


# =========================================================
# LOGIN ABLAK
# =========================================================

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master, on_success):
        super().__init__(master)

        self.master = master
        self.on_success = on_success

        self.title("AstroAI – Bejelentkezés")
        self.geometry("500x620")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.protocol(
            "WM_DELETE_WINDOW",
            self.close_app
        )

        self.create_login_ui()

        self.email_entry.focus()

    def close_app(self):
        self.master.destroy()

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def logo(self, subtitle):
        frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        frame.pack(
            fill="x",
            padx=45,
            pady=(45, 20)
        )

        ctk.CTkLabel(
            frame,
            text="✦",
            font=("Segoe UI", 42),
            text_color=ACCENT
        ).pack()

        ctk.CTkLabel(
            frame,
            text="AstroAI",
            font=("Segoe UI", 32, "bold"),
            text_color=TEXT
        ).pack()

        ctk.CTkLabel(
            frame,
            text=subtitle,
            font=("Segoe UI", 12),
            text_color=TEXT_MUTED
        ).pack(pady=(5, 0))

    def make_entry(self, placeholder, show=None):
        return ctk.CTkEntry(
            self,
            height=50,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
            fg_color=PANEL,
            text_color=TEXT,
            placeholder_text=placeholder,
            font=("Segoe UI", 14),
            show=show
        )

    def create_login_ui(self):
        self.clear_window()

        self.logo("Jelentkezz be az AstroAI-ba")

        self.email_entry = self.make_entry("E-mail")
        self.email_entry.pack(
            fill="x",
            padx=45,
            pady=(10, 12)
        )

        self.password_entry = self.make_entry(
            "Jelszó",
            show="*"
        )
        self.password_entry.pack(
            fill="x",
            padx=45,
            pady=12
        )

        self.remember_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(
            self,
            text="Maradjak bejelentkezve",
            variable=self.remember_var,
            text_color=TEXT_MUTED,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI", 12)
        ).pack(
            anchor="w",
            padx=45,
            pady=(2, 18)
        )

        self.login_button = ctk.CTkButton(
            self,
            text="BEJELENTKEZÉS",
            height=50,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI", 14, "bold"),
            command=self.login
        )
        self.login_button.pack(
            fill="x",
            padx=45,
            pady=8
        )

        ctk.CTkButton(
            self,
            text="Nincs még fiókod?  Regisztráció",
            height=42,
            fg_color="transparent",
            hover_color=PANEL_2,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            command=self.create_register_ui
        ).pack(
            fill="x",
            padx=45,
            pady=8
        )

        self.message_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 11),
            text_color="#F87171",
            wraplength=400
        )
        self.message_label.pack(
            padx=45,
            pady=10
        )

    def create_register_ui(self):
        self.clear_window()

        self.logo("Hozd létre a saját AstroAI fiókodat")

        self.email_entry = self.make_entry("E-mail")
        self.email_entry.pack(
            fill="x",
            padx=45,
            pady=7
        )

        self.password_entry = self.make_entry(
            "Jelszó (legalább 6 karakter)",
            show="*"
        )
        self.password_entry.pack(
            fill="x",
            padx=45,
            pady=7
        )

        self.password2_entry = self.make_entry(
            "Jelszó újra",
            show="*"
        )
        self.password2_entry.pack(
            fill="x",
            padx=45,
            pady=7
        )

        self.username_entry = self.make_entry(
            "Felhasználónév"
        )
        self.username_entry.pack(
            fill="x",
            padx=45,
            pady=7
        )

        ctk.CTkLabel(
            self,
            text="Az e-mail a belépéshez kell.\n"
                 "A felhasználónevedet az AstroAI később megjelenítheti.",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
            justify="center"
        ).pack(pady=(8, 12))

        ctk.CTkButton(
            self,
            text="FIÓK LÉTREHOZÁSA",
            height=50,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI", 14, "bold"),
            command=self.register
        ).pack(
            fill="x",
            padx=45,
            pady=8
        )

        ctk.CTkButton(
            self,
            text="← Vissza a bejelentkezéshez",
            height=42,
            fg_color="transparent",
            hover_color=PANEL_2,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            command=self.create_login_ui
        ).pack(
            fill="x",
            padx=45
        )

        self.message_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 11),
            text_color="#F87171",
            wraplength=400
        )
        self.message_label.pack(
            padx=45,
            pady=8
        )

        self.email_entry.focus()

    def login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get()

        if not email or not password:
            self.message_label.configure(
                text="Töltsd ki az e-mail és jelszó mezőt."
            )
            return

        user = authenticate(email, password)

        if not user:
            self.message_label.configure(
                text="Hibás e-mail vagy jelszó."
            )
            return

        if self.remember_var.get():
            save_session(user["email"])
        else:
            clear_session()

        self.on_success(user)
        self.destroy()

    def register(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        password2 = self.password2_entry.get()
        username = self.username_entry.get().strip()

        if password != password2:
            self.message_label.configure(
                text="A két jelszó nem egyezik."
            )
            return

        success, message = create_account(
            email,
            password,
            username
        )

        if not success:
            self.message_label.configure(
                text=message
            )
            return

        user = authenticate(email, password)

        if user:
            save_session(user["email"])
            self.on_success(user)
            self.destroy()


# =========================================================
# ASTROAI APP
# =========================================================

class AstroAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.withdraw()

        self.title("AstroAI")
        self.geometry("1200x760")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.current_user = None
        self.knowledge = []
        self.language_memory = []

        self.thinking = False
        self.thinking_index = 0
        self.streaming_label = None
        self.streaming_frame = None

        self.login_window = None

        self.after(
            100,
            self.start_authentication
        )

    # =====================================================
    # AUTHENTIKÁCIÓ
    # =====================================================

    def start_authentication(self):
        session_email = load_session()

        if session_email:
            users = load_users()
            user = users.get(session_email)

            if user:
                self.login_success(user)
                return

        self.show_login()

    def show_login(self):
        if self.login_window is not None:
            try:
                self.login_window.destroy()
            except Exception:
                pass

        self.login_window = LoginWindow(
            self,
            self.login_success
        )

        self.login_window.grab_set()

    def login_success(self, user):
        self.current_user = user

        email = user["email"]

        self.knowledge = load_knowledge(email)
        self.language_memory = load_language_memory(email)

        self.deiconify()
        self.create_layout()

        self.add_ai_message(
            f"Szia, {user['username']}! 👋\n\n"
            "Én AstroAI vagyok. Kérdezz bármit, "
            "taníts PDF-ekből, vagy használj internetes "
            "keresést a 🌐 jellel."
        )

    def logout(self):
        result = messagebox.askyesno(
            "Kijelentkezés",
            "Biztosan ki szeretnél jelentkezni?"
        )

        if not result:
            return

        clear_session()

        self.current_user = None
        self.knowledge = []
        self.language_memory = []

        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkToplevel):
                try:
                    widget.destroy()
                except Exception:
                    pass

        self.withdraw()
        self.show_login()

    # =====================================================
    # ELRENDEZÉS
    # =====================================================

    def create_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=250,
            corner_radius=0,
            fg_color=SIDEBAR
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.sidebar.grid_propagate(False)

        logo_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent"
        )

        logo_frame.pack(
            fill="x",
            padx=20,
            pady=(25, 15)
        )

        ctk.CTkLabel(
            logo_frame,
            text="✦",
            font=("Segoe UI", 34),
            text_color=ACCENT
        ).pack(side="left")

        title_frame = ctk.CTkFrame(
            logo_frame,
            fg_color="transparent"
        )

        title_frame.pack(
            side="left",
            padx=10
        )

        ctk.CTkLabel(
            title_frame,
            text="AstroAI",
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="PERSONAL AI",
            font=("Segoe UI", 9, "bold"),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        online_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color=PANEL,
            corner_radius=12
        )

        online_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ctk.CTkLabel(
            online_frame,
            text="●  ONLINE",
            font=("Segoe UI", 12, "bold"),
            text_color=SUCCESS
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 2)
        )

        ctk.CTkLabel(
            online_frame,
            text=f"{MODEL} • helyben fut",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 12)
        )

        ctk.CTkLabel(
            self.sidebar,
            text="FIÓK",
            font=("Segoe UI", 10, "bold"),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            padx=20,
            pady=(18, 8)
        )

        account_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color=PANEL,
            corner_radius=12
        )

        account_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 8)
        )

        ctk.CTkLabel(
            account_frame,
            text=f"👤 {self.current_user['username']}",
            font=("Segoe UI", 12, "bold"),
            text_color=TEXT
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 2)
        )

        ctk.CTkLabel(
            account_frame,
            text=self.current_user["email"],
            font=("Segoe UI", 9),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 10)
        )

        ctk.CTkButton(
            account_frame,
            text="Kijelentkezés",
            height=34,
            corner_radius=9,
            fg_color="transparent",
            hover_color=PANEL_2,
            text_color=TEXT_MUTED,
            anchor="w",
            command=self.logout
        ).pack(
            fill="x",
            padx=7,
            pady=(0, 7)
        )

        ctk.CTkLabel(
            self.sidebar,
            text="FUNKCIÓK",
            font=("Segoe UI", 10, "bold"),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            padx=20,
            pady=(18, 8)
        )

        self.sidebar_button(
            "🌐  Internet",
            self.web_search_manual
        )

        self.sidebar_button(
            "📄  PDF tanítása",
            self.select_pdf
        )

        self.sidebar_button(
            "🧮  Matek",
            self.focus_input
        )

        self.sidebar_button(
            "🧠  Tudásbázis",
            self.show_knowledge
        )

        self.sidebar_button(
            "✍️  Nyelvi memória",
            self.show_language_memory
        )

        bottom = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent"
        )

        bottom.pack(
            side="bottom",
            fill="x",
            padx=15,
            pady=20
        )

        ctk.CTkLabel(
            bottom,
            text="AstroAI v4.0",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        ctk.CTkLabel(
            bottom,
            text="Local • Private • Accounts",
            font=("Segoe UI", 9),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        self.main = ctk.CTkFrame(
            self,
            fg_color=BG,
            corner_radius=0
        )

        self.main.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(
            self.main,
            height=75,
            fg_color=BG,
            corner_radius=0
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="AstroAI",
            font=("Segoe UI", 20, "bold"),
            text_color=TEXT
        ).pack(
            side="left",
            padx=25,
            pady=20
        )

        self.header_status = ctk.CTkLabel(
            header,
            text="● Készen állok",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED
        )

        self.header_status.pack(side="left")

        self.chat = ctk.CTkScrollableFrame(
            self.main,
            fg_color=BG,
            corner_radius=0
        )

        self.chat.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=15
        )

        input_container = ctk.CTkFrame(
            self.main,
            fg_color=BG,
            corner_radius=0
        )

        input_container.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(5, 20)
        )

        input_container.grid_columnconfigure(1, weight=1)

        self.pdf_button = ctk.CTkButton(
            input_container,
            text="📄",
            width=50,
            height=50,
            corner_radius=14,
            fg_color=PANEL,
            hover_color=PANEL_2,
            command=self.select_pdf
        )

        self.pdf_button.grid(
            row=0,
            column=0,
            padx=(0, 10)
        )

        self.entry = ctk.CTkEntry(
            input_container,
            height=50,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
            fg_color=PANEL,
            text_color=TEXT,
            placeholder_text="Írj üzenetet...  (🌐 = internet)",
            font=("Segoe UI", 14)
        )

        self.entry.grid(
            row=0,
            column=1,
            sticky="ew"
        )

        self.send_button = ctk.CTkButton(
            input_container,
            text="➤",
            width=55,
            height=50,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI", 20),
            command=self.send_message
        )

        self.send_button.grid(
            row=0,
            column=2,
            padx=(10, 0)
        )

        self.entry.bind(
            "<Return>",
            lambda event: self.send_message()
        )

        self.status_label = ctk.CTkLabel(
            input_container,
            text="",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED
        )

        self.status_label.grid(
            row=1,
            column=1,
            sticky="w",
            pady=(4, 0)
        )

    # =====================================================
    # OLDALSÁV
    # =====================================================

    def sidebar_button(self, text, command):
        button = ctk.CTkButton(
            self.sidebar,
            text=text,
            anchor="w",
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color=PANEL_2,
            text_color=TEXT,
            font=("Segoe UI", 12),
            command=command
        )

        button.pack(
            fill="x",
            padx=10,
            pady=2
        )

    # =====================================================
    # ÜZENETEK
    # =====================================================

    def add_user_message(self, message):
        frame = ctk.CTkFrame(
            self.chat,
            fg_color="transparent"
        )

        frame.pack(
            fill="x",
            padx=10,
            pady=8
        )

        bubble = ctk.CTkFrame(
            frame,
            fg_color=USER_BUBBLE,
            corner_radius=16
        )

        bubble.pack(
            side="right",
            padx=10
        )

        ctk.CTkLabel(
            bubble,
            text=message,
            font=("Segoe UI", 14),
            text_color="white",
            wraplength=650,
            justify="left"
        ).pack(
            padx=16,
            pady=12
        )

    def add_ai_message(self, message):
        frame = ctk.CTkFrame(
            self.chat,
            fg_color="transparent"
        )

        frame.pack(
            fill="x",
            padx=10,
            pady=8
        )

        ctk.CTkLabel(
            frame,
            text="✦",
            font=("Segoe UI", 20),
            text_color=ACCENT
        ).pack(
            side="left",
            anchor="n",
            padx=(5, 8)
        )

        bubble = ctk.CTkFrame(
            frame,
            fg_color=AI_BUBBLE,
            border_width=1,
            border_color=BORDER,
            corner_radius=16
        )

        bubble.pack(side="left")

        ctk.CTkLabel(
            bubble,
            text=message,
            font=("Segoe UI", 14),
            text_color=TEXT,
            wraplength=700,
            justify="left"
        ).pack(
            padx=16,
            pady=12
        )

        self.after(50, self.scroll_chat)

    def start_ai_stream_message(self):
        frame = ctk.CTkFrame(
            self.chat,
            fg_color="transparent"
        )
        frame.pack(
            fill="x",
            padx=10,
            pady=8
        )

        ctk.CTkLabel(
            frame,
            text="✦",
            font=("Segoe UI", 20),
            text_color=ACCENT
        ).pack(
            side="left",
            anchor="n",
            padx=(5, 8)
        )

        bubble = ctk.CTkFrame(
            frame,
            fg_color=AI_BUBBLE,
            border_width=1,
            border_color=BORDER,
            corner_radius=16
        )
        bubble.pack(side="left")

        label = ctk.CTkLabel(
            bubble,
            text="",
            font=("Segoe UI", 14),
            text_color=TEXT,
            wraplength=700,
            justify="left"
        )
        label.pack(
            padx=16,
            pady=12
        )

        self.streaming_frame = frame
        self.streaming_label = label
        self.after(0, self.scroll_chat)

    def update_ai_stream_message(self, text):
        if self.streaming_label is not None:
            self.streaming_label.configure(text=text)
            self.after(0, self.scroll_chat)

    def finish_ai_stream_message(self):
        self.streaming_label = None
        self.streaming_frame = None

    def scroll_chat(self):
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # =====================================================
    # GONDOLKODÁS
    # =====================================================

    def start_thinking(self):
        self.thinking = True
        self.thinking_index = 0

        self.header_status.configure(
            text="● Gondolkodom...",
            text_color=ACCENT
        )

        self.animate_thinking()

    def animate_thinking(self):
        if not self.thinking:
            return

        dots = [".", "..", "..."]

        self.status_label.configure(
            text="AstroAI gondolkodik "
            + dots[self.thinking_index]
        )

        self.thinking_index = (
            self.thinking_index + 1
        ) % 3

        self.after(400, self.animate_thinking)

    def stop_thinking(self):
        self.thinking = False

        self.status_label.configure(text="")

        self.header_status.configure(
            text="● Készen állok",
            text_color=TEXT_MUTED
        )

    # =====================================================
    # INPUT
    # =====================================================

    def focus_input(self):
        self.entry.focus()

    def set_controls(self, enabled):
        state = "normal" if enabled else "disabled"

        self.entry.configure(state=state)
        self.send_button.configure(state=state)
        self.pdf_button.configure(state=state)

        if enabled:
            self.entry.focus()

    # =====================================================
    # ÜZENET
    # =====================================================

    def send_message(self):
        message = self.entry.get().strip()

        if not message:
            return

        force_web = "🌐" in message

        message = message.replace("🌐", "").strip()

        if not message:
            return

        self.entry.delete(0, "end")

        self.add_user_message(message)

        self.set_controls(False)
        self.start_thinking()

        threading.Thread(
            target=self.ask_ai,
            args=(message, force_web),
            daemon=True
        ).start()

    # =====================================================
    # AI
    # =====================================================

    def ask_ai(self, message, force_web=False):
        try:
            if is_greeting(message):
                answer = greeting_response(message)

                self.after(
                    0,
                    self.ai_finished,
                    answer,
                    message
                )
                return

            if looks_like_math(message):
                result = calculate_math(message)

                if result is not None:
                    answer = "Az eredmény: " + result

                    self.after(
                        0,
                        self.ai_finished,
                        answer,
                        message
                    )
                    return

            web_context = ""
            web_sources = []

            if force_web:
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="🌐 Internet keresése..."
                    )
                )

                results = search_web(
                    message,
                    max_results=5
                )

                for result in results:
                    title = result.get("title", "")
                    body = result.get("body", "")
                    url = result.get("url", "")

                    web_context += (
                        f"\nCím: {title}\n"
                        f"Tartalom: {body}\n"
                        f"Forrás: {url}\n"
                    )

                    if url and url not in web_sources:
                        web_sources.append(url)

            relevant = search_pdf_knowledge(
                message,
                self.knowledge
            )

            pdf_context = ""

            if relevant:
                pdf_context = "\n\nPDF-TUDÁSBÁZIS:\n"

                for item in relevant:
                    pdf_context += (
                        "\nForrás: "
                        + item.get("source", "")
                        + "\n"
                        + item.get("text", "")
                        + "\n"
                    )

            language_context = build_language_context(
                self.language_memory
            )

            system_prompt = """
Te AstroAI vagy.

Egy intelligens, magyar nyelvű,
helyben futó személyi AI-asszisztens vagy.

MAGYAR NYELV:

- Mindig természetes magyarul válaszolj.
- Használj helyes magyar nyelvtant.
- Használd helyesen a magyar ékezeteket.
- Használj természetes magyar szórendet.
- Ne fordíts szó szerint angol mondatokat.
- Ne használj gépies megfogalmazást.
- Ha a felhasználó lazán vagy szlengesen ír,
  válaszolhatsz természetes, közvetlen stílusban.
- Ne javítsd ki automatikusan a felhasználó
  helyesírását, hacsak nem kéri.

SZEMÉLYISÉG:

- Nyugodt.
- Intelligens.
- Közvetlen.
- Barátságos.
- Néha humoros.
- Nem vagy túlzottan lelkes.
- Nem köszönsz minden válaszban.
- Nem ismétled magad.
- Rövid kérdésre röviden válaszolsz.
- Összetett kérdésre részletesebben válaszolsz.

IDENTITÁS:

A neved AstroAI.

Ha megkérdezik, ki vagy:
"AstroAI vagyok."

Ne mondd azt, hogy Qwen vagy.

INTERNET:

Ha internetes információt kapsz,
használd fel a válaszban.

Az internetes találatokat adatforrásként kezeld.

Ne találj ki olyan információt,
amely nem szerepel a kapott adatokban.

PDF:

A PDF-tudásbázisból kapott információt
használd fel, ha releváns.

Ne találj ki PDF-ből származó információt.

NYELVI TANULÁS:

A korábbi példákból tanulj természetes
magyar megfogalmazási mintákat.

Ne másold őket szó szerint,
ha az nem indokolt.

A helyes magyar nyelvtan és természetes
megfogalmazás fontosabb, mint a korábbi
válaszok szó szerinti követése.

FONTOS:

A felhasználó kérdésének jelentését
próbáld megérteni, ne csak kulcsszavakra
reagálj.
"""

            self.after(0, self.start_ai_stream_message)

            response = ollama.chat(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content":
                            system_prompt
                            + language_context
                            + pdf_context
                            + web_context
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                options={
                    "temperature": 0.3,
                    "top_p": 0.9
                },
                keep_alive="10m",
                stream=True
            )

            answer_parts = []

            for chunk in response:
                chunk_text = chunk.get("message", {}).get("content", "")
                if chunk_text:
                    answer_parts.append(chunk_text)
                    self.after(
                        0,
                        self.update_ai_stream_message,
                        "".join(answer_parts)
                    )

            answer = "".join(answer_parts)

            if force_web and web_sources:
                answer += "\n\nForrások:\n"

                for source in web_sources:
                    answer += "🔗 " + source + "\n"

            self.language_memory = add_language_learning(
                self.language_memory,
                message,
                answer
            )

            save_language_memory(
                self.current_user["email"],
                self.language_memory
            )

        except Exception as e:
            self.after(0, self.finish_ai_stream_message)

            answer = (
                "Hiba történt:\n"
                + str(e)
                + "\n\n"
                "Ellenőrizd, hogy az Ollama fut-e."
            )

        self.after(
            0,
            self.ai_finished,
            answer,
            message
        )

    # =====================================================
    # AI KÉSZ
    # =====================================================

    def ai_finished(self, answer, user_message=""):
        self.stop_thinking()

        if self.streaming_label is not None:
            self.update_ai_stream_message(answer)
            self.finish_ai_stream_message()
        else:
            self.add_ai_message(answer)

        self.set_controls(True)

    # =====================================================
    # PDF
    # =====================================================

    def select_pdf(self):
        path = filedialog.askopenfilename(
            title="PDF kiválasztása",
            filetypes=[
                ("PDF fájl", "*.pdf")
            ]
        )

        if not path:
            return

        self.set_controls(False)

        self.status_label.configure(
            text="📄 PDF feldolgozása..."
        )

        threading.Thread(
            target=self.process_pdf,
            args=(path,),
            daemon=True
        ).start()

    def process_pdf(self, path):
        try:
            text = extract_pdf_text(path)

            if not text.strip():
                self.after(
                    0,
                    self.pdf_finished,
                    "Nem sikerült szöveget kiolvasni a PDF-ből."
                )
                return

            chunks = split_text(text)
            filename = os.path.basename(path)
            added = 0

            for chunk in chunks:
                self.knowledge.append({
                    "source": filename,
                    "text": chunk
                })
                added += 1

            save_knowledge(
                self.current_user["email"],
                self.knowledge
            )

            self.after(
                0,
                self.pdf_finished,
                f"Sikeresen megtanultam a PDF-et! ({added} rész)"
            )

        except Exception as e:
            self.after(
                0,
                self.pdf_finished,
                "Hiba a PDF feldolgozásakor:\n" + str(e)
            )

    def pdf_finished(self, message):
        self.stop_thinking()
        self.add_ai_message(message)
        self.set_controls(True)

    # =====================================================
    # INTERNET
    # =====================================================

    def web_search_manual(self):
        self.entry.focus()

        current = self.entry.get().strip()

        if current:
            if "🌐" not in current:
                self.entry.insert(0, "🌐 ")

            self.send_message()
        else:
            self.entry.insert(0, "🌐 ")
            self.entry.focus()

    # =====================================================
    # TUDÁSBÁZIS
    # =====================================================

    def show_knowledge(self):
        window = ctk.CTkToplevel(self)

        window.title("AstroAI Tudásbázis")
        window.geometry("700x600")
        window.configure(fg_color=BG)

        ctk.CTkLabel(
            window,
            text="🧠 AstroAI Tudásbázis",
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT
        ).pack(
            anchor="w",
            padx=25,
            pady=(25, 5)
        )

        ctk.CTkLabel(
            window,
            text=f"{len(self.knowledge)} megtanult PDF-rész",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            padx=25,
            pady=(0, 15)
        )

        box = ctk.CTkTextbox(
            window,
            font=("Consolas", 12),
            fg_color=PANEL,
            text_color=TEXT
        )

        box.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(0, 25)
        )

        if not self.knowledge:
            box.insert(
                "end",
                "A tudásbázis jelenleg üres."
            )
        else:
            for index, item in enumerate(
                self.knowledge,
                1
            ):
                box.insert(
                    "end",
                    f"[{index}] "
                    + item.get(
                        "source",
                        "Ismeretlen"
                    )
                    + "\n\n"
                )

                box.insert(
                    "end",
                    item.get(
                        "text",
                        ""
                    )
                    + "\n\n"
                )

                box.insert(
                    "end",
                    "────────────────────────\n\n"
                )

        box.configure(state="disabled")

    # =====================================================
    # NYELVI MEMÓRIA
    # =====================================================

    def show_language_memory(self):
        window = ctk.CTkToplevel(self)

        window.title("AstroAI – Nyelvi memória")
        window.geometry("800x650")
        window.configure(fg_color=BG)

        header = ctk.CTkFrame(
            window,
            fg_color="transparent"
        )

        header.pack(
            fill="x",
            padx=25,
            pady=(25, 10)
        )

        ctk.CTkLabel(
            header,
            text="✍️ Nyelvi memória",
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text=(
                f"{len(self.language_memory)} "
                "elmentett tanulási példa"
            ),
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED
        ).pack(
            anchor="w",
            pady=(4, 0)
        )

        box = ctk.CTkTextbox(
            window,
            font=("Segoe UI", 12),
            fg_color=PANEL,
            text_color=TEXT
        )

        box.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(0, 15)
        )

        if not self.language_memory:
            box.insert(
                "end",
                "A nyelvi memória még üres."
            )
        else:
            for index, item in enumerate(
                self.language_memory,
                1
            ):
                user_text = item.get("user", "")
                answer_text = item.get("answer", "")

                box.insert(
                    "end",
                    f"[{index}]\n"
                )

                box.insert(
                    "end",
                    f"Felhasználó: {user_text}\n"
                )

                box.insert(
                    "end",
                    f"AstroAI: {answer_text}\n\n"
                )

                box.insert(
                    "end",
                    "────────────────────────\n\n"
                )

        box.configure(state="disabled")

        def clear_memory():
            result = messagebox.askyesno(
                "Nyelvi memória törlése",
                "Biztosan törlöd az összes nyelvi tanulási példát?"
            )

            if not result:
                return

            self.language_memory = []

            save_language_memory(
                self.current_user["email"],
                self.language_memory
            )

            window.destroy()

            self.add_ai_message(
                "A nyelvi memóriát töröltem. 🧠"
            )

        ctk.CTkButton(
            window,
            text="🗑 Nyelvi memória törlése",
            height=42,
            corner_radius=12,
            fg_color=DANGER,
            hover_color=DANGER_HOVER,
            command=clear_memory
        ).pack(
            fill="x",
            padx=25,
            pady=(0, 25)
        )


# =========================================================
# INDÍTÁS
# =========================================================

if __name__ == "__main__":
    app = AstroAIApp()
    app.mainloop()
