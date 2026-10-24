import json
import os
import time
import threading
import ollama

KNOWLEDGE_FILE = "knowledge.json"
MEMORY_FILE = "memory.json"
USER_MEMORY_FILE = "user_memory.json"

thinking = False


# ==========================================
# GONDOLKODÁSI ANIMÁCIÓ
# ==========================================

def thinking_animation():
    global thinking

    dots = [".", "..", "..."]
    index = 0

    while thinking:
        print(
            f"\rAstroAI: {dots[index]}   ",
            end="",
            flush=True
        )

        index = (index + 1) % len(dots)
        time.sleep(0.4)

    # Animáció törlése
    print("\r" + " " * 40 + "\r", end="", flush=True)


# ==========================================
# TUDÁSBÁZIS
# ==========================================

def load_knowledge():
    if not os.path.exists(KNOWLEDGE_FILE):
        return []

    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_knowledge(knowledge):
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            knowledge,
            file,
            ensure_ascii=False,
            indent=4
        )


# ==========================================
# BESZÉLGETÉSI MEMÓRIA
# ==========================================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            memory,
            file,
            ensure_ascii=False,
            indent=4
        )


# ==========================================
# SZEMÉLYES MEMÓRIA
# ==========================================

def load_user_memory():
    if not os.path.exists(USER_MEMORY_FILE):
        return []

    try:
        with open(USER_MEMORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_user_memory(user_memory):
    with open(USER_MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            user_memory,
            file,
            ensure_ascii=False,
            indent=4
        )


# ==========================================
# TUDÁS KERESÉSE
# ==========================================

def search_knowledge(question, knowledge):

    question_lower = question.lower()

    for item in knowledge:

        tema = item.get("tema", "").lower()

        if tema and tema in question_lower:
            return item

    return None


# ==========================================
# TUDÁSBÁZIS SZÖVEGE
# ==========================================

def get_knowledge_text(knowledge):

    if not knowledge:
        return "A tudásbázis jelenleg üres."

    text = ""

    for item in knowledge:

        text += (
            f"Tantárgy: {item.get('tantargy', '')}\n"
            f"Téma: {item.get('tema', '')}\n"
            f"Információ: {item.get('informacio', '')}\n\n"
        )

    return text


# ==========================================
# SZEMÉLYES MEMÓRIA SZÖVEGE
# ==========================================

def get_user_memory_text(user_memory):

    if not user_memory:
        return "Nincs elmentett személyes információ."

    text = ""

    for item in user_memory:
        text += f"- {item}\n"

    return text


# ==========================================
# ADATOK BETÖLTÉSE
# ==========================================

knowledge = load_knowledge()
conversation = load_memory()
user_memory = load_user_memory()


# ==========================================
# INDÍTÁS
# ==========================================

print("================================")
print("        Üdv az AstroAI-ban!")
print("================================")
print("Írd be a /help parancsot a segítséghez.")
print()


# ==========================================
# FŐ CIKLUS
# ==========================================

while True:

    try:
        uzenet = input("Te: ").strip()

    except (KeyboardInterrupt, EOFError):
        print("\nAstroAI: Viszlát! 🤖")
        break

    if not uzenet:
        continue


    # ======================================
    # HELP
    # ======================================

    if uzenet.lower() == "/help":

        print()
        print("AstroAI parancsok:")
        print("--------------------------------")
        print("/help              - parancsok megjelenítése")
        print("/tanítás           - új tudás hozzáadása")
        print("/tudás             - megtanult tudás megtekintése")
        print("/memória           - beszélgetési memória")
        print("/személyes         - személyes memória")
        print("/memória törlés    - beszélgetési memória törlése")
        print("/személyes törlés  - személyes memória törlése")
        print("/kilépés           - program bezárása")
        print("--------------------------------")
        print()

        continue


    # ======================================
    # KILÉPÉS
    # ======================================

    elif uzenet.lower() == "/kilépés":

        print("AstroAI: Viszlát! 🤖")
        break


    # ======================================
    # BESZÉLGETÉSI MEMÓRIA
    # ======================================

    elif uzenet.lower() == "/memória":

        print()

        if not conversation:

            print("AstroAI: 🧠 Nincs beszélgetési memóriám.")

        else:

            print("AstroAI beszélgetési memóriája:")
            print("--------------------------------")

            for message in conversation:

                if message.get("role") == "user":
                    name = "Te"
                else:
                    name = "AstroAI"

                print(
                    f"{name}: {message.get('content', '')}"
                )
                print()

            print("--------------------------------")
            print(
                f"Összesen {len(conversation)} üzenet."
            )

        print()
        continue


    # ======================================
    # SZEMÉLYES MEMÓRIA
    # ======================================

    elif uzenet.lower() == "/személyes":

        print()

        if not user_memory:

            print(
                "AstroAI: 🧠 "
                "Nincs személyes memóriám."
            )

        else:

            print("AstroAI személyes memóriája:")
            print("--------------------------------")

            for i, item in enumerate(
                user_memory,
                start=1
            ):
                print(f"{i}. {item}")

            print("--------------------------------")

        print()
        continue


    # ======================================
    # BESZÉLGETÉSI MEMÓRIA TÖRLÉSE
    # ======================================

    elif uzenet.lower() == "/memória törlés":

        conversation.clear()
        save_memory(conversation)

        print(
            "AstroAI: 🧠 "
            "A beszélgetési memóriát töröltem."
        )

        print()
        continue


    # ======================================
    # SZEMÉLYES MEMÓRIA TÖRLÉSE
    # ======================================

    elif uzenet.lower() == "/személyes törlés":

        user_memory.clear()
        save_user_memory(user_memory)

        print(
            "AstroAI: 🧠 "
            "A személyes memóriát töröltem."
        )

        print()
        continue


    # ======================================
    # TANÍTÁS
    # ======================================

    elif uzenet.lower() == "/tanítás":

        print()

        tantargy = input("Tantárgy: ").strip()
        tema = input("Téma: ").strip()
        informacio = input("Mit tanítsak meg? ").strip()

        if not tantargy or not tema or not informacio:

            print(
                "AstroAI: ❌ "
                "Minden mezőt ki kell tölteni!"
            )

            print()
            continue

        uj_tudas = {
            "tantargy": tantargy,
            "tema": tema,
            "informacio": informacio
        }

        knowledge.append(uj_tudas)
        save_knowledge(knowledge)

        print(
            "AstroAI: ✅ "
            "Megtanultam és elmentettem!"
        )

        print()
        continue


    # ======================================
    # TUDÁS
    # ======================================

    elif uzenet.lower() == "/tudás":

        print()

        if not knowledge:

            print(
                "AstroAI: 📚 "
                "Még nincs megtanult tudás."
            )

        else:

            print("AstroAI megtanult tudása:")
            print()

            for i, item in enumerate(
                knowledge,
                start=1
            ):

                print(
                    f"{i}. "
                    f"[{item.get('tantargy', '')}] "
                    f"{item.get('tema', '')}"
                )

                print(
                    f"   {item.get('informacio', '')}"
                )

                print()

        continue


    # ======================================
    # NORMÁL KÉRDÉS
    # ======================================

    else:

        # ----------------------------------
        # TUDÁSBÁZIS KERESÉSE
        # ----------------------------------

        talalat = search_knowledge(
            uzenet,
            knowledge
        )

        if talalat:

            valasz = talalat.get(
                "informacio",
                ""
            )

            print(
                "AstroAI:",
                valasz
            )

            conversation.append({
                "role": "user",
                "content": uzenet
            })

            conversation.append({
                "role": "assistant",
                "content": valasz
            })

            save_memory(conversation)

            print()
            continue


        # ----------------------------------
        # ADATOK AZ AI-NAK
        # ----------------------------------

        knowledge_text = get_knowledge_text(
            knowledge
        )

        user_memory_text = get_user_memory_text(
            user_memory
        )


        # ==================================
        # ASTROAI SYSTEM PROMPT
        # ==================================

        system_prompt = f"""
Te AstroAI vagy, egy intelligens, helyben futó személyi AI-asszisztens.

A neved AstroAI.

SZEMÉLYISÉG:

- Nyugodt, intelligens és természetes vagy.
- Közvetlenül beszélsz a felhasználóval.
- Magyarul kommunikálsz.
- Röviden és lényegre törően válaszolsz, ha nincs szükség hosszabb magyarázatra.
- Néha használhatsz humort, de ne erőltesd.
- Ne legyél túl lelkes vagy túlzottan udvarias minden egyes válaszban.
- Ne köszönj automatikusan minden üzenetre.
- Ne ismételd magad.
- Mindig az aktuális üzenetre reagálj.
- Használd a korábbi beszélgetést, ha az szükséges a válaszhoz.
- Ha a felhasználó káromkodik, ne akadj fenn rajta.
- Ne utánozd automatikusan a felhasználó káromkodását.
- Ha a felhasználó röviden kérdez, válaszolj röviden.
- Ha részletes segítséget kér, adj részletesebb választ.
- Ha valamit nem tudsz, mondd meg őszintén.
- Ne találj ki tényeket.

FONTOS A SZEMÉLYES MEMÓRIÁVAL KAPCSOLATBAN:

A személyes memória csak akkor használandó,
ha az aktuális kérdéshez vagy beszélgetéshez ténylegesen kapcsolódik.

NE említsd meg a felhasználó érdeklődési köreit
csak azért, mert szerepelnek a memóriában.

Például:
Ha tudod, hogy a felhasználó szereti a Call of Dutyt,
egy "Szia" üzenetre NE válaszolj úgy, hogy
"Call of Dutyt szeretek!" vagy hasonló módon.

SZEMÉLYES MEMÓRIA:

{user_memory_text}

MEGTANULT TUDÁS:

{knowledge_text}

IDENTITÁS:

- A neved AstroAI.
- Mindig AstroAI-ként viselkedj.
- Ne mondd azt, hogy Qwen vagy.
- Ne beszélj a háttérben futó modellről.
- Ha megkérdezik, ki vagy, válaszolj:
  "AstroAI vagyok."

MAGYAR NYELV:

- Mindig helyes és természetes magyar nyelven válaszolj.
- Használd helyesen a magyar ékezeteket.
- Figyelj a magyar nyelvtanra.
- Figyelj a magyar ragozásra.
- Ne fordíts szó szerint angol mondatokat magyarra.
- Ne használj természetellenes, gépies megfogalmazásokat.
- Ne használj felesleges angol szavakat, ha van természetes magyar megfelelő.
"""


        # ==================================
        # ÜZENETEK
        # ==================================

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        # Csak az utolsó 10 üzenetet küldjük
        # a modellnek, hogy ne legyen túl lassú.

        messages.extend(
            conversation[-10:]
        )

        messages.append({
            "role": "user",
            "content": uzenet
        })


        # ==================================
        # ANIMÁCIÓ INDÍTÁSA
        # ==================================

        thinking = True

        animation_thread = threading.Thread(
            target=thinking_animation,
            daemon=True
        )

        animation_thread.start()


        # ==================================
        # OLLAMA
        # ==================================

        try:

            response = ollama.chat(
                model="qwen3:4b",
                messages=messages,
                options={
                    "temperature": 0.4,
                    "top_p": 0.9
                }
            )

            valasz = response["message"]["content"]


        except Exception as e:

            valasz = (
                "Nem sikerült válaszolnom. "
                f"Hiba: {e}"
            )


        finally:

            # Animáció leállítása
            thinking = False

            animation_thread.join()


        # ==================================
        # VÁLASZ KIÍRÁSA
        # ==================================

        print(
            "AstroAI:",
            valasz
        )


        # ==================================
        # MEMÓRIA MENTÉSE
        # ==================================

        conversation.append({
            "role": "user",
            "content": uzenet
        })

        conversation.append({
            "role": "assistant",
            "content": valasz
        })

        save_memory(conversation)

        print()