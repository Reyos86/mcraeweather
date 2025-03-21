import math
from flask import Flask, request, jsonify, render_template
import json
import requests
import os
import threading
from datetime import datetime, timedelta

app = Flask(__name__, template_folder="templates")

# Load API keys from environment variables
WUNDER_API_KEY = os.getenv("WUNDERGROUND_API_KEY", "497e85fd58f14e39be85fd58f1ee3956")  # Your Wunderground API key
OWM_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "35b5f6e19f2be4347afe5d6076b4d008")  # Your OpenWeatherMap API key

BASE_URL = "https://api.weather.com/v2/pws/observations/current"
FORECAST_URL = "https://api.weather.com/v3/wx/forecast/daily/5day"


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
    return render_template("chat.html") #Chat HTML?

@app.route("/weather", methods=["GET"])
def get_weather():
    station_id = request.args.get("stationId", "KMOJOPLI144")
    
    params = {
        "stationId": station_id,
        "format": "json",
        "units": "e",
        "apiKey": WUNDER_API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()

    print("API Response:", data)
    
    if response.status_code != 200:
        return jsonify({"error": data.get("message", "Unable to fetch weather data")}), response.status_code

    # Ensure observation data exists before using it
    observations = data.get("observations", [])
    if not observations:
        return jsonify({"error": "No observation data found"}), 404
    
    observation = observations[0]  # Get the first observation safely

    wind_chill = observation["imperial"].get("windChill", "N/A")
    precip_rate = observation["imperial"].get("precipRate", "N/A")
    precip_total = observation["imperial"].get("precipTotal", "N/A")

    lat = float(observation["lat"])
    lon = float(observation["lon"])

    wind_dir = observation.get("winddir")
    wind_cardinal = wind_direction_to_cardinal(wind_dir) if wind_dir is not None else "Unknown"

    zoom_level = 3
    xtile, ytile = lat_lon_to_tile(lat, lon, zoom_level)

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
        "rainForecast": precip_rate,
        "totalRain": precip_total,
        "windDir": wind_cardinal,
        "weatherMap": map_url,
    })


@app.route('/forecast')
def get_forecast():
    # Example coordinates (you can update these as needed)
    lat, lon = 37.0842, -94.5133  
    forecast_url = f'https://api.weather.com/v3/wx/forecast/daily/5day?postalKey=64804:US&units=e&language=en-US&format=json&apiKey={WUNDER_API_KEY}'

    response = requests.get(forecast_url)
    data = response.json()

    # **DEBUG PRINT - Print the entire API response**
    print("\n=== FULL FORECAST API RESPONSE ===")
    print(json.dumps(data, indent=2))  # Pretty-print the entire response

    if 'dayOfWeek' not in data or len(data['dayOfWeek']) == 0:
        return jsonify({"error": "No forecast data available"}), 400

    forecast_data = []
    days_of_week = data.get('dayOfWeek', [])
    dayparts = data.get('daypart', [])

    # Get today's and tomorrow's day names dynamically
    today = datetime.today().strftime('%A')  # Get the current day as a string (e.g., 'Monday')
    tomorrow = (datetime.today() + timedelta(days=1)).strftime('%A')  # Get the next day (e.g., 'Tuesday')

    # Default to "default" icon
    today_icon = "default" 

    # Loop through the forecast days
    for i in range(len(days_of_week)):
        day = days_of_week[i]
        narrative = data.get('narrative', [])[i] if i < len(data.get('narrative', [])) else "No narrative"

        temp_max_values = data.get('temperatureMax', [])
        temp_min_values = data.get('temperatureMin', [])

        temp_max = temp_max_values[i] if i < len(temp_max_values) and temp_max_values[i] is not None else "N/A"
        temp_min = temp_min_values[i] if i < len(temp_min_values) and temp_min_values[i] is not None else "N/A"

        # Default to 'default' icon if no valid icon is found
        icon_code = "default" 

        # We expect dayparts to be a list of dictionaries with keys daypartName, dayOrNight, and iconCode
        daypart_names = dayparts[0].get('daypartName', [])
        day_or_night = dayparts[0].get('dayOrNight', [])
        icon_codes = dayparts[0].get('iconCode', [])

        if not daypart_names or not day_or_night or not icon_codes:
            print(f"Missing data for day {day}. Skipping icon assignment.")
        else:
            # Determine if we should use "Today" or "Tonight" based on time of day
            if day == today:
                # If the data is already for tonight, label it as "Tonight"
                day = "Tonight" if "night" in narrative.lower() else "Today"
                today_icon = icon_codes[1] if "N" in day_or_night else icon_codes[0]  # Use night icon if after sunset
            elif day == tomorrow:
                day = "Tomorrow"

            # Loop through each day's daypart names to find the corresponding daytime and nighttime icon code
            for j in range(len(daypart_names)):
                if daypart_names[j] and daypart_names[j].lower() == day.lower():
                    icon_code = icon_codes[j]
                    break  # Stop once the correct icon for the day is found

        print(f"Processed {day}: icon={icon_code}, tempMax={temp_max}, tempMin={temp_min}")  # Debug output

        forecast_data.append({
            "day": day,
            "narrative": narrative,
            "iconCode": icon_code,
            "tempMax": temp_max,
            "tempMin": temp_min
        })

    # Add today's icon to the response, so it can be displayed at the top
    return jsonify({
        "todayIcon": today_icon,
        "forecastData": forecast_data
    })

# Function to run Flask on port 5000
def run_on_5000():
    app.run(host='127.0.0.1', port=5000)

# Function to run Flask on port 10000
def run_on_10000():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    # Run both instances on separate threads
    threading.Thread(target=run_on_5000).start()
    threading.Thread(target=run_on_10000).start()


