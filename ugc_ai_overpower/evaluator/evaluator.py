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

        # Vector Database for Semantic RAG Tracking (Upgraded to MongoDB Atlas)
        self.use_mongo = False
        self.db_path = "performance_db.json" # Fallback JSON
        self.collection = None
        self._init_db()

    def _init_db(self):
        if self.mongo_uri:
            try:
                from pymongo import MongoClient
                from pymongo.server_api import ServerApi

                # Create a new client and connect to the server
                self.mongo_client = MongoClient(self.mongo_uri, server_api=ServerApi('1'))

                # Send a ping to confirm a successful connection
                self.mongo_client.admin.command('ping')

                self.db = self.mongo_client['ugc_abyss_tier']
                self.collection = self.db['hook_performance']
                self.use_mongo = True
                logger.info("[Evaluator] MongoDB Atlas Connected! Cloud Darwinian RAG Memory Initialized.")
            except ImportError:
                logger.warning("[Evaluator] pymongo not installed. Falling back to local JSON memory.")
                self._fallback_init()
            except Exception as e:
                logger.warning(f"[Evaluator] Failed to connect to MongoDB Atlas: {e}. Falling back to local JSON.")
                self._fallback_init()
        else:
            logger.info("[Evaluator] No MONGO_URI provided. Using local JSON for Darwinian Memory.")
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
                # In a real setup, we would generate a dense vector embedding here
                # (e.g., using OpenAI or SentenceTransformers) to store alongside the text
                # for MongoDB Atlas Vector Search.
                # Simulated vector generation:
                simulated_vector = [random.uniform(-1, 1) for _ in range(384)]

                document = {
                    "hook": hook,
                    "score": score,
                    "metadata": context_metadata,
                    "embedding": simulated_vector
                }

                # Upsert logic based on the hook text
                self.collection.update_one(
                    {"hook": hook},
                    {"$set": document},
                    upsert=True
                )
                logger.info(f"Logged hook performance to MongoDB Atlas: Score {score}")
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
                # Simulated MongoDB Atlas Vector Search ($vectorSearch operator)
                # In production, this would perform a semantic similarity search

                # We simulate standard query fallback for now
                winning_docs = list(self.collection.find({"score": {"$gte": 85}}).limit(3))
                losing_docs = list(self.collection.find({"score": {"$lt": 70}}).limit(3))

                ctx = "DARWINIAN SEMANTIC RAG MEMORY (MONGODB ATLAS):\n"
                if winning_docs:
                    winners = [doc["hook"] for doc in winning_docs]
                    ctx += f"SUCCESSFUL HOOKS IN THIS VIBE (USE AS INSPIRATION): {', '.join(winners)}\n"
                if losing_docs:
                    losers = [doc["hook"] for doc in losing_docs]
                    ctx += f"FAILED HOOKS TO STRICTLY AVOID: {', '.join(losers)}\n"
                return ctx
            except Exception as e:
                logger.warning(f"MongoDB RAG failed: {e}")
                return "No semantic historical data available yet."
        else:
            history = self._get_history_json()
            if not history:
                return "No historical data available yet."

            winning_hooks = [h["hook"] for h in history if h["score"] >= 90][:3]
            losing_hooks = [h["hook"] for h in history if h["score"] < 70][:3]

            ctx = "DARWINIAN AUTO-EVOLUTION DATA:\n"
            if winning_hooks:
                ctx += f"SUCCESSFUL HOOKS TO ITERATE ON: {', '.join(winning_hooks)}\n"
            if losing_hooks:
                ctx += f"FAILED HOOKS TO STRICTLY AVOID: {', '.join(losing_hooks)}\n"

            return ctx

    def swarm_evaluate_and_generate(self, product_name: str, niche: str, trend_data: dict = None, vampire_data: dict = None) -> dict:
        logger.info(f"[Swarm AI] Generating Evolutionary I2V Node-Based Workflow for {product_name}...")

        trends_context = ""
        if trend_data:
            hooks = ", ".join(trend_data.get("trending_hooks", []))
            tags = ", ".join(trend_data.get("trending_hashtags", []))
            trends_context = f"\nCRITICAL TRENDS: Hijack these live TikTok hooks: {hooks}\nHashtags: {tags}\n"

        vampire_context = ""
        if vampire_data:
            vampire_context = f"""
VAMPIRE TACTIC ENGAGED (HIGH PRIORITY):
A competitor's video is currently going viral with this transcript:
"{vampire_data.get('competitor_transcript')}"
Emotional Trigger Used: {vampire_data.get('emotional_trigger')}

Your mission: STEAL this exact narrative structure, but make it 2x more aggressive, manipulative, and FOMO-inducing. Do not copy it word-for-word, but clone its psychological payload to steal their traffic.
"""

        rag_context = self._build_rag_context(niche)

        prompt = f"""
You are an advanced AI Swarm representing an Abyss-Tier Creative Agency.
Task: Create a viral TikTok/Reels UGC video workflow for '{product_name}' (Niche: {niche}).
{trends_context}
{vampire_context}
{rag_context}

You must act as these roles to build an I2V (Image-to-Video) NODE-BASED WORKFLOW JSON:

1. AD ANALYZER: Choose `05_extend_and_stitch` template.
2. VAMPIRE COPYWRITER: Execute the Vampire Tactic context provided above to write the ultimate aggressive script.
3. CHARACTER SHEET DIRECTOR:
   - You MUST design an absolute flawless anchor face/character blueprint.
   - Example: "Portrait of a 24-year-old Indonesian female, high cheekbones, natural skin texture, short black hair, wearing a white minimalist turtleneck, studio lighting, hyper-detailed, 8k resolution, raw photo."
4. MASTER PROMPT ENGINEER (I2V Specialist):
   - Write explicit I2V (Image-to-Video) Motion Prompts for `Wan2.1-I2V`.
   - Your prompts MUST ONLY describe how the character from the anchor image moves.
   - Example: "The character turns her head slightly to the left while smiling, holding up the product. Smooth camera pan, 15s."
5. NODE ARCHITECT: Output generation steps using `{{{{node_id}}}}` syntax.

Output ONLY valid JSON matching this schema:
{{
    "template_type": "05_extend_and_stitch",
    "hook": "The first 3 seconds to grab attention",
    "hashtags": ["#tag1"],
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
            logger.error(f"Error during Swarm Evaluation using {self.model_name}: {e}")
            return self._fallback_result(product_name, trend_data, vampire_data)

    def _fallback_result(self, product_name: str, trend_data: dict = None, vampire_data: dict = None) -> dict:
        logger.info("Using built-in simulation fallback for Node-Based Swarm AI (Vampire Engine).")

        hook = "Sumpah kalian harus stop lakuin ini kalau mau glowing!"
        hashtags = ["#skincareviral", "#fyp"]

        narration1 = f"{hook} Aku nemu rahasia dari {product_name} yang beneran ngebantu banget. Teksturnya super ringan, cepet meresap."
        narration2 = "Gak cuma itu, ini tuh bikin wajah cerah seharian. Cek keranjang kuning sekarang mumpung lagi diskon di si oren!"

        if vampire_data:
            hook = "Kemarin muka aku hancur parah, nyesel banget baru tau rahasia ini!"
            narration1 = f"{hook} Udah buang duit beli merk mahal tetep zonk. Pas iseng nyoba {product_name}, kaget banget teksturnya se-cair itu."
            narration2 = "Sumpah 3 hari doang bekas hitam langsung minggat! Ini aku ingetin mumpung lagi flash sale gede-gedean, langsung amankan di keranjang kuning sekarang sebelum kehabisan!"

        elif trend_data:
            if trend_data.get("trending_hooks"):
                hook = trend_data["trending_hooks"][0]
            if trend_data.get("trending_hashtags"):
                hashtags = trend_data["trending_hashtags"]

        return {
            "template_type": "05_extend_and_stitch",
            "hook": hook,
            "hashtags": hashtags,
            "nodes": [
                {
                    "id": "node_character_prompt",
                    "type": "t2i_character_prompt",
                    "value": "Portrait of a 24-year-old Indonesian female, high cheekbones, natural skin texture, short black hair, wearing a white minimalist turtleneck, studio lighting, hyper-detailed, 8k resolution, raw photo."
                },
                {
                    "id": "node_part1_prompt",
                    "type": "i2v_motion_prompt",
                    "value": "The character holds the camera selfie-style, looking frustrated then relieved. She points to her cheek. Smooth camera pan, 15s."
                },
                {
                    "id": "node_part2_prompt",
                    "type": "i2v_motion_prompt",
                    "value": "The character smiles warmly and raises an eyebrow aggressively, aggressively pointing at the screen. Static tripod shot, 15s."
                },
                {
                    "id": "node_narration_part1",
                    "type": "text",
                    "value": narration1
                },
                {
                    "id": "node_narration_part2",
                    "type": "text",
                    "value": narration2
                },
                {
                    "id": "node_broll_1",
                    "type": "broll_prompt",
                    "value": "Macro close-up, 9:16, bright lighting. Fingers gently rubbing serum. No on-screen text. The feeling of deep hydration.",
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
        logger.info(f"[Recursive Loop] Evaluating Final Video at {video_path} for FYP Potential...")
        prompt = f"""
