import openai
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FYPEvaluator:
    def __init__(self):
        # We can use an open-source model endpoint or OpenAI
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        if self.api_key:
            openai.api_key = self.api_key

    def evaluate_script(self, script: str, product_name: str) -> dict:
        """
        Evaluates the script hook, retention potential, and call-to-action.
        """
        logger.info(f"Evaluating script for product: {product_name}")

        prompt = f"""
Evaluate this TikTok UGC script for FYP potential in Indonesia for the product '{product_name}'.
Consider hook strength, retention, and call-to-action.

Script: {script}

Respond ONLY in JSON format:
{{
    "score": <0-100>,
    "feedback": "<detailed feedback on what to improve>"
}}
"""
        try:
            if self.api_key:
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                import json
                result = json.loads(response.choices[0].message.content)
                score = result.get("score", 70)
                feedback = result.get("feedback", "No feedback provided.")
            else:
                logger.warning("No OPENAI_API_KEY provided. Simulating evaluation.")
                score = 85
                feedback = "Hook is strong, but the Call To Action needs more urgency."
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            score = 70
            feedback = "Evaluation failed due to an error."

        return {
            "score": score,
            "feedback": feedback,
            "is_ready_for_fyp": score >= 80
        }

    def improve_script(self, script: str, feedback: str, product_name: str) -> str:
        prompt = f"""
You are an expert Indonesian TikTok UGC creator.
Improve the following script for '{product_name}' based on this feedback: "{feedback}"
Make it highly engaging, conversational, and likely to hit the FYP. Keep it short.

Original Script: {script}

Respond ONLY with the new script text.
"""
        try:
            if self.api_key:
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content.strip()
            else:
                logger.warning("No OPENAI_API_KEY provided. Simulating improvement.")
                return script + f"\n(Improved based on: {feedback})"
        except Exception as e:
            logger.error(f"Error during improvement: {e}")
            return script

    def recursive_improvement_loop(self, initial_script: str, product_name: str, max_iterations: int = 3):
        """
        Recursively improves the script until it reaches an 'FYP' ready score.
        """
        current_script = initial_script

        for i in range(max_iterations):
            logger.info(f"Iteration {i+1} for FYP Evaluation...")
            evaluation = self.evaluate_script(current_script, product_name)

            if evaluation["is_ready_for_fyp"]:
                logger.info("Script is ready for FYP!")
                return current_script, evaluation

            logger.info(f"Script needs improvement: {evaluation['feedback']}")
            current_script = self.improve_script(current_script, evaluation['feedback'], product_name)

        return current_script, {"score": 75, "feedback": "Max iterations reached", "is_ready_for_fyp": False}

if __name__ == "__main__":
    evaluator = FYPEvaluator()
    script = "Hai guys, aku mau review skincare ini..."
    final_script, result = evaluator.recursive_improvement_loop(script, "Skincare XYZ")
    print(final_script)
    print(result)
