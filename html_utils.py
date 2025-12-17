import json
import pandas as pd
import base64

def generate_audio_map_html(input_df, audio_bytes, audio_mime_type):
    """
    Creates a standalone HTML component with Leaflet.js, an audio player,
    and a synchronized stats dashboard.
    """
    import json
    import base64
    import pandas as pd

    # 1. Prepare Data for JS
    export_data = []
    
    # Check which columns are available
    has_stats = 'Rate' in input_df.columns
    
    # Handle column names flexibly
    rate_col = 'Rate' if 'Rate' in input_df.columns else 'rate_placeholder'
    split_col = 'Split (s/500m)' if 'Split (s/500m)' in input_df.columns else 'Speed (m/s)'
    dist_col = 'Distance' if 'Distance' in input_df.columns else 'dist_placeholder'

    for index, row in input_df.iterrows():
        # Basic Map Data
        point_data = {
            'lat': row['latitude'],
            'lon': row['longitude'],
            'seconds': row['seconds_elapsed'], # Crucial for sync
            'time': str(row.get('Elapsed Time', '00:00'))
        }
        
        # Add Stats if they exist (default to 0 or empty)
        if has_stats:
            point_data['rate'] = row.get(rate_col, 0)
            point_data['split'] = row.get(split_col, 0)
            point_data['dist'] = int(row.get(dist_col, 0))
        else:
            point_data['rate'] = "--"
            point_data['split'] = 0
            point_data['dist'] = "--"
            
        export_data.append(point_data)
        
    json_data = json.dumps(export_data)
    
    # 2. Encode Audio
    b64_audio = base64.b64encode(audio_bytes).decode()
    
    # 3. Define HTML Template
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; }}
            
            /* Stats Grid */
            .stats-grid {{ 
                display: grid; 
                grid-template-columns: repeat(4, 1fr); 
                gap: 5px; 
                margin-bottom: 10px; 
                text-align: center;
            }}
            .stat-box {{ background: white; padding: 5px; border-radius: 5px; border: 1px solid #ddd; }}
            .stat-label {{ font-size: 10px; color: #666; display: block; }}
            .stat-value {{ font-size: 16px; font-weight: bold; color: #333; }}

            #map {{ height: 400px; width: 100%; border-radius: 10px; margin-bottom: 10px; }}
            audio {{ width: 100%; margin-top: 5px; }}
            .info-box {{ margin-bottom: 5px; color: #555; font-size: 12px; text-align: center; }}
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
        
        <div class="info-box">Audio syncs automatically with the map position.</div>
        
        <audio id="audioPlayer" controls>
            <source src="data:{audio_mime_type};base64,{b64_audio}" type="{audio_mime_type}">
            Your browser does not support the audio element.
        </audio>

        <script>
            // --- Helper: Format Seconds to MM:SS.s ---
            function fmtSplit(seconds) {{
                if (!seconds || seconds === 0) return "--";
                let m = Math.floor(seconds / 60);
                let s = (seconds % 60).toFixed(1);
                if (s < 10) s = "0" + s;
                return m + ":" + s;
            }}

            // 1. Load Data
            var routePoints = {json_data};
            
            // 2. Initialize Map
            var startLat = routePoints[0].lat;
            var startLon = routePoints[0].lon;
            var map = L.map('map').setView([startLat, startLon], 14);

            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            }}).addTo(map);

            // 3. Draw Route (Thicker Grey Line)
            var latlngs = routePoints.map(p => [p.lat, p.lon]);
            var polyline = L.polyline(latlngs, {{color: 'grey', weight: 8, opacity: 0.6}}).addTo(map);
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
            
            // Optimization: Keep track of last index to avoid searching from 0 every time
            var lastIdx = 0;

            audio.ontimeupdate = function() {{
                var currentTime = audio.currentTime;
                
                // Find closest point (Simple linear search from last known position)
                var closestPoint = routePoints[lastIdx];
                var minDiff = Math.abs(currentTime - routePoints[lastIdx].seconds);
                
                // Scan forward/backward from last index
                // (Reset to 0 if we scrubbed backward)
                var startSearch = (currentTime < routePoints[lastIdx].seconds) ? 0 : lastIdx;

                for (var i = startSearch; i < routePoints.length; i++) {{
                    var diff = Math.abs(currentTime - routePoints[i].seconds);
                    if (diff <= minDiff) {{
                        minDiff = diff;
                        closestPoint = routePoints[i];
                        lastIdx = i;
                    }} else {{
                        // Assuming sorted time, if diff starts growing, we passed the closest point
                        break; 
                    }}
                }}

                // Update UI
                marker.setLatLng([closestPoint.lat, closestPoint.lon]);
                
                document.getElementById("disp-rate").innerText = closestPoint.rate;
                document.getElementById("disp-split").innerText = fmtSplit(closestPoint.split);
                document.getElementById("disp-dist").innerText = closestPoint.dist;
                document.getElementById("disp-time").innerText = closestPoint.time;
            }};
        </script>
    </body>
    </html>
    """
    return html_code

def generate_client_side_replay(merged_df):
    """
    Generates a client-side interactive replay with Speed/Split toggles,
    Fullscreen map, and DATA TRIMMING to fix axis scaling issues.
    """
    import json
    
    # 1. Prepare Data for JS
    export_data = []
    
    # Handle column names flexibly
    rate_col = 'Rate' if 'Rate' in merged_df.columns else merged_df.columns[0]
    dist_col = 'Distance'
    
    # Prioritize Split, fallback to Speed
    if 'Split (s/500m)' in merged_df.columns:
        split_col = 'Split (s/500m)'
    else:
        split_col = 'Speed (m/s)' 

    chart_labels = [] 
    data_rate = []
    data_split = []

    for index, row in merged_df.iterrows():
        # Get values
        dist_val = int(row.get(dist_col, 0))
        rate_val = row.get(rate_col, 0)
        split_val = row.get(split_col, 0) 

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
                border-top: 1px solid #ddd;
            }}
            .slider-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 5px; }}
            .slider-label {{ min-width: 70px; font-size: 11px; color: #555; font-weight: bold; }}
            input[type=range] {{ width: 100%; cursor: pointer; }}
            
            .trim-controls {{
                margin-top: 5px;
                padding-top: 5px;
                border-top: 1px dashed #ccc;
                display: flex;
                gap: 15px;
                justify-content: center;
            }}
            .trim-group {{ display: flex; flex-direction: column; width: 45%; }}
            .trim-group label {{ font-size: 10px; color: #666; margin-bottom: 2px; }}
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
            <div class="slider-row">
                <span class="slider-label">Replay:</span>
                <input type="range" id="replaySlider" min="0" max="100" value="0">
            </div>
            
            <div class="trim-controls">
                <div class="trim-group">
                    <label>Crop Start (Remove stationary start)</label>
                    <input type="range" id="trimStart" min="0" max="100" value="0">
                </div>
                <div class="trim-group">
                    <label>Crop End (Remove stationary end)</label>
                    <input type="range" id="trimEnd" min="0" max="100" value="100">
                </div>
            </div>
            <div style="text-align:center; margin-top:2px; color:#888; font-size:10px;">
                Adjust "Crop" sliders to rescale the graph Y-axis.
            </div>
        </div>

        <script>
            function fmtSplit(seconds) {{
                if (!seconds || seconds === 0) return "--";
                let m = Math.floor(seconds / 60);
                let s = (seconds % 60).toFixed(1);
                if (s < 10) s = "0" + s;
                return m + ":" + s;
            }}

            // --- 1. Load RAW Data ---
            const rawDataPoints = {json_data};
            const rawLabels = {chart_labels};
            const rawRate = {data_rate};
            const rawSplit = {data_split};
            const totalLen = rawDataPoints.length;

            // --- 2. Initialize UI Elements ---
            const replaySlider = document.getElementById("replaySlider");
            const trimStartSlider = document.getElementById("trimStart");
            const trimEndSlider = document.getElementById("trimEnd");

            // Initialize sliders bounds
            trimStartSlider.max = totalLen - 1;
            trimEndSlider.max = totalLen - 1;
            trimEndSlider.value = totalLen - 1; // Default to full end

            // --- 3. Initialize Map ---
            var startLat = rawDataPoints[0].lat;
            var startLon = rawDataPoints[0].lon;
            
            var map = L.map('map', {{
                fullscreenControl: true,
                fullscreenControlOptions: {{ position: 'topleft' }}
            }}).setView([startLat, startLon], 14);

            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19, attribution: '© OpenStreetMap'
            }}).addTo(map);

            // Polyline (Full Route)
            var latlngs = rawDataPoints.map(p => [p.lat, p.lon]);
            var polyline = L.polyline(latlngs, {{color: 'blue', weight: 3, opacity: 0.6}}).addTo(map);
            map.fitBounds(polyline.getBounds());

            var boatIcon = L.divIcon({{
                className: 'boat-marker',
                html: "<div style='background-color:red; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);'></div>",
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            }});
            var marker = L.marker([startLat, startLon], {{icon: boatIcon}}).addTo(map);

            // --- 4. Initialize Chart ---
            var ctx = document.getElementById('perfChart').getContext('2d');
            
            const verticalLinePlugin = {{
                id: 'verticalLine',
                defaults: {{ color: 'red', width: 2 }},
                afterDraw: (chart, args, options) => {{
                    if (chart.tooltip?._active?.length) return;
                    
                    // Convert Replay Slider (Absolute Index) to Chart Index (Relative)
                    const absoluteIdx = parseInt(replaySlider.value);
                    const startCropIdx = parseInt(trimStartSlider.value);
                    
                    // Chart data index starts at 0, which corresponds to raw index 'startCropIdx'
                    const relativeIdx = absoluteIdx - startCropIdx;

                    const meta = chart.getDatasetMeta(0);
                    
                    // Safety check: is the point inside the current visible chart?
                    if (relativeIdx < 0 || relativeIdx >= meta.data.length) return;
                    if (!meta.data[relativeIdx]) return;

                    const x = meta.data[relativeIdx].x;
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
                    labels: rawLabels, // Start with full data
                    datasets: [
                        {{
                            label: 'Rate (SPM)',
                            data: rawRate,
                            borderColor: 'orange',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            yAxisID: 'y'
                        }},
                        {{
                            label: 'Split (s/500m)',
                            data: rawSplit,
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
                            reverse: true,
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

            // --- 5. Logic: Update Data Range based on Trim ---
            function updateDataRange() {{
                let start = parseInt(trimStartSlider.value);
                let end = parseInt(trimEndSlider.value);

                // Validation: Start cannot overlap End
                if (start >= end) {{
                    start = end - 1;
                    trimStartSlider.value = start;
                }}

                // 1. Slice Data for Chart
                const newLabels = rawLabels.slice(start, end + 1);
                const newRate = rawRate.slice(start, end + 1);
                const newSplit = rawSplit.slice(start, end + 1);

                // 2. Update Chart
                myChart.data.labels = newLabels;
                myChart.data.datasets[0].data = newRate;
                myChart.data.datasets[1].data = newSplit;
                myChart.update(); // This triggers auto-scaling of Y axes!

                // 3. Update Replay Slider Bounds
                replaySlider.min = start;
                replaySlider.max = end;
                
                // If replay slider is out of bounds, reset it
                if (parseInt(replaySlider.value) < start) replaySlider.value = start;
                if (parseInt(replaySlider.value) > end) replaySlider.value = end;

                // 4. Update Display
                updateDisplay(replaySlider.value);
            }}

            // --- 6. Logic: Update Display (Map + Stats) ---
            function updateDisplay(idx) {{
                idx = parseInt(idx);
                var pt = rawDataPoints[idx];
                
                if (pt) {{
                    marker.setLatLng([pt.lat, pt.lon]);
                    document.getElementById("disp-rate").innerText = pt.rate;
                    document.getElementById("disp-split").innerText = fmtSplit(pt.split);
                    document.getElementById("disp-dist").innerText = pt.dist;
                    document.getElementById("disp-time").innerText = pt.time;
                }}
                
                myChart.draw(); // Redraw vertical line
            }}

            // --- Listeners ---
            trimStartSlider.oninput = updateDataRange;
            trimEndSlider.oninput = updateDataRange;
            
            replaySlider.oninput = function() {{
                updateDisplay(this.value);
            }};

            // Initial Call
            updateDataRange();

        </script>
    </body>
    </html>
    """
    return html_code
