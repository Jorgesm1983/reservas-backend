import pyshorteners

def acortar_url_para_whatsapp(url_larga):
    s = pyshorteners.Shortener()
    return s.tinyurl.short(url_larga)