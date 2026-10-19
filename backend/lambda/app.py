import json
import os
import boto3

# Bedrock client — same region as Lambda (ap-southeast-1)
bedrock = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
MODEL_ID = "apac.amazon.nova-lite-v1:0"

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Requested-With",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def lambda_handler(event, context):
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")

    # CORS preflight
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": HEADERS, "body": ""}

    if path == "/api/health":
        return {
            "statusCode": 200,
            "headers": HEADERS,
            "body": json.dumps({"status": "healthy", "service": "see-you-co2"}),
        }

    # Main AI endpoint — handles report, quest, and chat actions
    if path == "/ai" and http_method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
            action = body.get("action", "chat")
            inputs = body.get("inputs", {})
            user_question = body.get("userQuestion", "")

            if action == "report":
                result = generate_report(inputs)
            elif action == "quest":
                result = generate_quest(inputs)
            elif action == "chat":
                result = generate_chat(inputs, user_question)
            else:
                result = generate_chat(inputs, user_question)

            return {
                "statusCode": 200,
                "headers": HEADERS,
                "body": json.dumps(result),
            }
        except Exception as e:
            print(f"[ERROR] /ai endpoint: {e}")
            return {
                "statusCode": 500,
                "headers": HEADERS,
                "body": json.dumps({"error": str(e)}),
            }

    if path == "/api/calculate" and http_method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
            result = calculate_emissions(body)
            return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(result)}
        except Exception as e:
            return {"statusCode": 400, "headers": HEADERS, "body": json.dumps({"error": str(e)})}

    return {
        "statusCode": 404,
        "headers": HEADERS,
        "body": json.dumps({"error": "Not found"}),
    }


# ── Bedrock helper ────────────────────────────────────────────────────

def call_bedrock(prompt: str, max_tokens: int = 800) -> str:
    """Send a prompt to Nova Lite and return the text response."""
    payload = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
    }
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


# ── Action handlers ───────────────────────────────────────────────────

def generate_report(inputs: dict) -> dict:
    total = inputs.get("totalMonthlyKg", 0)
    transport = inputs.get("transportMonthlyKg", 0)
    diet = inputs.get("dietMonthlyKg", 0)
    energy = inputs.get("energyMonthlyKg", 0)
    transport_type = inputs.get("transportType", "Car")
    diet_type = inputs.get("dietType", "Mixed Diet")
    annual = inputs.get("annualTonnes", 0)
    score = inputs.get("ecoScore", 0)

    prompt = f"""You are SemAI, an expert sustainability coach. A user has completed their carbon footprint assessment.

User's monthly carbon footprint:
- Total: {total} kg CO2
- Transport ({transport_type}): {transport} kg CO2
- Diet ({diet_type}): {diet} kg CO2
- Energy: {energy} kg CO2
- Annual total: {annual} tonnes CO2
- Eco Score: {score}/100

Generate a personalised sustainability report with these 4 sections. Be specific, warm, and actionable. Keep each section concise (2-3 sentences max).

Return ONLY a JSON object with these exact keys:
{{
  "insight": "Key insight about their biggest emission driver and what it means",
  "action": "The single most impactful action they can take this week with estimated CO2 saving",
  "goal": "A specific 14-day sustainability goal tailored to their profile",
  "motivation": "A short motivational message personalised to their eco score and progress"
}}"""

    text = call_bedrock(prompt, max_tokens=600)

    # Parse JSON from response
    try:
        # Extract JSON if wrapped in markdown code blocks
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        ai_data = json.loads(text.strip())
    except Exception:
        # Fallback if JSON parsing fails
        ai_data = {
            "insight": text[:200],
            "action": "Reduce your highest emission activity by 10% this week.",
            "goal": f"Track and reduce your {inputs.get('transportType','transport')} usage for 14 days.",
            "motivation": f"With an eco score of {score}/100, you're making a real difference!"
        }

    return {"ai": ai_data}


