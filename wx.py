import math
from flask import Flask, request, jsonify, render_template
import requests
import os

app = Flask(__name__, template_folder="templates")

# Load API keys from environment variables
WUNDER_API_KEY = os.getenv("WUNDERGROUND_API_KEY", "497e85fd58f14e39be85fd58f1ee3956")  # Your Wunderground API key
OWM_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "35b5f6e19f2be4347afe5d6076b4d008")  # Your OpenWeatherMap API key

BASE_URL = "https://api.weather.com/v2/pws/observations/current"

# Function to convert wind direction (0-360) to cardinal direction
def wind_direction_to_cardinal(degrees):
    directions = ['North', 'North-East', 'East', 'South-East', 'South', 'South-West', 'West', 'North-West']
    index = math.floor((degrees + 22.5) / 45)
    return directions[index % 8]  # Ensure the index wraps around

# Function to calculate tile x, y based on latitude, longitude, and zoom level
def lat_lon_to_tile(lat, lon, zoom):
    # Convert latitude and longitude to Mercator projection
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

@app.route("/")
def home():
    return render_template("weather.html")  # This serves the HTML page

@app.route("/weather", methods=["GET"])
def get_weather():
    station_id = request.args.get("stationId", "KMOJOPLI144")
    
    params = {
        "stationId": station_id,
        "format": "json",
        "units": "e",
        "apiKey": WUNDER_API_KEY  # Using WunderGround API key
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()

    # Debug: Print the raw data to see its structure
    print("Raw Weather Data:", data)

    if response.status_code != 200:
        return jsonify({"error": data.get("message", "Unable to fetch weather data")}), response.status_code
    
    observation = data.get("observations", [])[0] if "observations" in data else None
    if not observation:
        return jsonify({"error": "No observation data found"}), 404
    
    wind_chill = observation["imperial"].get("windChill", "N/A")
    precip_rate = observation["imperial"].get("precipRate", "N/A")  # Rain rate
    precip_total = observation["imperial"].get("precipTotal", "N/A")  # Total precipitation

    # Get actual latitude and longitude from the observation
    lat = float(observation['lat'])  # Ensure lat is a float
    lon = float(observation['lon'])  # Ensure lon is a float
    
    # Extract wind direction (winddir in degrees) and convert to cardinal
    wind_dir = observation.get("winddir")  # winddir is in degrees (safe access with .get())
    wind_cardinal = wind_direction_to_cardinal(wind_dir) if wind_dir is not None else "Unknown"

    print("Wind Direction (Cardinal):", wind_cardinal)

    # Use OpenWeatherMap API key to fetch weather map
    zoom_level = 3  # You can adjust the zoom level as necessary
    xtile, ytile = lat_lon_to_tile(lat, lon, zoom_level)
    
    # Building the OpenWeatherMap tile URL
    map_url = f"https://tile.openweathermap.org/map/precipitation_new/{zoom_level}/{xtile}/{ytile}.png?appid={OWM_API_KEY}"

    return jsonify({
    "stationID": observation["stationID"],
    "temperature": observation["imperial"]["temp"],
    "weather": {
        "humidity": observation["humidity"],
        "windSpeed": observation["imperial"]["windSpeed"],
        "pressure": observation["imperial"]["pressure"]
    },
    "windChill": wind_chill,
    "rainForecast": precip_rate,  # Using precipRate for rain forecast
    "totalRain": precip_total,  # Using precipTotal for total rainfall
    "windDir": wind_cardinal,  # Adding the wind direction in cardinal form
    "weatherMap": map_url  # Adding the weather map URL
})
if __name__ == "__main__":
    app.run(debug=True)
