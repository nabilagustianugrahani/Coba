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

        self.db_path = "performance_db.json"
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({"history": []}, f)

    def _get_history(self):
        with open(self.db_path, "r") as f:
            return json.load(f).get("history", [])

    def log_performance(self, hook: str, score: int):
        data = {"history": self._get_history()}
        data["history"].append({"hook": hook, "score": score})
        data["history"] = sorted(data["history"], key=lambda x: x["score"], reverse=True)[:100]
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _build_rag_context(self):
        history = self._get_history()
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

    def swarm_evaluate_and_generate(self, product_name: str, niche: str, trend_data: dict = None) -> dict:
        """
        'Swarm in a Prompt' incorporating Character Sheet Director for flawless consistency.
        """
        logger.info(f"[Swarm AI] Generating Evolutionary Node-Based Workflow for {product_name}...")

        trends_context = ""
        if trend_data:
            hooks = ", ".join(trend_data.get("trending_hooks", []))
            tags = ", ".join(trend_data.get("trending_hashtags", []))
            trends_context = f"\nCRITICAL TRENDS: Hijack these live TikTok hooks: {hooks}\nHashtags: {tags}\n"

        rag_context = self._build_rag_context()

        prompt = f"""
You are an advanced AI Swarm representing a top-tier Indonesian Creative Agency.
Task: Create a viral TikTok/Reels UGC video workflow for '{product_name}' (Niche: {niche}).
{trends_context}
{rag_context}

You must act as these roles to build a NODE-BASED WORKFLOW JSON:

1. AD ANALYZER: Choose `05_extend_and_stitch` template.
2. SCRIPTWRITER & COMPLIANCE: Learn from DARWINIAN DATA. No shadowbanned words.
3. CHARACTER SHEET DIRECTOR (CRITICAL):
   - You MUST design an absolute flawless anchor face/character blueprint.
   - This prompt must explicitly define age, ethnicity, bone structure, eye color, and clothing.
   - Example: "Portrait of a 24-year-old Indonesian female, high cheekbones, natural skin texture, short black hair, wearing a white minimalist turtleneck, studio lighting, hyper-detailed, 8k resolution, raw photo."
4. MASTER PROMPT ENGINEER:
   - Match the video generation prompts EXACTLY to the Character Sheet Director's clothing and styling so there are no morphing artifacts.
5. NODE ARCHITECT: Output generation steps using `{{{{node_id}}}}` syntax.

Output ONLY valid JSON matching this schema:
{{
    "template_type": "05_extend_and_stitch",
    "hook": "The first 3 seconds to grab attention",
    "hashtags": ["#tag1"],
    "nodes": [
        {{ "id": "node_character_prompt", "type": "t2i_character_prompt", "value": "Portrait of..." }},
        {{ "id": "node_part1_prompt", "type": "t2v_prompt", "value": "..." }},
        {{ "id": "node_part2_prompt", "type": "t2v_prompt", "value": "..." }},
        {{ "id": "node_narration_part1", "type": "text", "value": "Script part 1" }},
        {{ "id": "node_narration_part2", "type": "text", "value": "Script part 2" }},
        {{ "id": "node_broll_1", "type": "broll_prompt", "value": "...", "start": 2.0, "end": 4.5 }}
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
        return self._run_prompt(prompt, product_name, trend_data)

    def _run_prompt(self, prompt: str, product_name: str, trend_data: dict = None) -> dict:
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
                return self._fallback_result(product_name, trend_data)
        except Exception as e:
            logger.error(f"Error during Swarm Evaluation using {self.model_name}: {e}")
            return self._fallback_result(product_name, trend_data)

    def _fallback_result(self, product_name: str, trend_data: dict = None) -> dict:
        logger.info("Using built-in simulation fallback for Node-Based Swarm AI.")

        hook = "Sumpah kalian harus stop lakuin ini kalau mau glowing!"
        hashtags = ["#skincareviral", "#fyp"]

        if trend_data:
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
                    "type": "t2v_prompt",
                    "value": "15s, 9:16, bright minimal bedroom, morning natural light. 24yo Indonesian woman, clear skin, white minimalist turtleneck. Eye-level, selfie-style handheld camera. No on-screen text. The feeling of fresh morning confidence."
                },
                {
                    "id": "node_part2_prompt",
                    "type": "t2v_prompt",
                    "value": "15s, 9:16, bright minimal bedroom. Eye-level, tripod static camera. 24yo Indonesian woman in white minimalist turtleneck points to her glowing cheek and smiles warmly. No on-screen text. The feeling of lasting radiance."
                },
                {
                    "id": "node_narration_part1",
                    "type": "text",
                    "value": f"{hook} Aku nemu rahasia dari {product_name} yang beneran ngebantu banget. Teksturnya super ringan, cepet meresap."
                },
                {
                    "id": "node_narration_part2",
                    "type": "text",
                    "value": "Gak cuma itu, ini tuh bikin wajah cerah seharian. Cek keranjang kuning sekarang mumpung lagi diskon di si oren!"
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
        self.log_performance(script_data.get('hook', 'unknown'), score)

        return res

if __name__ == "__main__":
    evaluator = FYPEvaluator()
    result = evaluator.swarm_evaluate_and_generate("Serum Retinol XYZ", "skincare")
    print(json.dumps(result, indent=2))