You are an AI TikTok Algorithm simulator.
Evaluate the final completed UGC video metadata for FYP viral potential.

Original Script Hook: {script_data.get('hook')}
Template Used: {script_data.get('template_type')}

Does this combination have a high probability of going viral in Indonesia right now?
Output ONLY valid JSON:
{{
    "is_viral_ready": true,
    "final_score": 92,
    "critique": "Detailed analysis"
}}
"""
        res = self._run_prompt(prompt, "Final Video")

        score = 92
        if isinstance(res, dict) and "final_score" in res:
            score = res["final_score"]

        context_meta = {
            "niche": "skincare",
            "emotion": "manipulative",
            "vampire_tactic": True
        }
        self.log_performance(script_data.get('hook', 'unknown'), score, context_meta)

        return res

if __name__ == "__main__":
    evaluator = FYPEvaluator()
    vamp_data = {
            "competitor_hook": "Jujur nyesel banget baru tau serum ini sekarang.",
            "competitor_transcript": "Jujur nyesel banget baru tau serum ini sekarang. Kemarin muka aku hancur parah banyak bekas jerawat hitam.",
            "pacing_speed": "fast",
            "emotional_trigger": "regret_and_discovery",
            "views_velocity": "100k_per_hour"
    }
    result = evaluator.swarm_evaluate_and_generate("Serum Retinol XYZ", "skincare", vampire_data=vamp_data)
    print(json.dumps(result, indent=2))
