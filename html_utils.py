import json
import base64

def generate_audio_map_html(gpx_df, audio_bytes, audio_mime_type):
    """
    Creates a standalone HTML component with Leaflet.js and an audio player.
    The JS logic handles syncing the marker position to the audio timestamp.
    """
    # 1. Prepare Data for JS
    # only need lat, lon, and seconds to keep the payload light
    route_data = gpx_df[['latitude', 'longitude', 'seconds_elapsed']].to_dict(orient='records')
    json_data = json.dumps(route_data)
    
    # 2. Encode Audio to Base64 to embed in HTML
    b64_audio = base64.b64encode(audio_bytes).decode()
    
    # 3. Define HTML Template
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map {{ height: 400px; width: 100%; border-radius: 10px; margin-bottom: 10px; }}
            audio {{ width: 100%; margin-top: 10px; }}
            .info-box {{ font-family: sans-serif; margin-bottom: 5px; color: #555; font-size: 14px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="info-box">Press Play to see the marker move along the route in sync with the audio.</div>
        <div id="map"></div>
        <audio id="audioPlayer" controls>
            <source src="data:{audio_mime_type};base64,{b64_audio}" type="{audio_mime_type}">
            Your browser does not support the audio element.
        </audio>

        <script>
            // 1. Load Data
            var routePoints = {json_data};
            
            // 2. Initialize Map
            var startLat = routePoints[0].latitude;
            var startLon = routePoints[0].longitude;
            var map = L.map('map').setView([startLat, startLon], 14);

            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            }}).addTo(map);

            // 3. Draw Route (Grey Background)
            var latlngs = routePoints.map(p => [p.latitude, p.longitude]);
            var polyline = L.polyline(latlngs, {{color: 'grey', weight: 4, opacity: 0.6}}).addTo(map);
            
            map.fitBounds(polyline.getBounds());

            // 4. Create Boat Marker
            var boatIcon = L.divIcon({{
                className: 'custom-div-icon',
                html: "<div style='background-color:red; width: 12px; height: 12px; border-radius: 50%; border: 2px solid black;'></div>",
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            }});
            var marker = L.marker([startLat, startLon], {{icon: boatIcon}}).addTo(map);

            // 5. Audio Sync Logic
            var audio = document.getElementById("audioPlayer");
            
            audio.ontimeupdate = function() {{
                var currentTime = audio.currentTime;
                
                // Find the closest point in data based on time
                var closestPoint = routePoints[0];
                var minDiff = Math.abs(currentTime - routePoints[0].seconds_elapsed);

                for (var i = 1; i < routePoints.length; i++) {{
                    var diff = Math.abs(currentTime - routePoints[i].seconds_elapsed);
                    if (diff < minDiff) {{
                        minDiff = diff;
                        closestPoint = routePoints[i];
                    }}
                }}

                // Move Marker
                marker.setLatLng([closestPoint.latitude, closestPoint.longitude]);
            }};
        </script>
    </body>
    </html>
    """
    return html_code


def generate_client_side_replay(merged_df):
    """
    Generates a lag-free, client-side interactive replay map.
    All data is passed as JSON to JavaScript, allowing instant slider response.
    """
    # 1. Prepare Data for JS (Convert DataFrame to list of dicts)
    # Ensure we only pick the columns we need to keep payload small
    export_data = []
    
    for index, row in merged_df.iterrows():
        export_data.append({
            'lat': row['latitude'],
            'lon': row['longitude'],
            'rate': row.get('Rate', 0),
            'speed': row.get('Speed (m/s)', 0),
            'dist': row.get('Distance', 0),
            'time': str(row.get('Elapsed Time', '00:00')),
            'seconds': row.get('seconds_elapsed', 0)
        })
        
    json_data = json.dumps(export_data)
    
    # 2. Define HTML Template
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; }}
            #map {{ height: 400px; width: 100%; border-radius: 10px; }}
            .controls {{ margin-top: 15px; padding: 10px; background: #f9f9f9; border-radius: 10px; }}
            .slider-container {{ width: 100%; display: flex; align-items: center; gap: 10px; }}
            input[type=range] {{ width: 100%; cursor: pointer; }}
            
            .stats-grid {{ 
                display: grid; 
                grid-template-columns: repeat(4, 1fr); 
                gap: 10px; 
                margin-bottom: 10px; 
                text-align: center;
            }}
            .stat-box {{ background: white; padding: 8px; border-radius: 5px; border: 1px solid #ddd; }}
            .stat-label {{ font-size: 12px; color: #666; display: block; }}
            .stat-value {{ font-size: 18px; font-weight: bold; color: #333; }}
        </style>
    </head>
    <body>
        
        <div class="stats-grid">
            <div class="stat-box">
                <span class="stat-label">Rate (SPM)</span>
                <span id="disp-rate" class="stat-value">--</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Speed (m/s)</span>
                <span id="disp-speed" class="stat-value">--</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Distance (m)</span>
                <span id="disp-dist" class="stat-value">--</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Time</span>
                <span id="disp-time" class="stat-value">--</span>
            </div>
        </div>

        <div id="map"></div>

        <div class="controls">
            <div class="slider-container">
                <span>Start</span>
                <input type="range" id="replaySlider" min="0" max="100" value="0">
                <span>End</span>
            </div>
            <div style="text-align:center; margin-top:5px; color:#888; font-size:12px;">
                Drag slider to replay instantly
            </div>
        </div>

        <script>
            // 1. Load Data
            var dataPoints = {json_data};
            var maxIdx = dataPoints.length - 1;
            
            // Set slider max
            var slider = document.getElementById("replaySlider");
            slider.max = maxIdx;

            // 2. Initialize Map
            var startLat = dataPoints[0].lat;
            var startLon = dataPoints[0].lon;
            var map = L.map('map').setView([startLat, startLon], 14);

            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            }}).addTo(map);

            // 3. Draw Route
            var latlngs = dataPoints.map(p => [p.lat, p.lon]);
            var polyline = L.polyline(latlngs, {{color: 'blue', weight: 3, opacity: 0.6}}).addTo(map);
            map.fitBounds(polyline.getBounds());

            // 4. Create Boat Marker
            var boatIcon = L.divIcon({{
                className: 'boat-marker',
                html: "<div style='background-color:red; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);'></div>",
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            }});
            var marker = L.marker([startLat, startLon], {{icon: boatIcon}}).addTo(map);

            // 5. Interaction Logic
            function updateDisplay(idx) {{
                var pt = dataPoints[idx];
                
                // Move Marker
                marker.setLatLng([pt.lat, pt.lon]);
                
                // Update Stats
                document.getElementById("disp-rate").innerText = pt.rate;
                document.getElementById("disp-speed").innerText = pt.speed;
                document.getElementById("disp-dist").innerText = pt.dist;
                document.getElementById("disp-time").innerText = pt.time;
            }}

            // Initial Load
            updateDisplay(0);

            // Slider Event
            slider.oninput = function() {{
                updateDisplay(this.value);
            }}
        </script>
    </body>
    </html>
    """
    return html_code
