import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import requests  # for sending the feedback data to email service
from folium.plugins import Fullscreen

# --- Caching & Parsing Functions ---

@st.cache_data
def parse_time_str(time_str):
    """
    Parses time strings like '00:15:30' or '15:30.5' into total seconds.
    Rounds to the nearest integer.
    """
    try:
        if pd.isna(time_str): return 0
        if isinstance(time_str, (int, float)): return int(round(time_str))
        
        parts = str(time_str).split(':')
        total_seconds = 0.0
        
        if len(parts) == 3: # HH:MM:SS
            h, m, s = parts
            total_seconds = int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2: # MM:SS
            m, s = parts
            total_seconds = int(m) * 60 + float(s)
            
        return int(round(total_seconds))
    except:
        return 0

@st.cache_data
def parse_gpx_data(gpx_bytes):
    """
    Parses GPX bytes and returns a DataFrame of coordinates + 'seconds_elapsed'.
    Cached to prevent re-parsing on every interaction.
    """
    # Parse the GPX bytes
    gpx = gpxpy.parse(gpx_bytes)
    
    data = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                data.append({
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'time': point.time
                })
    
    df = pd.DataFrame(data)

    if not df.empty and 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        start_time = df['time'].iloc[0]
        # Calculate seconds elapsed, round to nearest int
        df['seconds_elapsed'] = (df['time'] - start_time).dt.total_seconds().round().astype(int)
    
    return df

@st.cache_data
def load_csv_data(csv_file):
    """
    Loads and cleans the CSV data. Cached for performance.
    """
    csv_df = pd.read_csv(csv_file, header=1)
    csv_df.columns = [c.strip() for c in csv_df.columns]
    
    if 'Elapsed Time' in csv_df.columns:
        csv_df['seconds_elapsed'] = csv_df['Elapsed Time'].apply(parse_time_str)
        
    return csv_df

@st.cache_data
def merge_datasets(gpx_df, csv_df):
    """
    Merges GPX and CSV data based on seconds_elapsed.
    Cached because merge_asof is expensive to run on every slider move.
    """
    gpx_clean = gpx_df.dropna(subset=['seconds_elapsed']).copy()
    csv_clean = csv_df.dropna(subset=['seconds_elapsed']).copy()
    
    gpx_clean['seconds_elapsed'] = gpx_clean['seconds_elapsed'].astype(int)
    csv_clean['seconds_elapsed'] = csv_clean['seconds_elapsed'].astype(int)
    
    gpx_sorted = gpx_clean.sort_values('seconds_elapsed')
    csv_sorted = csv_clean.sort_values('seconds_elapsed')

    merged_df = pd.merge_asof(
        csv_sorted, 
        gpx_sorted[['seconds_elapsed', 'latitude', 'longitude']], 
        on='seconds_elapsed', 
        direction='nearest',
        tolerance=5 
    )
    
    return merged_df.dropna(subset=['latitude', 'longitude'])

def plot_metrics(df):
    """Generates static line charts for rowing metrics."""
    wanted_cols = ['Rate', 'Speed (m/s)', 'Distance/Stroke', 'Check']
    cols_to_plot = [c for c in wanted_cols if c in df.columns]
    
    if cols_to_plot:
        st.subheader("Performance Metrics")
        if 'Distance' in df.columns:
            st.write("X-axis: Distance (m)")
            st.line_chart(df.set_index('Distance')[cols_to_plot])
        elif 'Elapsed Time' in df.columns:
            st.write("X-axis: Time")
            st.line_chart(df.set_index('Elapsed Time')[cols_to_plot])
        else:
            st.write("X-axis: Stroke Number")
            st.line_chart(df[cols_to_plot])

def send_simple_email(name, email, subject, message):
    api_url = "https://formspree.io/f/xpwvvnkn"
    payload = {"name": name, "_replyto": email, "_subject": subject, "message": message}
    response = requests.post(api_url, data=payload)
    return response.status_code, response.text


# --- Main App Logic ---

st.set_page_config(layout="wide")

# Header with Logo
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    st.image("logo.png", use_container_width=True)

st.write("Upload your rowing data to view the route and analysis.")

# 1. File Uploaders
c1, c2 = st.columns(2)
uploaded_gpx = c1.file_uploader("Upload GPX", type=['gpx'])
uploaded_csv = c2.file_uploader("Upload CSV (we recommend GRAPH over SPLIT)", type=['csv'])

# Holders for dataframes
gpx_df = None
csv_df = None

