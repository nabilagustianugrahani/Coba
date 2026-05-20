import openai
import os
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FYPEvaluator:
    def __init__(self):
        # We check for free provider keys first, then fallback to OpenAI
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.cerebras_key = os.getenv("CEREBRAS_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

        self.client = None
        self.model_name = "gpt-4o-mini"

        if self.groq_key:
            logger.info("Initializing Groq (Free/Ultra-fast) for Swarm Evaluator.")
            self.client = openai.OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            self.model_name = "llama-3.3-70b-versatile"
        elif self.cerebras_key:
            logger.info("Initializing Cerebras (Free/Ultra-fast) for Swarm Evaluator.")
            self.client = openai.OpenAI(api_key=self.cerebras_key, base_url="https://api.cerebras.ai/v1")
            self.model_name = "llama3.1-70b"
        elif self.openrouter_key:
            logger.info("Initializing OpenRouter (Free Gemini) for Swarm Evaluator.")
            self.client = openai.OpenAI(api_key=self.openrouter_key, base_url="https://openrouter.ai/api/v1")
            self.model_name = "google/gemini-2.0-flash-exp:free"
        elif self.openai_key:
            logger.info("Initializing OpenAI for Swarm Evaluator.")
            try:
                self.client = openai.OpenAI(api_key=self.openai_key)
            except AttributeError:
                openai.api_key = self.openai_key
                self.client = openai
        else:
            logger.warning("No API Keys found for Swarm Evaluator. Will use simulation fallback.")

    def swarm_evaluate_and_generate(self, product_name: str, niche: str) -> dict:
        """
        'Swarm in a Prompt' architecture updated with a Master Prompt Engineer.
        Runs entirely on free/zero-cost LLM providers.
        """
        logger.info(f"[Swarm AI] Generating God-Tier Script & Flawless Prompts for {product_name}...")

        prompt = f"""
You are an advanced AI Swarm representing a top-tier Indonesian Creative Agency.
You are tasked with creating a viral TikTok/Reels UGC video for the product: '{product_name}' (Niche: {niche}).

You must act as 5 roles simultaneously:
1. TREND WATCHER: Identify a current trending hook/style in Indonesia.
2. SCRIPTWRITER: Write highly engaging, fast-paced narration.
3. DIRECTOR: Suggest visual B-Roll scenes.
4. COMPLIANCE: Ensure no shadowbanned words (e.g., use 'Cek keranjang', 'Si Oren' instead of 'Beli', 'Shopee').
5. MASTER PROMPT ENGINEER: Write mathematically perfect, highly detailed Text-to-Video (T2V) prompts.
   - The T2V prompt MUST include lighting (e.g., 'volumetric lighting, soft studio light'), camera angle (e.g., 'medium shot, eye-level vlog angle'), camera movement ('static, locked off' to prevent morphing), character details, and explicitly forbid morphing/artifacts.
   - Also generate a 'negative_prompt' to ensure flawless, artifact-free generation (e.g., 'extra fingers, morphed face, bad anatomy, jitter, low resolution').

Output ONLY a valid JSON object matching this structure:
{{
    "hook": "The first 3 seconds to grab attention",
    "narration": "Full spoken script for Edge-TTS",
    "avatar_motion_prompt": "FLAWLESS detailed prompt for Text-to-Video model. Example: 'Medium shot of a beautiful Indonesian woman vlogging, eye-level, soft cinematic lighting, holding camera steady, realistic skin texture, 8k resolution, highly detailed, photorealistic'",
    "negative_prompt": "Detailed negative prompt to prevent artifacts",
    "b_roll_prompts": ["Prompt for cinematic B-roll 1", "Prompt for cinematic B-roll 2"],
    "score": 95,
    "feedback": "Why this script will hit the FYP"
}}
"""
        return self._run_prompt(prompt, product_name)

    def _run_prompt(self, prompt: str, product_name: str) -> dict:
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
                return self._fallback_result(product_name)
        except Exception as e:
            logger.error(f"Error during Swarm Evaluation using {self.model_name}: {e}")
            return self._fallback_result(product_name, score=70)

    def _fallback_result(self, product_name: str, score: int = 98) -> dict:
        logger.info("Using built-in simulation fallback for Swarm AI.")
        return {
            "hook": "Sumpah kalian harus stop lakuin ini kalau mau glowing!",
            "narration": "Sumpah kalian harus stop lakuin ini kalau mau glowing! Aku nemu rahasia dari " + product_name + " yang beneran ngebantu banget. Teksturnya super ringan, cepet meresap. Cek keranjang kuning sekarang mumpung lagi diskon di si oren!",
            "avatar_motion_prompt": "Medium shot of a beautiful Indonesian woman vlogging, eye-level angle, soft volumetric lighting, holding camera steady, realistic skin texture, photorealistic, 8k, locked off camera, no movement",
            "negative_prompt": "morphed face, bad anatomy, extra fingers, jitter, low resolution, blurry, distorted, cartoon, 3d render",
            "b_roll_prompts": [
                f"Cinematic close up of {product_name} texture on hand, 4k macro",
                f"Aesthetic shot of {product_name} packaging on a wooden table with sunlight"
            ],
            "score": score,
            "feedback": "Strong negative hook, compliant CTA, flawless vlog motion prompt."
        }

    def evaluate_final_video(self, script_data: dict, video_path: str) -> dict:
        logger.info(f"[Recursive Loop] Evaluating Final Video at {video_path} for FYP Potential...")
        prompt = f"""
You are an AI TikTok Algorithm simulator.
Evaluate the final completed UGC video metadata for FYP viral potential.

Original Script Hook: {script_data.get('hook')}
Original Narration: {script_data.get('narration')}
Video Motion Style: {script_data.get('avatar_motion_prompt')}

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
