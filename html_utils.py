import json
import pandas as pd
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
            var polyline = L.polyline(latlngs, {{color: 'grey', weight: 6, opacity: 0.8}}).addTo(map);
            
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
    REPLACES Speed with Split (s/500m).
    """
    import json
    
    # 1. Prepare Data for JS
    export_data = []
    
    # Column selection
    rate_col = 'Rate' if 'Rate' in merged_df.columns else merged_df.columns[0]
    dist_col = 'Distance'
    
    # PRIORITIZE SPLIT
    if 'Split (s/500m)' in merged_df.columns:
        split_col = 'Split (s/500m)'
    else:
        # Fallback if calculation failed (shouldn't happen with updated app.py)
        split_col = 'Speed (m/s)' 

    chart_labels = [] 
    data_rate = []
    data_split = []

    for index, row in merged_df.iterrows():
        # Get values
        dist_val = int(row.get(dist_col, 0))
        rate_val = row.get(rate_col, 0)
        split_val = row.get(split_col, 0) # This is in seconds (e.g., 135.5)

        # Prepare Map/Stats Data
        export_data.append({
            'lat': row['latitude'],
            'lon': row['longitude'],
            'rate': rate_val,
            'split': split_val,
            'dist': dist_val,
            'time': str(row.get('Elapsed Time', '00:00')),
        })
        
        # Prepare Chart Data
        chart_labels.append(dist_val)
        data_rate.append(rate_val)
        data_split.append(split_val)
        
    json_data = json.dumps(export_data)
    
    # 2. Define HTML Template
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        
        <script src='https://api.mapbox.com/mapbox.js/plugins/leaflet-fullscreen/v1.0.1/Leaflet.fullscreen.min.js'></script>
        <link href='https://api.mapbox.com/mapbox.js/plugins/leaflet-fullscreen/v1.0.1/leaflet.fullscreen.css' rel='stylesheet' />

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }}
            
            #map {{ flex: 1; min-height: 250px; width: 100%; border-radius: 10px; }}
            
            .chart-container {{ 
                height: 200px; 
                width: 100%; 
                margin-top: 10px;
                flex-shrink: 0;
            }}

            .stats-grid {{ 
                display: grid; 
                grid-template-columns: repeat(4, 1fr); 
                gap: 5px; 
                margin-bottom: 5px; 
                text-align: center;
                flex-shrink: 0;
            }}
            .stat-box {{ background: white; padding: 5px; border-radius: 5px; border: 1px solid #ddd; }}
            .stat-label {{ font-size: 10px; color: #666; display: block; }}
            .stat-value {{ font-size: 14px; font-weight: bold; color: #333; }}

            .controls {{ 
                margin-top: 5px; 
                padding: 10px; 
                background: #f9f9f9; 
                border-radius: 10px; 
                flex-shrink: 0;
                position: sticky; 
                bottom: 0;
            }}
            .slider-container {{ width: 100%; display: flex; align-items: center; gap: 10px; }}
            input[type=range] {{ width: 100%; cursor: pointer; }}
        </style>
    </head>
    <body>
        
        <div class="stats-grid">
            <div class="stat-box"><span class="stat-label">Rate (SPM)</span><span id="disp-rate" class="stat-value">--</span></div>
            <div class="stat-box"><span class="stat-label">Split (/500m)</span><span id="disp-split" class="stat-value">--</span></div>
            <div class="stat-box"><span class="stat-label">Distance (m)</span><span id="disp-dist" class="stat-value">--</span></div>
            <div class="stat-box"><span class="stat-label">Time</span><span id="disp-time" class="stat-value">--</span></div>
        </div>

        <div id="map"></div>

        <div class="chart-container">
            <canvas id="perfChart"></canvas>
        </div>

        <div class="controls">
            <div class="slider-container">
                <span style="font-size:12px;">Start</span>
                <input type="range" id="replaySlider" min="0" max="100" value="0">
                <span style="font-size:12px;">End</span>
            </div>
            <div style="text-align:center; margin-top:2px; color:#888; font-size:10px;">
                Drag to replay • Chart indicates current stroke
            </div>
        </div>

        <script>
            // --- Helper: Format Seconds to MM:SS.s ---
            function fmtSplit(seconds) {{
                if (!seconds || seconds === 0) return "--";
                let m = Math.floor(seconds / 60);
                let s = (seconds % 60).toFixed(1);
                if (s < 10) s = "0" + s;
                return m + ":" + s;
            }}

            // --- 1. Load Data ---
            var dataPoints = {json_data};
            var chartLabels = {chart_labels};
            var rateData = {data_rate};
            var splitData = {data_split};
            
            var maxIdx = dataPoints.length - 1;
            var slider = document.getElementById("replaySlider");
            slider.max = maxIdx;

            // --- 2. Initialize Map ---
            var startLat = dataPoints[0].lat;
            var startLon = dataPoints[0].lon;
            
            var map = L.map('map', {{
                fullscreenControl: true,
                fullscreenControlOptions: {{ position: 'topleft' }}
            }}).setView([startLat, startLon], 14);

            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19, attribution: '© OpenStreetMap'
            }}).addTo(map);

            var latlngs = dataPoints.map(p => [p.lat, p.lon]);
            var polyline = L.polyline(latlngs, {{color: 'blue', weight: 3, opacity: 0.6}}).addTo(map);
            map.fitBounds(polyline.getBounds());

            var boatIcon = L.divIcon({{
                className: 'boat-marker',
                html: "<div style='background-color:red; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);'></div>",
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            }});
            var marker = L.marker([startLat, startLon], {{icon: boatIcon}}).addTo(map);

            // --- 3. Initialize Chart ---
            var ctx = document.getElementById('perfChart').getContext('2d');
            
            // Plugin for vertical line
            const verticalLinePlugin = {{
                id: 'verticalLine',
                defaults: {{ color: 'red', width: 2 }},
                afterDraw: (chart, args, options) => {{
                    if (chart.tooltip?._active?.length) return;
                    const idx = parseInt(slider.value);
                    const meta = chart.getDatasetMeta(0);
                    if (!meta.data[idx]) return;
                    const x = meta.data[idx].x;
                    const top = chart.chartArea.top;
                    const bottom = chart.chartArea.bottom;
                    const ctx = chart.ctx;
                    ctx.save();
                    ctx.beginPath();
                    ctx.moveTo(x, top);
                    ctx.lineTo(x, bottom);
                    ctx.lineWidth = options.width;
                    ctx.strokeStyle = options.color;
                    ctx.stroke();
                    ctx.restore();
                }}
            }};

            var myChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: chartLabels,
                    datasets: [
                        {{
                            label: 'Rate (SPM)',
                            data: rateData,
                            borderColor: 'orange',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            yAxisID: 'y'
                        }},
                        {{
                            label: 'Split (s/500m)',
                            data: splitData,
                            borderColor: 'green',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            yAxisID: 'y1'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    animation: false,
                    scales: {{
                        x: {{ 
                            title: {{ display: true, text: 'Distance (m)' }},
                            ticks: {{ maxTicksLimit: 10 }}
                        }},
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {{ display: true, text: 'Rate' }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: {{ drawOnChartArea: false }},
                            reverse: true,  // INVERTED AXIS: Lower split is higher/faster
                            title: {{ display: true, text: 'Split' }}
                        }}
                    }},
                    plugins: {{
                        verticalLine: {{ color: 'red', width: 1.5 }},
                        legend: {{ labels: {{ boxWidth: 10 }} }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    let label = context.dataset.label || '';
                                    if (label) {{ label += ': '; }}
                                    if (context.dataset.label.includes("Split")) {{
                                        return label + fmtSplit(context.parsed.y);
                                    }}
                                    return label + context.parsed.y;
                                }}
                            }}
                        }}
                    }}
                }},
                plugins: [verticalLinePlugin]
            }});

            // --- 4. Interaction Logic ---
            function updateDisplay(idx) {{
                var pt = dataPoints[idx];
                
                marker.setLatLng([pt.lat, pt.lon]);
                
                document.getElementById("disp-rate").innerText = pt.rate;
                // Format the split using the helper function
                document.getElementById("disp-split").innerText = fmtSplit(pt.split);
                document.getElementById("disp-dist").innerText = pt.dist;
                document.getElementById("disp-time").innerText = pt.time;
                
                myChart.draw();
            }}

            updateDisplay(0);

            slider.oninput = function() {{
                updateDisplay(this.value);
            }}
        </script>
    </body>
    </html>
    """
    return html_code
