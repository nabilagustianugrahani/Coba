import openai
import os
import logging
import json

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

    def swarm_evaluate_and_generate(self, product_name: str, niche: str, trend_data: dict = None) -> dict:
        """
        'Swarm in a Prompt' updated for Multi-Persona AI "Podcast" Debate Mode and "Live Commerce" Simulation.
        """
        logger.info(f"[Swarm AI] Generating God-Tier Podcast & Live Commerce Script for {product_name}...")

        trends_context = ""
        if trend_data:
            hooks = ", ".join(trend_data.get("trending_hooks", []))
            tags = ", ".join(trend_data.get("trending_hashtags", []))
            trends_context = f"\nCRITICAL: You MUST hijack these current live TikTok trends to ensure virality:\nTrending Hooks: {hooks}\nTrending Hashtags: {tags}\n"

        prompt = f"""
You are an advanced AI Swarm representing a top-tier Indonesian Creative Agency.
You are tasked with creating a viral TikTok/Reels UGC video for the product: '{product_name}' (Niche: {niche}).
{trends_context}

You must act as 6 roles simultaneously:
1. TREND WATCHER: Adapt the live trending hooks directly into the script.
2. SCRIPTWRITER (MULTI-PERSONA & LIVE COMMERCE): Write a script featuring TWO personas (Host A: Skeptical, Host B: Enthusiastic Expert) debating the product in a fast-paced podcast style.
   - INJECT SIMULATED LIVE COMMERCE INTERACTIONS: Host B must periodically respond to fake live chat comments (e.g., "Wah ada pertanyaan dari kak Budi...").
3. DIRECTOR: Suggest visual B-Roll scenes.
4. COMPLIANCE: Ensure no shadowbanned words (use 'Cek keranjang', 'Si Oren').
5. MASTER PROMPT ENGINEER: Write mathematically perfect Text-to-Video (T2V) prompts for Host A and Host B (forbidding morphing/artifacts).
6. VIDEO EDITOR AI: Define timestamps (in seconds) for B-Roll scenes and define timestamps for fake Live Chat UI popups.

Output ONLY a valid JSON object matching this structure:
{{
    "hook": "The first 3 seconds to grab attention",
    "narration_host_a": "Script for Host A (Skeptical)",
    "narration_host_b": "Script for Host B (Expert, answers fake live chat)",
    "combined_narration_script": "The chronological text of the entire dialogue",
    "avatar_a_motion_prompt": "FLAWLESS detailed prompt for Text-to-Video model (Host A).",
    "avatar_b_motion_prompt": "FLAWLESS detailed prompt for Text-to-Video model (Host B).",
    "negative_prompt": "Detailed negative prompt to prevent artifacts",
    "b_roll_schedule": [
        {{ "prompt": "Cinematic B-Roll 1", "start": 2.0, "end": 4.5 }}
    ],
    "live_chat_schedule": [
        {{ "username": "budi_gaming", "comment": "Beneran ngaruh bang?", "start": 5.0, "end": 8.0 }}
    ],
    "hashtags": ["#tag1", "#tag2"],
    "score": 95,
    "feedback": "Why this podcast/live-commerce style will hit the FYP"
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
            return self._fallback_result(product_name, trend_data, score=70)

    def _fallback_result(self, product_name: str, trend_data: dict = None, score: int = 98) -> dict:
        logger.info("Using built-in simulation fallback for Swarm AI.")

        hook = "Sumpah kalian harus stop lakuin ini kalau mau glowing!"
        hashtags = ["#skincareviral", "#fyp"]

        if trend_data:
            if trend_data.get("trending_hooks"):
                hook = trend_data["trending_hooks"][0]
            if trend_data.get("trending_hashtags"):
                hashtags = trend_data["trending_hashtags"]

        return {
            "hook": hook,
            "narration_host_a": f"{hook} Gak percaya gue sama produk ginian.",
            "narration_host_b": f"Eh jangan salah! {product_name} ini beda. Tuh lihat kak Budi nanya di chat, emang ngaruh? Ngaruh banget bro! Cek keranjang kuning sekarang mumpung lagi diskon di si oren!",
            "combined_narration_script": f"Host A: {hook} Gak percaya gue sama produk ginian. Host B: Eh jangan salah! {product_name} ini beda. Tuh lihat kak Budi nanya di chat, emang ngaruh? Ngaruh banget bro! Cek keranjang kuning sekarang mumpung lagi diskon di si oren!",
            "avatar_a_motion_prompt": "Medium shot of a skeptical Indonesian man vlogging, podcast mic, eye-level angle, soft volumetric lighting, photorealistic, 8k, locked off camera",
            "avatar_b_motion_prompt": "Medium shot of an enthusiastic Indonesian woman vlogging, podcast mic, eye-level angle, soft volumetric lighting, photorealistic, 8k, locked off camera",
            "negative_prompt": "morphed face, bad anatomy, extra fingers, jitter, low resolution, blurry, distorted, cartoon, 3d render",
            "b_roll_schedule": [
                {
                    "prompt": f"Cinematic close up of {product_name} texture on hand, 4k macro",
                    "start": 2.0,
                    "end": 4.0
                }
            ],
            "live_chat_schedule": [
                {
                    "username": "budi_gaming",
                    "comment": "Beneran ngaruh bang?",
                    "start": 5.0,
                    "end": 8.0
                }
            ],
            "hashtags": hashtags,
            "score": score,
            "feedback": "Multi-persona podcast format with simulated live commerce chat increases engagement drastically."
        }

    def evaluate_final_video(self, script_data: dict, video_path: str) -> dict:
        logger.info(f"[Recursive Loop] Evaluating Final Video at {video_path} for FYP Potential...")
        prompt = f"""
You are an AI TikTok Algorithm simulator.
Evaluate the final completed UGC video metadata for FYP viral potential.

Original Script Hook: {script_data.get('hook')}
Original Narration: {script_data.get('combined_narration_script')}
Video Motion Style: {script_data.get('avatar_a_motion_prompt')}
Editor Insertions: {len(script_data.get('b_roll_schedule', []))} B-Rolls
Live Chat Simulated: {len(script_data.get('live_chat_schedule', []))} interactions

Does this combination have a high probability of going viral in Indonesia right now?
Output ONLY valid JSON:
{{
    "is_viral_ready": true,
    "final_score": 92,
    "critique": "Detailed analysis"
}}
"""
        return self._run_prompt(prompt, "Final Video")

if __name__ == "__main__":
    evaluator = FYPEvaluator()
    result = evaluator.swarm_evaluate_and_generate("Serum Retinol XYZ", "skincare")
    print(json.dumps(result, indent=2))
