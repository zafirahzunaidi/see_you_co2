import json
import os


def lambda_handler(event, context):
    """
    Main Lambda handler for See You CO2 API.
    Handles API Gateway requests for the sustainability dashboard.
    """
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    # Route requests
    if path == "/api/health":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"status": "healthy", "service": "see-you-co2"}),
        }

    if path == "/api/calculate" and http_method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
            result = calculate_emissions(body)
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps(result),
            }
        except Exception as e:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": str(e)}),
            }

    return {
        "statusCode": 404,
        "headers": headers,
        "body": json.dumps({"error": "Not found"}),
    }


def calculate_emissions(data):
    """
    Calculate CO2 emissions based on input data.
    Customize this function with your actual calculation logic.
    """
    # Example calculation - replace with your actual logic
    energy_kwh = data.get("energy_kwh", 0)
    transport_km = data.get("transport_km", 0)
    waste_kg = data.get("waste_kg", 0)

    # Emission factors (kg CO2 per unit)
    energy_factor = 0.4  # kg CO2 per kWh (grid average)
    transport_factor = 0.21  # kg CO2 per km (average car)
    waste_factor = 0.5  # kg CO2 per kg waste

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
