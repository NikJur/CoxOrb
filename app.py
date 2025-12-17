import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import requests
from datetime import timedelta
import numpy as np

# --- 1. Helper Functions ---

def parse_time_str(time_str):
    """
    Parses time strings like '00:15:30' or '15:30.5' into total seconds.
    """
    try:
        if pd.isna(time_str): return 0
        # If it's already a number (seconds), return it
        if isinstance(time_str, (int, float)): return time_str
        
        parts = str(time_str).split(':')
        if len(parts) == 3: # HH:MM:SS
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2: # MM:SS
            m, s = parts
            return int(m) * 60 + float(s)
        return 0
    except:
        return 0

def parse_gpx(file_buffer):
    """Parses GPX to DataFrame and calculates seconds_elapsed."""
    gpx = gpxpy.parse(file_buffer)
    data = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                data.append({
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'time': point.time,
                    'elevation': point.elevation
                })
    
    df = pd.DataFrame(data)
    
    # Calculate Seconds Elapsed (Relative to start)
    if not df.empty and 'time' in df.columns:
        start_time = df['time'].iloc[0]
        df['seconds_elapsed'] = (df['time'] - start_time).dt.total_seconds()
    
    return df

def load_and_clean_csv(file_buffer):
    """Loads CSV and standardizes column names."""
    df = pd.read_csv(file_buffer)
    
    # Standardize Column Names (strip spaces, handle potential issues)
    df.columns = [c.strip() for c in df.columns]
    
    # Map common variations to standard internal names
    # User's columns: Distance, Elapsed Time, Avg Rate, Avg Speed (m/s)
    col_map = {
        'Elapsed Time': 'time_str',
        'Distance': 'distance',
        'Avg Rate': 'rate',
        'Avg Speed (m/s)': 'speed_ms',
        'Avg Speed (mm:ss/500m)': 'split_500'
    }
    
    # Rename columns if they exist
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    
    # Convert 'time_str' to 'seconds_elapsed' for merging
    if 'time_str' in df.columns:
        df['seconds_elapsed'] = df['time_str'].apply(parse_time_str)
    
    return df

def send_simple_email(name, email, subject, message):
    api_url = "https://formspree.io/f/xpwvvnkn" 
    payload = {"name": name, "_replyto": email, "_subject": subject, "message": message}
    try:
        response = requests.post(api_url, data=payload)
        return response.status_code, response.text
    except Exception as e:
        return 0, str(e)

# --- 2. Main App Logic ---

st.set_page_config(page_title="CoxOrb Visualizer", layout="wide")
st.title("CoxOrb Data Visualizer")

# Initialize Session State for Data
if 'merged_data' not in st.session_state:
    st.session_state.merged_data = None

# Sidebar for Uploads
with st.sidebar:
    st.header("Data Upload")
    uploaded_gpx = st.file_uploader("1. Upload GPX", type=['gpx'])
    uploaded_csv = st.file_uploader("2. Upload CSV", type=['csv'])
    
    if uploaded_gpx and uploaded_csv:
        if st.button("Process & Link Files"):
            try:
                # 1. Load Files
                gpx_df = parse_gpx(uploaded_gpx)
                csv_df = load_and_clean_csv(uploaded_csv)
                
                # 2. Merge Data
                # We merge "asof" (nearest timestamp) to link CSV stroke data to GPX coordinates
                gpx_df = gpx_df.sort_values('seconds_elapsed')
                csv_df = csv_df.sort_values('seconds_elapsed')
                
                merged = pd.merge_asof(
                    csv_df, 
                    gpx_df[['seconds_elapsed', 'latitude', 'longitude']], 
                    on='seconds_elapsed', 
                    direction='nearest',
                    tolerance=5 # Match if within 5 seconds
                )
                
                st.session_state.merged_data = merged
                st.success("Files Linked Successfully!")
                
            except Exception as e:
                st.error(f"Error merging files: {e}")

# --- 3. Visualization Section ---

if st.session_state.merged_data is not None:
    df = st.session_state.merged_data
    
    # A. The Slider
    # We use the index (Stroke Number) or Time as the slider
    max_time = int(df['seconds_elapsed'].max())
    
    st.markdown("### ⏱️ Replay Your Row")
    
    # Slider returns the 'seconds_elapsed' value
    selected_time = st.slider(
        "Move slider to see stats at that moment:", 
        min_value=0, 
        max_value=max_time, 
        value=0,
        step=1
    )
    
    # Get the row closest to the selected time
    # We use iloc to find the index where seconds_elapsed is closest
    row_idx = (df['seconds_elapsed'] - selected_time).abs().idxmin()
    current_row = df.loc[row_idx]
    
    # B. The Metrics Display (Dynamic)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Time", f"{timedelta(seconds=int(current_row['seconds_elapsed']))}")
    with col2:
        val = current_row.get('rate', 0)
        st.metric("Rate (spm)", f"{val:.1f}")
    with col3:
        val = current_row.get('speed_ms', 0)
        st.metric("Speed (m/s)", f"{val:.2f}")
    with col4:
        val = current_row.get('distance', 0)
        st.metric("Distance (m)", f"{val:.0f}")
        
    # C. The Map (with current position marker)
    # Note: We redraw the map to update the marker. 
    
    # Base Map centered on the track
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=14)
    
    # 1. Draw the full track (Grey)
    points = list(zip(df['latitude'], df['longitude']))
    folium.PolyLine(points, color="grey", weight=3, opacity=0.5).add_to(m)
    
    # 2. Draw the path UP TO the current point (Blue)
    # Filter data up to selected time
    past_df = df[df['seconds_elapsed'] <= selected_time]
    if not past_df.empty:
        past_points = list(zip(past_df['latitude'], past_df['longitude']))
        folium.PolyLine(past_points, color="blue", weight=4, opacity=1).add_to(m)
    
    # 3. Add Marker for current position
    folium.CircleMarker(
        location=[current_row['latitude'], current_row['longitude']],
        radius=8,
        color="red",
        fill=True,
        fill_color="red"
    ).add_to(m)
    
    st_folium(m, width=1000, height=500)
    
    # D. Full Charts below
    st.subheader("Session Analysis")
    st.line_chart(df.set_index('seconds_elapsed')[['rate', 'speed_ms']])

else:
    st.info("Please upload both GPX and CSV files in the sidebar to start.")


# --- 4. Contact Form ---
st.markdown("---")
with st.expander("Contact & Feedback"):
    with st.form("contact_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1: name_input = st.text_input("Name")
        with col2: email_input = st.text_input("Contact Email")
        subject_input = st.text_input("Subject Header")
        message_input = st.text_area("Main Text")
        submitted = st.form_submit_button("Send Feedback")
        
        if submitted:
            if not (name_input and email_input and message_input):
                st.error("Please fill in fields.")
            else:
                status, txt = send_simple_email(name_input, email_input, subject_input, message_input)
                if status == 200: st.success("Sent!")
                else: st.error(f"Error {status}: {txt}")
