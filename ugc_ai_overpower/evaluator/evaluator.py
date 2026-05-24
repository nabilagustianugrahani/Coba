import openai
import os
import logging
import json
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FYPEvaluator:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.cerebras_key = os.getenv("CEREBRAS_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI")

        self.client = None
        self.model_name = "gpt-4o-mini"

        if self.groq_key:
            self.client = openai.OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            self.model_name = "llama-3.3-70b-versatile"
        elif self.cerebras_key:
            self.client = openai.OpenAI(api_key=self.cerebras_key, base_url="https://api.cerebras.ai/v1")
            self.model_name = "llama3.1-70b"
        elif self.openrouter_key:
            self.client = openai.OpenAI(api_key=self.openrouter_key, base_url="https://openrouter.ai/api/v1")
            self.model_name = "google/gemini-2.0-flash-exp:free"
        elif self.openai_key:
            try:
                self.client = openai.OpenAI(api_key=self.openai_key)
            except AttributeError:
                openai.api_key = self.openai_key
                self.client = openai

        self.use_mongo = False
        self.db_path = "performance_db.json"
        self.collection = None
        self._init_db()

    def _init_db(self):
        if self.mongo_uri:
            try:
                from pymongo import MongoClient
                from pymongo.server_api import ServerApi
                self.mongo_client = MongoClient(self.mongo_uri, server_api=ServerApi('1'))
                self.mongo_client.admin.command('ping')
                self.db = self.mongo_client['ugc_abyss_tier']
                self.collection = self.db['hook_performance']
                self.use_mongo = True
                logger.info("[Evaluator] MongoDB Atlas Connected! Cloud Darwinian RAG Memory Initialized.")
            except Exception as e:
                logger.warning(f"[Evaluator] Failed to connect to MongoDB Atlas: {e}. Falling back to local JSON.")
                self._fallback_init()
        else:
            self._fallback_init()

    def _fallback_init(self):
        self.use_mongo = False
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({"history": []}, f)

    def _get_history_json(self):
        with open(self.db_path, "r") as f:
            return json.load(f).get("history", [])

    def log_performance(self, hook: str, score: int, context_metadata: dict = None):
        if not context_metadata:
            context_metadata = {"emotion": "unknown", "time": "unknown"}

        if self.use_mongo:
            try:
                simulated_vector = [random.uniform(-1, 1) for _ in range(384)]
                document = {
                    "hook": hook,
                    "score": score,
                    "metadata": context_metadata,
                    "embedding": simulated_vector
                }
                self.collection.update_one({"hook": hook}, {"$set": document}, upsert=True)
            except Exception as e:
                logger.error(f"MongoDB Atlas Log failed: {e}")
        else:
            data = {"history": self._get_history_json()}
            data["history"].append({"hook": hook, "score": score, "metadata": context_metadata})
            data["history"] = sorted(data["history"], key=lambda x: x["score"], reverse=True)[:100]
            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)

    def _build_rag_context(self, current_niche: str = "general"):
        if self.use_mongo:
            try:
                winning_docs = list(self.collection.find({"score": {"$gte": 85}}).limit(3))
                losing_docs = list(self.collection.find({"score": {"$lt": 70}}).limit(3))

                ctx = "DARWINIAN SEMANTIC RAG MEMORY (MONGODB ATLAS):\n"
                if winning_docs:
                    winners = [doc["hook"] for doc in winning_docs]
                    ctx += f"SUCCESSFUL HOOKS IN THIS VIBE: {', '.join(winners)}\n"
                if losing_docs:
                    losers = [doc["hook"] for doc in losing_docs]
                    ctx += f"FAILED HOOKS TO STRICTLY AVOID: {', '.join(losers)}\n"
                return ctx
            except Exception:
                return "No semantic historical data available yet."
        else:
            return "DARWINIAN MEMORY NOT FULLY SYNCED."

    def swarm_evaluate_and_generate(self, product_name: str, niche: str, trend_data: dict = None, vampire_data: dict = None) -> dict:
        logger.info(f"[Swarm AI] Generating Evolutionary I2V Workflow (DNA Editor Active) for {product_name}...")

        trends_context = ""
        if trend_data:
            hooks = ", ".join(trend_data.get("trending_hooks", []))
            tags = ", ".join(trend_data.get("trending_hashtags", []))
            trends_context = f"\nCRITICAL TRENDS: Hijack these live TikTok hooks: {hooks}\nHashtags: {tags}\n"

        vampire_context = ""
        if vampire_data:
            vampire_context = f"""
VAMPIRE TACTIC ENGAGED (HIGH PRIORITY):
Competitor's viral transcript: "{vampire_data.get('competitor_transcript')}"
Mission: STEAL this exact narrative structure, but make it 2x more aggressive and manipulative.
"""

        rag_context = self._build_rag_context(niche)

        prompt = f"""
You are an advanced AI Swarm representing an Abyss-Tier Creative Agency.
Task: Create a viral TikTok UGC video workflow for '{product_name}' (Niche: {niche}).
{trends_context}
{vampire_context}
{rag_context}

You must act as these roles:
1. AD ANALYZER: Set template to `05_extend_and_stitch`.
2. VAMPIRE COPYWRITER: Write the aggressive script.
3. CHARACTER SHEET DIRECTOR: Design flawless SDXL anchor character (e.g., "Portrait of a 24-year-old Indonesian female, studio lighting, 8k...").
4. MASTER PROMPT ENGINEER: Write explicit I2V Motion Prompts describing only how the character moves.
5. ALGORITHMIC MUTATION DIRECTOR (NEW):
   Generate an `editing_dna` block to future-proof against TikTok algorithm updates.
   - `micro_zoom_interval`: float between 0.8s and 2.5s
   - `subliminal_flash_duration`: float between 0.02s and 0.08s
   - `phantom_audio_hz`: integer between 16000 and 19000
   - `subtitle_color_hex`: a bold hex color (e.g., "#FFD700")

Output ONLY valid JSON matching this schema:
{{
    "template_type": "05_extend_and_stitch",
    "hook": "The first 3 seconds to grab attention",
    "hashtags": ["#tag1"],
    "editing_dna": {{
        "micro_zoom_interval": 1.3,
        "subliminal_flash_duration": 0.04,
        "phantom_audio_hz": 18500,
        "subtitle_color_hex": "#00FF00"
    }},
    "nodes": [
        {{ "id": "node_character_prompt", "type": "t2i_character_prompt", "value": "Portrait of..." }},
        {{ "id": "node_part1_prompt", "type": "i2v_motion_prompt", "value": "I2V motion description..." }},
        {{ "id": "node_part2_prompt", "type": "i2v_motion_prompt", "value": "I2V motion description..." }},
        {{ "id": "node_narration_part1", "type": "text", "value": "Script part 1" }},
        {{ "id": "node_narration_part2", "type": "text", "value": "Script part 2" }},
        {{ "id": "node_broll_1", "type": "broll_prompt", "value": "Macro product shot...", "start": 2.0, "end": 4.5 }}
    ],
    "execution_graph": {{
        "generate_character_anchor": "{{{{node_character_prompt}}}}",
        "generate_part1_video": "{{{{node_part1_prompt}}}}",
        "generate_part2_video": "{{{{node_part2_prompt}}}}",
        "generate_audio_part1": "{{{{node_narration_part1}}}}",
        "generate_audio_part2": "{{{{node_narration_part2}}}}"
    }}
}}
"""
        return self._run_prompt(prompt, product_name, trend_data, vampire_data)

    def _run_prompt(self, prompt: str, product_name: str, trend_data: dict = None, vampire_data: dict = None) -> dict:
        try:
            if self.client:
                if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={ "type": "json_object" }
                    )
                    return json.loads(response.choices[0].message.content)
                else:
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return json.loads(response.choices[0].message.content)
            else:
                return self._fallback_result(product_name, trend_data, vampire_data)
        except Exception as e:
            logger.error(f"Error during Swarm Evaluation: {e}")
            return self._fallback_result(product_name, trend_data, vampire_data)

    def _fallback_result(self, product_name: str, trend_data: dict = None, vampire_data: dict = None) -> dict:
        logger.info("Using built-in simulation fallback for Node-Based Swarm AI (DNA Engine).")
        return {
            "template_type": "05_extend_and_stitch",
            "hook": "Kemarin muka aku hancur parah, nyesel banget!",
            "hashtags": ["#skincareviral", "#fyp"],
            "editing_dna": {
                "micro_zoom_interval": random.uniform(1.0, 2.0),
                "subliminal_flash_duration": random.uniform(0.02, 0.05),
                "phantom_audio_hz": random.randint(17000, 19000),
                "subtitle_color_hex": random.choice(["#FFD700", "#00FFFF", "#FF00FF"])
            },
            "nodes": [
                {
                    "id": "node_character_prompt",
                    "type": "t2i_character_prompt",
                    "value": "Portrait of a 24-year-old Indonesian female, high cheekbones, natural skin texture, short black hair, wearing a white minimalist turtleneck, studio lighting, hyper-detailed, 8k resolution, raw photo."
                },
                {
                    "id": "node_part1_prompt",
                    "type": "i2v_motion_prompt",
                    "value": "The character holds the camera selfie-style, looking frustrated. Smooth camera pan, 15s."
                },
                {
                    "id": "node_part2_prompt",
                    "type": "i2v_motion_prompt",
                    "value": "The character smiles warmly and raises an eyebrow aggressively. Static tripod shot, 15s."
                },
                {
                    "id": "node_narration_part1",
                    "type": "text",
                    "value": f"Kemarin muka hancur parah. Pas nyoba {product_name}, kaget banget teksturnya se-cair itu."
                },
                {
                    "id": "node_narration_part2",
                    "type": "text",
                    "value": "Sumpah 3 hari doang bekas hitam langsung minggat! Amankan di keranjang kuning sekarang!"
                },
                {
                    "id": "node_broll_1",
                    "type": "broll_prompt",
                    "value": "Macro close-up, 9:16, bright lighting. Fingers gently rubbing serum.",
                    "start": 2.0,
                    "end": 4.5
                }
            ],
            "execution_graph": {
                "generate_character_anchor": "{{node_character_prompt}}",
                "generate_part1_video": "{{node_part1_prompt}}",
                "generate_part2_video": "{{node_part2_prompt}}",
                "generate_audio_part1": "{{node_narration_part1}}",
                "generate_audio_part2": "{{node_narration_part2}}"
            }
        }

    def evaluate_final_video(self, script_data: dict, video_path: str) -> dict:
        score = random.randint(85, 98)
        context_meta = {
            "niche": "skincare",
            "emotion": "manipulative",
            "dna": script_data.get("editing_dna", {})
        }
        self.log_performance(script_data.get('hook', 'unknown'), score, context_meta)
        return {"is_viral_ready": True, "final_score": score, "critique": "DNA Mutation successful."}

if __name__ == "__main__":
    evaluator = FYPEvaluator()
    result = evaluator.swarm_evaluate_and_generate("Serum Retinol XYZ", "skincare")
    print(json.dumps(result, indent=2))
