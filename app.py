import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import requests #for sending the feedback data to email service
from folium.plugins import Fullscreen
import streamlit.components.v1 as components
from html_utils import generate_audio_map_html, generate_client_side_replay

#set format to wide desktop screen:
st.set_page_config(layout="wide", page_title="CoxOrb Data Visualiser")

#check:
try:
    from html_utils import generate_audio_map_html, generate_client_side_replay
except ImportError:
    st.error("Could not import 'html_utils.py'. Please make sure the file exists and is named correctly.")

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
    Allows user to select which metrics to plot.
    Generates a Dual-Axis line chart.
    Left Axis: Rate, Distance/Stroke, Check
    Right Axis (Inverted): Split (formatted as mm:ss.t)
    
    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame containing CoxOrb CSV data.
    """
    import altair as alt

    # 1. Clean column names (Remove the rename logic!)
    df.columns = [c.strip() for c in df.columns]

    # 2. Define Metrics (Include Speed AND Split)
    wanted_cols = ['Rate', 'Split (s/500m)', 'Speed (m/s)', 'Distance/Stroke', 'Check']
    available_cols = [c for c in wanted_cols if c in df.columns]

    # 3. Create Formatted Split Column for Tooltips (mm:ss.t)
    if 'Split (s/500m)' in df.columns:
        def fmt_split(secs):
            if pd.isna(secs) or secs <= 0: return "-"
            m = int(secs // 60)
            s = secs % 60
            return f"{m}:{s:04.1f}"
        
        df['Split_Formatted'] = df['Split (s/500m)'].apply(fmt_split)

    if available_cols:
        st.subheader("Performance Metrics (Static Plot)")
        
        # Default defaults: Rate and Split
        default_cols = [c for c in available_cols]
        if not default_cols: default_cols = available_cols[:1]

        cols_to_plot = st.multiselect(
            "Select metrics to plot (unselect Splits to alter the left Y-axis):", 
            options=available_cols, 
            default=default_cols
        )

        if cols_to_plot:
            # Determine X-axis
            if 'Distance' in df.columns:
                x_axis = 'Distance'
                x_title = "Distance (m)"
            elif 'Elapsed Time' in df.columns:
                x_axis = 'Elapsed Time'
                x_title = "Time"
            else:
                x_axis = 'index'
                df = df.reset_index()
                x_title = "Stroke Number"

            # --- BUILD ALTAIR LAYERS ---
            layers = []
            
            # 1. Handle "Split" (Right Axis, Inverted, Green)
            if 'Split (s/500m)' in cols_to_plot:
                split_layer = alt.Chart(df).mark_line(color='#2ca02c').encode(
                    x=alt.X(x_axis, title=x_title),
                    y=alt.Y('Split (s/500m)', 
                            title='Split (s/500m)',
                            scale=alt.Scale(reverse=True, zero=False), # Inverted
                            axis=alt.Axis(orient='right', titleColor='#2ca02c')), 
                    tooltip=[
                        alt.Tooltip(x_axis, title=x_title),
                        alt.Tooltip('Split_Formatted', title='Split (mm:ss.t)'),
                        alt.Tooltip('Split (s/500m)', title='Raw Seconds')
                    ]
                )
                layers.append(split_layer)

            # 2. Handle Other Metrics (Left Axis - Rate, Speed, etc.)
            # We filter out 'Split (s/500m)' so it doesn't appear on the left
            left_metrics = [c for c in cols_to_plot if c != 'Split (s/500m)']
            
            if left_metrics:
                # Melt data for left metrics
                left_data = df[[x_axis] + left_metrics].melt(x_axis, var_name='Metric', value_name='Value')
                
                left_layer = alt.Chart(left_data).mark_line().encode(
                    x=alt.X(x_axis, title=x_title),
                    y=alt.Y('Value', title=' / '.join(left_metrics), scale=alt.Scale(zero=False)),
                    color=alt.Color('Metric', legend=alt.Legend(orient='bottom')),
                    tooltip=[x_axis, 'Metric', 'Value']
                )
                layers.append(left_layer)

            if layers:
                # Combine layers
                combined_chart = alt.layer(*layers).resolve_scale(
                    y='independent'
                ).properties(
                    height=500,
                    width='container'
                ).interactive()

                st.altair_chart(combined_chart, use_container_width=True)
            else:
                st.info("Please select a metric.")
        else:
            st.info("Select at least one metric to view the plot.")
    else:
        st.warning("Could not identify standard CoxOrb columns for the graph.")

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


# --- Main App Logic ---

# Create 3 columns: empty (1), logo (2), empty (1) to center the image
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # Use the logo as the main title
    st.image("logo.png", use_container_width=True)

# 1. Handle Query Parameters for Demo Mode
# We check if the user clicked the link (URL has ?demo=true)
query_params = st.query_params
demo_mode = query_params.get("demo") == "true"

# 2. Display Intro Text with Link
if not demo_mode:
    st.markdown(
        """
        Upload your rowing data to view the route and analysis. 
        Upload both GPX and CSV files to enable the interactive slider replay. 
        Click **[here](?demo=true)** to access a pre-loaded *example*.
        """
    )
else:
    st.markdown(
        """
        **Viewing Demo Data.** Click **[here](?)** to return to upload mode.
        """
    )

# Holders for dataframes so we can access them later for the combined map
gpx_df = None
csv_df = None
gpx_bytes = None
csv_file = None
audio_bytes = None # Added for audio
audio_type = 'audio/m4a' # Default for demo

# 4. Logic: Either Load Demo Data OR Show Uploaders
if demo_mode:
    # --- DEMO MODE ---
    try:
        gpx_url = "https://raw.githubusercontent.com/NikJur/CoxOrb/refs/heads/main/demo_data/example.GPX"
        csv_url = "https://raw.githubusercontent.com/NikJur/CoxOrb/refs/heads/main/demo_data/example_GRAPH.CSV"
        audio_url = "https://raw.githubusercontent.com/NikJur/CoxOrb/refs/heads/main/demo_data/example_recording.m4a"
        
        with st.spinner("Downloading demo data..."):
            gpx_response = requests.get(gpx_url)
            csv_response = requests.get(csv_url)
            audio_r = requests.get(audio_url)
            
            if gpx_response.status_code == 200 and csv_response.status_code == 200:
                # GPX
                gpx_bytes = gpx_response.content
                #CSV
                # For CSV, we need a file-like object for pandas
                from io import StringIO
                csv_file = StringIO(csv_response.text)
                # AUDIO
                if audio_r.status_code == 200:
                    audio_bytes = audio_r.content
                    
                st.success("Demo data loaded successfully!")
            else:
                st.error("Could not download demo files from GitHub. Please check the URLs.")
    except Exception as e:
        st.error(f"Error loading demo: {e}")

else:
    # --- UPLOAD MODE ---
    c1, c2 = st.columns(2)
    uploaded_gpx = c1.file_uploader("Upload GPX", type=['gpx'])
    uploaded_csv = c2.file_uploader("Upload CSV", type=['csv'])

    # If user uploaded, populate the unified variables
    if uploaded_gpx is not None:
        gpx_bytes = uploaded_gpx.getvalue()
        
    if uploaded_csv is not None:
        csv_file = uploaded_csv

# 2. Process and Plot GPX (Map + Raw View)
if gpx_bytes is not None:
    try:
        # Parse the GPX file
        gpx_df = parse_gpx(gpx_bytes)

        st.subheader("Rowing Route")
        
        # Center map on the starting point
        start_location = [gpx_df['latitude'].iloc[0], gpx_df['longitude'].iloc[0]]
        m = folium.Map(location=start_location, zoom_start=14)
        
        # Draw the route line (PolyLine)
        coordinates = list(zip(gpx_df['latitude'], gpx_df['longitude']))
        folium.PolyLine(coordinates, color="blue", weight=2.5, opacity=1).add_to(m)

        # Add Fullscreen Button
        Fullscreen().add_to(m)
        
        # Render map in Streamlit
        st_folium(m, width=1200, height=550)

        #View Raw GPX Data 
        with st.expander("📂 Raw GPX Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the GPX file:")
            st.dataframe(gpx_df)
        
    except Exception as e:
        st.error(f"Error processing GPX: {e}")

# 3. Process and Plot CSV (Stats)
if csv_file is not None:
    try:
        # Reset pointer if it's a StringIO object from demo
        if hasattr(csv_file, 'seek'): csv_file.seek(0)
        # Load CSV into Pandas DataFrame
        # header=1 tells pandas to ignore the first row ("COXORB Performance Data...") and use the second row as the actual column headers.
        csv_df = pd.read_csv(csv_file, header=1)

        # Clean column names
        csv_df.columns = [c.strip() for c in csv_df.columns]

        #Convert 'Elapsed Time' string to 'seconds_elapsed' float ---
        if 'Elapsed Time' in csv_df.columns:
            csv_df['seconds_elapsed'] = csv_df['Elapsed Time'].apply(parse_time_str)

        #convert speed to splits
        if 'Speed (m/s)' in csv_df.columns:
        #Formula: 500 / Speed (m/s) = Seconds per 500m
        #use a lambda to handle division by zero or empty values safely
            csv_df['Split (s/500m)'] = csv_df['Speed (m/s)'].apply(lambda x: 500/x if (pd.notnull(x) and x > 0) else 0)
        
        # Display raw data snapshot
        with st.expander("📂 Raw CSV Data View (Click to expand)"):
            st.write("Here is the raw data extracted from the CSV file:")
            st.dataframe(csv_df)
        
        # Plot the stats
        plot_metrics(csv_df)
        
    except Exception as e:
        st.error(f"Error processing CSV: {e}")


# 4. --- Client Side HTML based interactive replay map ---

if gpx_df is not None and csv_df is not None:
    st.markdown("---")
    st.subheader("Interactive Replay")
    st.caption("This runs entirely in your browser. Drag the slider for instant feedback. Click on the graph legend items to select/deselect them. If there are stationary periods at the beginning or end of your recording, trim them with the sliders to rescale the y-axes.")

    try:
        # Re-merge using the cached function (instant)
        merged_df_client = merge_datasets(gpx_df, csv_df)
        
        if not merged_df_client.empty:
            # Generate HTML using the imported utility function
            replay_html = generate_client_side_replay(merged_df_client)
            
            # Render the HTML component
            components.html(replay_html, height=520)
        else:
            st.warning("Data could not be merged for the client-side view.")

    except Exception as e:
        st.error(f"Error in client-side section: {e}")
        

# 5. --- Audio Analysis Section ---
st.markdown("---")
st.header("Audio Analysis")

# if NOT in demo mode (or demo download failed), allow upload
if audio_bytes is None:
    st.write("Upload an audio recording (e.g., Cox recording) to play it in sync with the map.")
    uploaded_audio = st.file_uploader("Upload Audio File (MP3/WAV/M4A)", type=['mp3', 'wav', 'm4a', 'ogg'])
    
    if uploaded_audio:
        audio_bytes = uploaded_audio.getvalue()
        audio_type = uploaded_audio.type
else:
    st.write("Playing loaded audio in sync with the map.")

# Process Audio Logic
if gpx_df is not None and audio_bytes is not None:
    st.write("Loading audio player and map sync...")
    
    if 'seconds_elapsed' in gpx_df.columns:
        # Prepare the data for Audio Sync
        if csv_df is not None:
            # If CSV exists, merge stats ONTO the GPX data.
            # We use merge_asof with GPX as the left table to keep the high-frequency map points (1Hz)
            # while pulling in the closest available stats from the CSV.

            # Merge stats onto GPX
            # Ensure types match
            gpx_df['seconds_elapsed'] = gpx_df['seconds_elapsed'].astype(int)
            csv_df['seconds_elapsed'] = csv_df['seconds_elapsed'].astype(int)
            
            audio_data = pd.merge_asof(
                gpx_df.sort_values('seconds_elapsed'),
                csv_df.sort_values('seconds_elapsed'),
                on='seconds_elapsed',
                direction='nearest',
                tolerance=5
            )
        else:
            # If no CSV, just use the GPX data (stats will show as "--")
            audio_data = gpx_df

        # Generate HTML
        audio_html = generate_audio_map_html(audio_data, audio_bytes, audio.type)
        components.html(audio_html, height=600) # Increased height to fit stats + map + player
    else:
        st.error("GPX data does not have time info required for sync.")

# 5. Compare Two GPX Lines ---

st.markdown("---")
st.header("Compare GPX Lines")
st.write("Upload up to three different GPX files to compare their steering lines side-by-side.")

# Create 3 columns for uploaders
col_comp1, col_comp2, col_comp3 = st.columns(3)
comp_gpx_1 = col_comp1.file_uploader("Upload Track 1 (Blue)", type=['gpx'], key="comp1")
comp_gpx_2 = col_comp2.file_uploader("Upload Track 2 (Red)", type=['gpx'], key="comp2")
comp_gpx_3 = col_comp3.file_uploader("Upload Track 3 (Black)", type=['gpx'], key="comp3")

# List to store successfully parsed tracks
tracks_to_plot = []

# Parse available files
if comp_gpx_1:
    try:
        tracks_to_plot.append({'data': parse_gpx(comp_gpx_1), 'color': 'blue', 'name': 'Track 1'})
    except Exception as e:
        st.error(f"Error parsing Track 1: {e}")

if comp_gpx_2:
    try:
        tracks_to_plot.append({'data': parse_gpx(comp_gpx_2), 'color': 'red', 'name': 'Track 2'})
    except Exception as e:
        st.error(f"Error parsing Track 2: {e}")

if comp_gpx_3:
    try:
        tracks_to_plot.append({'data': parse_gpx(comp_gpx_3), 'color': 'black', 'name': 'Track 3'})
    except Exception as e:
        st.error(f"Error parsing Track 3: {e}")

if tracks_to_plot:
    try:
        # Calculate combined bounds for all uploaded tracks
        # We concatenate all latitude series and all longitude series to find absolute min/max
        all_lats = pd.concat([t['data']['latitude'] for t in tracks_to_plot])
        all_lons = pd.concat([t['data']['longitude'] for t in tracks_to_plot])
        
        min_lat, max_lat = all_lats.min(), all_lats.max()
        min_lon, max_lon = all_lons.min(), all_lons.max()
        
        sw = [min_lat, min_lon]
        ne = [max_lat, max_lon]
        
        # Create Map centered roughly in the middle
        m_compare = folium.Map(location=[(min_lat + max_lat)/2, (min_lon + max_lon)/2], zoom_start=13)
        m_compare.fit_bounds([sw, ne])

        # Add Fullscreen Button
        Fullscreen().add_to(m_compare)
        
        # Plot each track
        for track in tracks_to_plot:
            folium.PolyLine(
                list(zip(track['data']['latitude'], track['data']['longitude'])), 
                color=track['color'], weight=3, opacity=0.7, tooltip=track['name']
            ).add_to(m_compare)
        
        st_folium(m_compare, width=1200, height=500, key="compare_map")
        
        # Dynamic Legend
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


# 6. Feedback Part on the Bottom of the page:
st.markdown("---")  # Horizontal rule for visual separation

# 6.1. Developer Credits
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

# 6.2. Contact Form
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
