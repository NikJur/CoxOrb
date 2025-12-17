import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

def parse_gpx(file_buffer):
    """
    Parses a GPX file buffer and returns a DataFrame of coordinates.

    Parameters:
    -----------
    file_buffer : UploadedFile
        The GPX file object uploaded by the user.

    Returns:
    --------
    pd.DataFrame
        A DataFrame containing 'latitude' and 'longitude' columns.
    """
    # Parse the GPX file using gpxpy library
    gpx = gpxpy.parse(file_buffer)
    
    # Extract point data from tracks/segments
    data = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                data.append({
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'time': point.time
                })
    
    return pd.DataFrame(data)

def plot_metrics(df):
    """
    Generates a line chart for rowing metrics (Rate/Speed) from CSV data.

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame containing CoxOrb CSV data.
    """
    # Streamlit's native line chart is interactive by default
    # We assume standard CoxOrb columns; users may need to adjust column names
    # Common columns: 'Stroke Rate', 'Speed', 'Distance', 'Power'
    
    available_cols = [c for c in ['Rate', 'Speed', 'Power', 'Stroke Rate'] if c in df.columns]
    
    if available_cols:
        st.subheader("Performance Metrics")
        st.line_chart(df[available_cols])
    else:
        st.warning("Could not identify standard CoxOrb columns (Rate, Speed, Power).")
        st.write("Available columns:", df.columns.tolist())

# --- Main App Logic ---

st.title("CoxOrb Data Visualizer")
st.write("Upload your rowing data to view the route and analysis.")

# 1. File Uploaders
c1, c2 = st.columns(2)
uploaded_gpx = c1.file_uploader("Upload GPX", type=['gpx'])
uploaded_csv = c2.file_uploader("Upload CSV", type=['csv'])

# 2. Process and Plot GPX (Map)
if uploaded_gpx is not None:
    try:
        # Parse the GPX file
        track_df = parse_gpx(uploaded_gpx)
        
        st.subheader("Rowing Route")
        
        # Center map on the starting point
        start_location = [track_df['latitude'].iloc[0], track_df['longitude'].iloc[0]]
        m = folium.Map(location=start_location, zoom_start=14)
        
        # Draw the route line (PolyLine)
        coordinates = list(zip(track_df['latitude'], track_df['longitude']))
        folium.PolyLine(coordinates, color="blue", weight=2.5, opacity=1).add_to(m)
        
        # Render map in Streamlit
        st_folium(m, width=700, height=500)
        
    except Exception as e:
        st.error(f"Error processing GPX: {e}")

# 3. Process and Plot CSV (Stats)
if uploaded_csv is not None:
    try:
        # Load CSV into Pandas DataFrame
        # Skiprows might be needed depending on CoxOrb header format (often line 1 or 2)
        df = pd.read_csv(uploaded_csv)
        
        # Display raw data snapshot
        with st.expander("Raw Data View"):
            st.dataframe(df.head())
        
        # Plot the stats
        plot_metrics(df)
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
