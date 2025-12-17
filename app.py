import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import requests #for sending the feedback data to email service

def parse_time_str(time_str):
    """
    Parses time strings like '00:15:30' or '15:30.5' into total seconds.
    Used for the CSV 'Elapsed Time' column.
    round to the nearest integer
    """
    try:
        if pd.isna(time_str): return 0
        # If it's already a number, return the rounded integer
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

def parse_gpx(file_buffer):
    """
    Parses a GPX file buffer and returns a DataFrame of coordinates. + add "seconds_elapsed" column to compare with csv files

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
    df = pd.DataFrame(data)

    #Convert absolute time to elapsed seconds
    if not df.empty and 'time' in df.columns:
        # Ensure time is in datetime format (gpxpy usually does this, but being safe)
        df['time'] = pd.to_datetime(df['time'])
        
        # Get the start time (first entry)
        start_time = df['time'].iloc[0]
        
        # Calculate difference and convert to total seconds
        df['seconds_elapsed'] = (df['time'] - start_time).dt.total_seconds()
    
    return df

def plot_metrics(df):
    """
    Generates a line chart for rowing metrics (Rate/Speed) from CSV data.
    Sets 'Distance' as the X-axis if available.
    
    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame containing CoxOrb CSV data.
    """
    # Streamlit's native line chart is interactive by default
    #1 Clean column names (remove extra spaces)
    df.columns = [c.strip() for c in df.columns]

    #2 Define the exact columns we want to plot based on your file format
    #file format: Distance, Elapsed Time, Stroke Count, Rate, Check, Speed (mm:ss/500m), Speed (m/s), Distance/Stroke
    wanted_cols = ['Rate', 'Speed (m/s)', 'Distance/Stroke']
    
    #3 Filter for columns that actually exist in the file
    cols_to_plot = [c for c in wanted_cols if c in df.columns]
    
    if cols_to_plot:
        st.subheader("Performance Metrics")
        
        # If 'Distance' exists, set it as the index (X-axis)
        if 'Distance' in df.columns:
            st.write("X-axis: Distance (m)")
            # We explicitly set the index to Distance for the chart
            chart_data = df.set_index('Distance')[cols_to_plot]
            st.line_chart(chart_data)
        
        # If no Distance, try 'Elapsed Time'
        elif 'Elapsed Time' in df.columns:
            st.write("X-axis: Time")
            chart_data = df.set_index('Elapsed Time')[cols_to_plot]
            st.line_chart(chart_data)
            
        # Fallback to Row Number (Stroke Count)
        else:
            st.write("X-axis: Stroke Number")
            st.line_chart(df[cols_to_plot])

def send_simple_email(name, email, subject, message):
    """
    Sends the user feedback to the developer via the Formspree API.

    Parameters:
    -----------
    name : str
        The name of the user submitting feedback.
    email : str
        The user's email address for replies.
    subject : str
        The subject header of the message.
    message : str
        The main body of the feedback text.

    Returns:
    --------
    int
        The HTTP status code of the request (200 indicates success).
    """
    # Replace 'YOUR_FORMSPREE_ENDPOINT' below with your actual URL
    # Example format: "https://formspree.io/f/xyzkqwe"
    api_url = "https://formspree.io/f/xpwvvnkn"

    payload = {
        "name": name,
        "_replyto": email,
        "_subject": subject,
        "message": message
    }

    # Post the data to the API
    response = requests.post(api_url, data=payload)
    return response.status_code, response.text

# --- Main App Logic ---

st.title("CoxOrb Data Visualiser")
st.write("Upload your rowing data to view the route and analysis.")

# 1. File Uploaders
c1, c2 = st.columns(2)
uploaded_gpx = c1.file_uploader("Upload GPX", type=['gpx'])
uploaded_csv = c2.file_uploader("Upload CSV (we recommend GRAPH over SPLIT)", type=['csv'])

# Holders for dataframes so we can access them later for the combined map
gpx_df = None
csv_df = None

# 2. Process and Plot GPX (Map + Raw View)
if uploaded_gpx is not None:
    try:
        # Parse the GPX file
        gpx_df = parse_gpx(uploaded_gpx)

        st.subheader("Rowing Route")
        
        # Center map on the starting point
        start_location = [gpx_df['latitude'].iloc[0], gpx_df['longitude'].iloc[0]]
        m = folium.Map(location=start_location, zoom_start=14)
        
        # Draw the route line (PolyLine)
        coordinates = list(zip(gpx_df['latitude'], gpx_df['longitude']))
        folium.PolyLine(coordinates, color="blue", weight=2.5, opacity=1).add_to(m)
        
        # Render map in Streamlit
        st_folium(m, width=500, height=500)

        #View Raw GPX Data 
        with st.expander("📂 Raw GPX Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the GPX file:")
            st.dataframe(gpx_df)
        
    except Exception as e:
        st.error(f"Error processing GPX: {e}")

# 3. Process and Plot CSV (Stats)
if uploaded_csv is not None:
    try:
        # Load CSV into Pandas DataFrame
        # header=1 tells pandas to ignore the first row ("COXORB Performance Data...") and use the second row as the actual column headers.
        csv_df = pd.read_csv(uploaded_csv, header=1)

        # Clean column names
        csv_df.columns = [c.strip() for c in csv_df.columns]

        #Convert 'Elapsed Time' string to 'seconds_elapsed' float ---
        if 'Elapsed Time' in csv_df.columns:
            csv_df['seconds_elapsed'] = csv_df['Elapsed Time'].apply(parse_time_str)
        
        # Display raw data snapshot
        with st.expander("📂 Raw CSV Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the CSV file:")
            st.dataframe(csv_df)
        
        # Plot the stats
        plot_metrics(csv_df)
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")

# 4.  --- Interactive Replay Map (Combined Data) ---

if gpx_df is not None and csv_df is not None:
    st.markdown("---")
    st.subheader("Interactive Replay")
    st.write("Move the slider to see stats and location at that specific moment.")

    try:
        # A. PREPARE DATA
        # 1. Drop rows where seconds_elapsed is NaN
        gpx_clean = gpx_df.dropna(subset=['seconds_elapsed']).copy()
        csv_clean = csv_df.dropna(subset=['seconds_elapsed']).copy()
        
        # 2. Force both to Integer
        gpx_clean['seconds_elapsed'] = gpx_clean['seconds_elapsed'].astype(int)
        csv_clean['seconds_elapsed'] = csv_clean['seconds_elapsed'].astype(int)
        
        # 3. Sort
        gpx_sorted = gpx_clean.sort_values('seconds_elapsed')
        csv_sorted = csv_clean.sort_values('seconds_elapsed')

        # B. MERGE
        merged_df = pd.merge_asof(
            csv_sorted, 
            gpx_sorted[['seconds_elapsed', 'latitude', 'longitude']], 
            on='seconds_elapsed', 
            direction='nearest',
            tolerance=5 
        )

        merged_df = merged_df.dropna(subset=['latitude', 'longitude'])

        if not merged_df.empty:
            # --- VIEWPORT CALCULATION (Run Once) ---
            # We calculate the boundaries of the ENTIRE route.
            # This ensures the map stays fixed while the dot moves.
            min_lat, max_lat = gpx_df['latitude'].min(), gpx_df['latitude'].max()
            min_lon, max_lon = gpx_df['longitude'].min(), gpx_df['longitude'].max()
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
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
                # 1. Center map on the COURSE CENTER (not the boat)
                # 2. Set bounds to fit the whole course
                m_interactive = folium.Map(location=[center_lat, center_lon], zoom_start=14)
                
                # Fit the map to the course boundaries
                m_interactive.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

                # Full Path (Gray)
                folium.PolyLine(
                    list(zip(gpx_df['latitude'], gpx_df['longitude'])), 
                    color="gray", weight=2, opacity=0.5
                ).add_to(m_interactive)

                # Path So Far (Blue)
                current_time_sec = current_row['seconds_elapsed']
                path_so_far = gpx_df[gpx_df['seconds_elapsed'] <= current_time_sec]
                if not path_so_far.empty:
                    folium.PolyLine(
                        list(zip(path_so_far['latitude'], path_so_far['longitude'])), 
                        color="blue", weight=4, opacity=1
                    ).add_to(m_interactive)

                # Boat Dot
                boat_loc = [current_row['latitude'], current_row['longitude']]
                folium.CircleMarker(
                    location=boat_loc, radius=8, color="red", fill=True, fill_color="red"
                ).add_to(m_interactive)

                st_folium(m_interactive, width=800, height=500, key="interactive_map")
        else:
            st.warning("Could not link CSV and GPX data. Please check if the timestamps align.")
            
    except Exception as e:
        st.error(f"Error in interactive section: {e}")


# 5. Feedback Part on the Bottom of the page:
st.markdown("---")  # Horizontal rule for visual separation

# 5.1. Developer Credits
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
st.write("Have suggestions? Send a message directly using the form below.")

# 5.2. Contact Form
with st.form("contact_form", clear_on_submit=True):
    # Layout the input fields
    col1, col2 = st.columns(2)
    with col1:
        name_input = st.text_input("Name")
    with col2:
        email_input = st.text_input("Contact Email")
    
    subject_input = st.text_input("Subject Header")
    message_input = st.text_area("Main Text")
    
    # Form submit button
    submitted = st.form_submit_button("Send Feedback")

    if submitted:
        # Basic validation to ensure fields are not empty
        if not (name_input and email_input and message_input):
            st.error("Please fill in your name, email, and a message.")
        else:
            # Get both status and response text
            status, response_text = send_simple_email(name_input, email_input, subject_input, message_input)

            if status == 200:
                st.success("Message sent successfully! Thank you for your feedback; we will get back to you as soon as possible.")
            else:
                st.error(f"Failed to send. Status Code: {status}")
                with st.expander("See Error Details"):
                    st.text(response_text)