# 2. Process and Plot GPX (Map + Raw View)
if uploaded_gpx is not None:
    try:
        # Pass BYTES to the cached function to ensure stability
        gpx_df = parse_gpx_data(uploaded_gpx.getvalue())

        st.subheader("Rowing Route")
        
        # Center map on the starting point
        start_location = [gpx_df['latitude'].iloc[0], gpx_df['longitude'].iloc[0]]
        m = folium.Map(location=start_location, zoom_start=14)
        
        # Draw the route line (PolyLine)
        coordinates = list(zip(gpx_df['latitude'], gpx_df['longitude']))
        folium.PolyLine(coordinates, color="blue", weight=2.5, opacity=1).add_to(m)

        # FIX: Fullscreen must be added BEFORE st_folium renders the map
        Fullscreen().add_to(m)
        
        # Render map in Streamlit
        st_folium(m, width=1200, height=500)

        # View Raw GPX Data 
        with st.expander("📂 Raw GPX Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the GPX file:")
            st.dataframe(gpx_df)
        
    except Exception as e:
        st.error(f"Error processing GPX: {e}")

# 3. Process and Plot CSV (Stats)
if uploaded_csv is not None:
    try:
        # Use cached CSV loader
        csv_df = load_csv_data(uploaded_csv)
        
        with st.expander("📂 Raw CSV Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the CSV file:")
            st.dataframe(csv_df)
        
        plot_metrics(csv_df)
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")

# 4. --- Interactive Replay Map (Combined Data) ---

if gpx_df is not None and csv_df is not None:
    st.markdown("---")
    st.subheader("Interactive Replay")
    st.write("Move the map to frame the course. Drag the slider to replay. The map stays where you leave it.")

    try:
        # Use cached merge function
        merged_df = merge_datasets(gpx_df, csv_df)

        if not merged_df.empty:
            # C. The Slider
            max_index = len(merged_df) - 1
            selected_index = st.slider("Select Point / Stroke", 0, max_index, 0)
            
            # Get current row
            current_row = merged_df.iloc[selected_index]
            
            # D. Layout
            col_stats, col_map = st.columns([1, 3])
            
            with col_stats:
                st.markdown("### Current Stats")
                rate = current_row.get('Rate', 0)
                speed = current_row.get('Speed (m/s)', 0)
                dist = current_row.get('Distance', 0)
                time_str = current_row.get('Elapsed Time', '00:00')

                st.metric("Rate (SPM)", f"{rate}")
                st.metric("Speed (m/s)", f"{speed}")
                st.metric("Distance", f"{dist} m")
                st.caption(f"Time: {time_str}")

            with col_map:
                # --- MAP GENERATION ---
                
                # 1. Determine Zoom/Center (Persist User State)
                min_lat, max_lat = gpx_df['latitude'].min(), gpx_df['latitude'].max()
                min_lon, max_lon = gpx_df['longitude'].min(), gpx_df['longitude'].max()
                default_center = [(min_lat + max_lat) / 2, (min_lon + max_lon) / 2]
                default_zoom = 14
                
                map_state = st.session_state.get("interactive_map", {})
                
                if map_state and "center" in map_state and "zoom" in map_state:
                    center_to_use = [map_state["center"]["lat"], map_state["center"]["lng"]]
                    zoom_to_use = map_state["zoom"]
                    should_fit_bounds = False 
                else:
                    center_to_use = default_center
                    zoom_to_use = default_zoom
                    should_fit_bounds = True
                
                m_interactive = folium.Map(location=center_to_use, zoom_start=zoom_to_use)

                if should_fit_bounds:
                     sw = [min_lat, min_lon]
                     ne = [max_lat, max_lon]
                     m_interactive.fit_bounds([sw, ne])

                # 2. Draw Full Route in RED (Untravelled background)
                folium.PolyLine(
                    list(zip(gpx_df['latitude'], gpx_df['longitude'])), 
                    color="red", weight=3, opacity=0.6, tooltip="Untravelled"
                ).add_to(m_interactive)

                # 3. Draw Travelled Route in BLUE
                current_time_sec = current_row['seconds_elapsed']
                path_so_far = gpx_df[gpx_df['seconds_elapsed'] <= current_time_sec]
                if not path_so_far.empty:
                    folium.PolyLine(
                        list(zip(path_so_far['latitude'], path_so_far['longitude'])), 
                        color="blue", weight=4, opacity=1, tooltip="Travelled"
                    ).add_to(m_interactive)

                # 4. Boat Dot
                boat_loc = [current_row['latitude'], current_row['longitude']]
                folium.CircleMarker(
                    location=boat_loc, 
                    radius=8, 
                    color="black",      
                    weight=1,           
                    fill=True, 
                    fill_color="red",   
                    fill_opacity=1
                ).add_to(m_interactive)

                st_folium(m_interactive, width=800, height=500, key="interactive_map")
        else:
            st.warning("Could not link CSV and GPX data.")
            
    except Exception as e:
        st.error(f"Error in interactive section: {e}")

