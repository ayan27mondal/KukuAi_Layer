"""Cheap, offline language detection for English / Hindi / Hinglish / Bengali / Assamese."""
import re

HINGLISH_WORDS = set("""mera meri mere hai hain nahi nahin nhi kya kyun kaise kaun kab kitna kitne aap tum main mai hum ko ka ki ke se par pe ne
 wapas vapas paisa paise rupaye rupay deposit makaan malik maalik kiraya kiraydar dukaan dukandar company salary tankhwah tankha mahine
 mahina saal din dekar diya diye nahi chahiye chahta chahti karna karo kar raha rahi rahe ho tha thi the abhi bahut lekin aur ya toh to
 bol bola bolta bata batao batana likh likho banao bana mil mila mili milega milegi dena de do vakeel dhamki case notice
 contract breach agreement property dispute recovery injunction partition declaration civil suit damages plaintiff defendant decree execution mutation title possession kabza batwara wapas lena harjana tankhwah""".split())

def detect_language(text, default="en"):
    t = text or ""
    dev = len(re.findall(r"[\u0900-\u097F]", t))
    ben = len(re.findall(r"[\u0980-\u09FF]", t))
    letters = len(re.findall(r"\w", t)) or 1
    if ben / letters > 0.3:
        return "as" if re.search(r"[ৰৱ]", t) else "bn"
    if dev / letters > 0.3:
        return "hi"
    words = re.findall(r"[a-z]+", t.lower())
    if words:
        hits = sum(1 for w in words if w in HINGLISH_WORDS)
        if hits >= 2 and hits / len(words) >= 0.15:
            return "hinglish"
    return "en" if re.search(r"[A-Za-z]", t) else default
