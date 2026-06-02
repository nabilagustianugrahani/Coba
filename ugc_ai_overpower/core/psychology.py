import json

PSYCHOLOGY_FRAMEWORKS = {
    "loss_aversion": {
        "name": "Loss Aversion",
        "principle": "Orang lebih takut kehilangan daripada senang dapet",
        "triggers": ["Stok tinggal", "Promo berakhir", "Jangan sampe kehabisan", "Limited edition"],
        "best_for": ["skincare", "fashion", "gadget", "makeup"]
    },
    "social_proof": {
        "name": "Social Proof",
        "principle": "Orang percaya sama yang dipake orang lain",
        "triggers": ["Udah 10.000 orang pake", "Viral di TikTok", "Best seller", "FYP"],
        "best_for": ["semua"]
    },
    "authority": {
        "name": "Authority Effect",
        "principle": "Orang percaya sama yang dianggap expert",
        "triggers": ["Rekomendasi dokter", "Top 1", "Award winner"],
        "best_for": ["skincare", "makeup", "kesehatan", "fitness"]
    },
    "fear": {
        "name": "Fear",
        "principle": "Takut = motivasi beli terkuat",
        "triggers": ["Kalo gak pake sekarang", "Bahaya kalo diabaikan", "Lo bakal nyesel"],
        "best_for": ["skincare", "kesehatan", "fitness", "asuransi"]
    },
    "curiosity": {
        "name": "Curiosity Gap",
        "principle": "Orang gamau ketinggalan informasi",
        "triggers": ["Rahasia", "Gak semua orang tau", "Yang jarang dibahas"],
        "best_for": ["semua"]
    },
    "reciprocity": {
        "name": "Reciprocity",
        "principle": "Orang merasa wajib balas budi",
        "triggers": ["FREE", "GRATIS", "Download", "Ebook gratis"],
        "best_for": ["pendidikan", "gadget", "fashion"]
    },
    "scarcity": {
        "name": "Scarcity",
        "principle": "Barang terbatas = makin berharga",
        "triggers": ["Limited", "Pre-order", "Cuma", "Exclusive"],
        "best_for": ["fashion", "gadget", "makeup"]
    },
    "aspiration": {
        "name": "Aspiration",
        "principle": "Orang beli versi ideal dari diri mereka",
        "triggers": ["Transformasi", "Jadi versi terbaik", "Glowing alami"],
        "best_for": ["skincare", "fashion", "fitness", "makeup"]
    }
}

TARGET_GROUPS = {
    "wanita": {
        "description": "Perhatian tinggi pada penampilan, estetika, dan kepercayaan diri",
        "niches": ["skincare", "fashion", "makeup", "rumah"],
        "preferred_platforms": ["tiktok", "instagram"],
        "psychology_triggers": ["aspiration", "social_proof", "curiosity", "scarcity"]
    },
    "orang_tua": {
        "description": "Takut kehilangan kemandirian fisik dan jadi beban keluarga",
        "niches": ["kesehatan", "fitness", "parenting"],
        "preferred_platforms": ["youtube", "facebook"],
        "psychology_triggers": ["fear", "authority", "loss_aversion"]
    },
    "anak_muda": {
        "description": "Mencari identitas, mengejar karier, ambisi sukses",
        "niches": ["pendidikan", "gadget", "gaming", "travel"],
        "preferred_platforms": ["tiktok", "youtube", "instagram"],
        "psychology_triggers": ["aspiration", "curiosity", "scarcity", "social_proof"]
    }
}

class PsychologyEngine:
    def get_target_group(self, product_category):
        for group, info in TARGET_GROUPS.items():
            for niche in info["niches"]:
                if niche in product_category.lower():
                    return group, info
        return "anak_muda", TARGET_GROUPS["anak_muda"]

    def get_triggers_for_product(self, product_category):
        _, target_info = self.get_target_group(product_category)
        triggers = target_info.get("psychology_triggers", [])
        return [PSYCHOLOGY_FRAMEWORKS[t] for t in triggers if t in PSYCHOLOGY_FRAMEWORKS]

    def generate_hook_by_psychology(self, product, psychology_key):
        framework = PSYCHOLOGY_FRAMEWORKS.get(psychology_key)
        if not framework:
            return f"Coba {product} sekarang!"
        return f"{framework['triggers'][0]} {product}?"

    def build_caption(self, product, target_group, psychology_keys):
        _, target_info = self.get_target_group(product)
        platform = target_info["preferred_platforms"][0]
        trigger_words = []
        for k in psychology_keys:
            if k in PSYCHOLOGY_FRAMEWORKS:
                trigger_words.append(PSYCHOLOGY_FRAMEWORKS[k]["triggers"][0])
        hook = trigger_words[0] if trigger_words else f"{product} terbaik"
        caption = f"{hook} {product}!\n"
        caption += f"Cocok buat kamu yang {target_info['description'][:50]}...\n"
        caption += "Link afiliasi di bio! #fyp #rekomendasi"
        return caption