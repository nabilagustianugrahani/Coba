import openai
import os
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FYPEvaluator:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except AttributeError:
                openai.api_key = self.api_key
                self.client = openai
        else:
            self.client = None

    def swarm_evaluate_and_generate(self, product_name: str, niche: str) -> dict:
        """
        'Swarm in a Prompt' architecture.
        """
        logger.info(f"[Swarm AI] Generating God-Tier Script for {product_name}...")

        prompt = f"""
You are an advanced AI Swarm representing a top-tier Indonesian Creative Agency.
You are tasked with creating a viral TikTok/Reels UGC video for the product: '{product_name}' (Niche: {niche}).

You must act as 4 roles simultaneously:
1. TREND WATCHER: Identify a current trending hook/style in Indonesia.
2. SCRIPTWRITER: Write highly engaging, fast-paced narration.
3. DIRECTOR: Suggest visual B-Roll scenes and motion for the AI Avatar (Vlog style).
4. COMPLIANCE: Ensure no shadowbanned words (e.g., use 'Cek keranjang', 'Si Oren' instead of 'Beli', 'Shopee').

Output ONLY a valid JSON object matching this structure:
{{
    "hook": "The first 3 seconds to grab attention",
    "narration": "Full spoken script for Edge-TTS",
    "avatar_motion_prompt": "Prompt for Text-to-Video model (e.g., 'Indonesian woman vlogging while walking in a cafe')",
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
                        model="gpt-4o-mini",
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
                logger.warning("No OPENAI_API_KEY provided. Simulating Swarm Output.")
                return self._fallback_result(product_name)
        except Exception as e:
            logger.error(f"Error during Swarm Evaluation: {e}")
            return self._fallback_result(product_name, score=70)

    def _fallback_result(self, product_name: str, score: int = 98) -> dict:
        return {
            "hook": "Sumpah kalian harus stop lakuin ini kalau mau glowing!",
            "narration": "Sumpah kalian harus stop lakuin ini kalau mau glowing! Aku nemu rahasia dari " + product_name + " yang beneran ngebantu banget. Teksturnya super ringan, cepet meresap. Cek keranjang kuning sekarang mumpung lagi diskon di si oren!",
            "avatar_motion_prompt": "Beautiful Indonesian woman vlogging, holding camera close, walking in a bright aesthetic cafe, hyper-realistic, 8k",
            "b_roll_prompts": [
                f"Cinematic close up of {product_name} texture on hand, 4k macro",
                f"Aesthetic shot of {product_name} packaging on a wooden table with sunlight"
            ],
            "score": score,
            "feedback": "Strong negative hook, compliant CTA, dynamic vlog motion."
        }

    def evaluate_final_video(self, script_data: dict, video_path: str) -> dict:
        """
        Recursive loop simulation: Evaluates the completed video metadata and script
        to ensure it meets FYP viral standards before uploading.
        """
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