def generate_quest(inputs: dict) -> dict:
    total = inputs.get("totalMonthlyKg", 0)
    transport_type = inputs.get("transportType", "Car")
    diet_type = inputs.get("dietType", "Mixed Diet")
    score = inputs.get("ecoScore", 0)

    prompt = f"""You are SemAI, a gamified sustainability coach. Generate 3 fun eco quest missions for a user.

User profile:
- Monthly footprint: {total} kg CO2
- Transport: {transport_type}
- Diet: {diet_type}
- Eco Score: {score}/100

Return ONLY a JSON object:
{{
  "quests": [
    {{
      "title": "Quest title (max 6 words)",
      "description": "What to do and why (1-2 sentences)",
      "xp": 50,
      "difficulty": "Easy",
      "co2_saving": "estimated kg CO2 saved"
    }},
    {{
      "title": "Quest title",
      "description": "What to do and why",
      "xp": 100,
      "difficulty": "Medium",
      "co2_saving": "estimated kg CO2 saved"
    }},
    {{
      "title": "Quest title",
      "description": "What to do and why",
      "xp": 200,
      "difficulty": "Hard",
      "co2_saving": "estimated kg CO2 saved"
    }}
  ],
  "message": "An encouraging message about their eco journey (1 sentence)"
}}"""

    text = call_bedrock(prompt, max_tokens=500)

    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        ai_data = json.loads(text.strip())
    except Exception:
        ai_data = {
            "quests": [
                {"title": "Go Car-Free for a Day", "description": "Use public transport or walk instead of driving.", "xp": 50, "difficulty": "Easy", "co2_saving": "3 kg CO2"},
                {"title": "Plant-Based Meal Week", "description": "Replace 5 meals with plant-based options.", "xp": 100, "difficulty": "Medium", "co2_saving": "8 kg CO2"},
                {"title": "Zero Waste Challenge", "description": "Produce no landfill waste for 7 days.", "xp": 200, "difficulty": "Hard", "co2_saving": "12 kg CO2"},
            ],
            "message": "Every small action counts — keep going!"
        }

    return {"ai": ai_data}


def generate_chat(inputs: dict, user_question: str) -> dict:
    total = inputs.get("totalMonthlyKg", 0)
    transport_type = inputs.get("transportType", "Car")
    diet_type = inputs.get("dietType", "Mixed Diet")
    score = inputs.get("ecoScore", 0)
    annual = inputs.get("annualTonnes", 0)

    # Handle greetings gracefully
    greetings = ["hi", "hello", "hey", "helo", "hai", "sup", "yo"]
    if user_question.lower().strip() in greetings:
        return {
            "ai": {
                "text": f"Hi there! 🌿 I'm SemAI, your personal sustainability coach. I can see your monthly carbon footprint is **{total} kg CO2** with an eco score of **{score}/100**.\n\nAsk me anything about reducing your carbon footprint, your diet, transport choices, or what actions will make the biggest difference for you!"
            }
        }

    prompt = f"""You are SemAI, a friendly and knowledgeable sustainability AI coach. You are having a conversation with a user about their carbon footprint and how to live more sustainably.

User's profile:
- Monthly footprint: {total} kg CO2
- Annual footprint: {annual} tonnes CO2
- Transport: {transport_type}
- Diet: {diet_type}
- Eco Score: {score}/100
- Global average for comparison: 392 kg CO2/month

User's question: {user_question}

Respond in a friendly, conversational tone. Be specific and practical. Reference their actual data where relevant. Keep response under 150 words. Use emojis sparingly.

Return ONLY a JSON object:
{{"text": "your response here"}}"""

    text = call_bedrock(prompt, max_tokens=300)

    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        ai_data = json.loads(text.strip())
    except Exception:
        # If JSON parsing fails, return the raw text
        ai_data = {"text": text.strip()}

    return {"ai": ai_data}


# ── Carbon calculator ─────────────────────────────────────────────────

def calculate_emissions(data):
    energy_kwh = data.get("energy_kwh", 0)
    transport_km = data.get("transport_km", 0)
    waste_kg = data.get("waste_kg", 0)

    energy_factor = 0.4
    transport_factor = 0.21
    waste_factor = 0.5

    total_emissions = (
        energy_kwh * energy_factor
        + transport_km * transport_factor
        + waste_kg * waste_factor
    )

    return {
        "total_co2_kg": round(total_emissions, 2),
        "breakdown": {
            "energy": round(energy_kwh * energy_factor, 2),
            "transport": round(transport_km * transport_factor, 2),
            "waste": round(waste_kg * waste_factor, 2),
        },
        "unit": "kg CO2",
    }