# 5. Compare Two GPX Lines ---

st.markdown("---")
st.header("Compare GPX Lines")
st.write("Upload up to three different GPX files to compare their steering lines side-by-side.")

col_comp1, col_comp2, col_comp3 = st.columns(3)
comp_gpx_1 = col_comp1.file_uploader("Upload Track 1 (Blue)", type=['gpx'], key="comp1")
comp_gpx_2 = col_comp2.file_uploader("Upload Track 2 (Red)", type=['gpx'], key="comp2")
comp_gpx_3 = col_comp3.file_uploader("Upload Track 3 (Black)", type=['gpx'], key="comp3")

tracks_to_plot = []

# Parse available files (Using cached function)
if comp_gpx_1:
    try:
        tracks_to_plot.append({'data': parse_gpx_data(comp_gpx_1.getvalue()), 'color': 'blue', 'name': 'Track 1'})
    except Exception as e:
        st.error(f"Error parsing Track 1: {e}")

if comp_gpx_2:
    try:
        tracks_to_plot.append({'data': parse_gpx_data(comp_gpx_2.getvalue()), 'color': 'red', 'name': 'Track 2'})
    except Exception as e:
        st.error(f"Error parsing Track 2: {e}")

if comp_gpx_3:
    try:
        tracks_to_plot.append({'data': parse_gpx_data(comp_gpx_3.getvalue()), 'color': 'black', 'name': 'Track 3'})
    except Exception as e:
        st.error(f"Error parsing Track 3: {e}")

if tracks_to_plot:
    try:
        all_lats = pd.concat([t['data']['latitude'] for t in tracks_to_plot])
        all_lons = pd.concat([t['data']['longitude'] for t in tracks_to_plot])
        
        min_lat, max_lat = all_lats.min(), all_lats.max()
        min_lon, max_lon = all_lons.min(), all_lons.max()
        
        sw = [min_lat, min_lon]
        ne = [max_lat, max_lon]
        
        m_compare = folium.Map(location=[(min_lat + max_lat)/2, (min_lon + max_lon)/2], zoom_start=13)
        m_compare.fit_bounds([sw, ne])

        Fullscreen().add_to(m_compare)
        
        for track in tracks_to_plot:
            folium.PolyLine(
                list(zip(track['data']['latitude'], track['data']['longitude'])), 
                color=track['color'], weight=3, opacity=0.7, tooltip=track['name']
            ).add_to(m_compare)
        
        st_folium(m_compare, width=800, height=500, key="compare_map")
        
        st.markdown(
            """
            <div style="display: flex; gap: 20px; justify-content: center; margin-top: 10px;">
                <span style="color: blue; font-weight: bold;">■ Track 1 (Blue)</span>
                <span style="color: red; font-weight: bold;">■ Track 2 (Red)</span>
                <span style="color: black; font-weight: bold;">■ Track 3 (Black)</span>
            </div>
            """, 
            unsafe_allow_html=True
        )

    except Exception as e:
        st.error(f"Error processing comparison map: {e}")

# 6. Feedback Part
st.markdown("---") 

st.markdown(
    """
    <div style='text-align: center; color: grey;'>
        <small>This web application is developed and maintained by 
        <a href='https://github.com/NikJur'>NikJur (Github)</a>.</small>
    </div>
    """,
    unsafe_allow_html=True
)

st.header("Contact & Feedback")
with st.form("contact_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1: name_input = st.text_input("Name")
    with col2: email_input = st.text_input("Contact Email")
    subject_input = st.text_input("Subject Header")
    message_input = st.text_area("Main Text")
    submitted = st.form_submit_button("Send Feedback")
    
    if submitted:
        if not (name_input and email_input and message_input):
            st.error("Please fill in your name, email, and a message.")
        else:
            status, response_text = send_simple_email(name_input, email_input, subject_input, message_input)
            if status == 200:
                st.success("Message sent successfully!")
            else:
                st.error(f"Failed to send. Status Code: {status}")
                with st.expander("See Error Details"):
                    st.text(response_text)
