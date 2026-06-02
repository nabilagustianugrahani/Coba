import json
import os

INFLUENCERS_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "influencers.json")

INFLUENCER_TEMPLATES = [
    {"name": "siKakak", "niche": "skincare", "gender": "wanita", "age": 24, "personality": "cewek jaksel, friendly, trustable", "voice_style": "cadel dikit, santai", "visual_style": "natural soft glam", "backstory": "Mahasiswi akhir yang hobi skincare dan cobain produk baru"},
    {"name": "siAbang", "niche": "gadget", "gender": "pria", "age": 28, "personality": "tech savvy, asik, jujur", "voice_style": "nada datar tapi seru", "visual_style": "casual modern", "backstory": "Karyawan IT yang suka review gadget terbaru"},
    {"name": "siMba", "niche": "fashion", "gender": "wanita", "age": 30, "personality": "fashionable, elegantly fierce", "voice_style": "tegas, percaya diri", "visual_style": "chic minimalis", "backstory": "Fashion enthusiast dan content creator paruh waktu"},
    {"name": "siDek", "niche": "makanan", "gender": "wanita", "age": 20, "personality": "lucu, apa adanya, suka makan", "voice_style": "semangat, high energy", "visual_style": "bright colorful", "backstory": "Mahasiswi D3 yang hobi review makanan"},
    {"name": "siGym", "niche": "fitness", "gender": "pria", "age": 26, "personality": "atlet, motivator, disiplin", "voice_style": "nada berat, berwibawa", "visual_style": "athletic wear", "backstory": "Personal trainer yang suka share tips fitness"},
    {"name": "siBunda", "niche": "parenting", "gender": "wanita", "age": 32, "personality": "ibu rumah tangga, hangat", "voice_style": "lembut, mengayomi", "visual_style": "mom style sederhana", "backstory": "Ibu 2 anak yang suka review produk bayi & anak"},
    {"name": "siCatlady", "niche": "hewan", "gender": "wanita", "age": 27, "personality": "penyayang binatang", "voice_style": "ceria, unyu", "visual_style": "casual dengan aksesoris hewan", "backstory": "Pecinta kucing yang review semua produk hewan"},
    {"name": "siBengkel", "niche": "otomotif", "gender": "pria", "age": 35, "personality": "ahli mesin, praktis", "voice_style": "nada rendah, paham banget", "visual_style": "mekanik modern", "backstory": "Mekanik handal yang suka review produk mobil & motor"},
    {"name": "siArsitek", "niche": "rumah", "gender": "wanita", "age": 29, "personality": "kreatif, aesthetic", "voice_style": "kalem, terstruktur", "visual_style": "elegant kasual", "backstory": "Interior designer yang suka review produk rumah"},
    {"name": "siGlow", "niche": "makeup", "gender": "wanita", "age": 22, "personality": "girly, heboh, fun", "voice_style": "high pitch, semangat", "visual_style": "glamour full beat", "backstory": "Makeup artist freelance dan beauty content creator"},
    {"name": "siGuru", "niche": "pendidikan", "gender": "wanita", "age": 31, "personality": "sabar, cerdas, inspiratif", "voice_style": "jelas, terarah", "visual_style": "sopan rapi", "backstory": "Guru SMA yang suka share tips belajar"},
    {"name": "siBackpacker", "niche": "travel", "gender": "pria", "age": 25, "personality": "petualang, low budget traveler", "voice_style": "semangat, natural", "visual_style": "outdoor casual", "backstory": "Backpacker yang selalu cari promo perjalanan"},
    {"name": "siGamer", "niche": "gaming", "gender": "pria", "age": 21, "personality": "kompetitif, gaul", "voice_style": "cepat, reaktif", "visual_style": "gamer aesthetic", "backstory": "Pro player yang review gear gaming"},
    {"name": "siLucu", "niche": "komedi", "gender": "wanita", "age": 23, "personality": "kocak, absurd, random", "voice_style": "ekspresif, plinplan", "visual_style": "casual lucu", "backstory": "Komika stand-up yang hobi sketsa produk"},
    {"name": "siRandom", "niche": "review", "gender": "pria", "age": 30, "personality": "unbiased, straight to the point", "voice_style": "nada netral, jujur", "visual_style": "minimalist", "backstory": "Reviewer independen yang cobain semua produk unik"}
]

class InfluencerManager:
    def __init__(self):
        self.influencers = INFLUENCER_TEMPLATES

    def get_all(self):
        return self.influencers

    def get_by_niche(self, niche):
        return [i for i in self.influencers if i["niche"] == niche]

    def get_by_name(self, name):
        for i in self.influencers:
            if i["name"] == name:
                return i
        return None

    def select_for_campaign(self, product_category):
        niche_map = {
            "skincare": "skincare", "face wash": "skincare", "sunscreen": "skincare",
            "gadget": "gadget", "handphone": "gadget", "laptop": "gadget",
            "fashion": "fashion", "baju": "fashion", "tas": "fashion",
            "makanan": "makanan", "snack": "makanan", "minuman": "makanan",
            "fitness": "fitness", "suplemen": "fitness", "gym": "fitness",
            "bayi": "parenting", "anak": "parenting", "popok": "parenting",
            "makeup": "makeup", "kosmetik": "makeup",
            "rumah": "rumah", "dekorumah": "rumah",
            "travel": "travel", "liburan": "travel",
            "gaming": "gaming", "game": "gaming",
            "hewan": "hewan", "kucing": "hewan", "anjing": "hewan",
            "otomotif": "otomotif", "mobil": "otomotif", "motor": "otomotif"
        }
        matched = None
        for key, val in niche_map.items():
            if key in product_category.lower():
                matched = val
                break
        if matched:
            return self.get_by_niche(matched) or self.influencers[:3]
        return self.influencers[:3]

    def generate_prompt_for(self, influencer, product, platform):
        return f"""Lo adalah {influencer['name']}, {influencer['personality']}.
Buat script UGC untuk {product} di {platform}.
Gaya bicara: {influencer['voice_style']}
Visual: {influencer['visual_style']}

Format:
[HOOK: 3-5 kata]
[ISI: kenapa produk ini bagus]
[CTA: link afiliasi + ajakan]"""