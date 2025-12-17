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
