import streamlit as st
import pandas as pd
import gpxpy
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import requests #for sending the feedback data to email service

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
    return response.status_code

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


# 4. Feedback Part on the Bottom of the page:
st.markdown("---")  # Horizontal rule for visual separation

# 1. Developer Credits
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

# 2. Contact Form
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
            # Attempt to send the email
            status = send_simple_email(name_input, email_input, subject_input, message_input)

            if status == 200:
                st.success("Message sent successfully! Thank you for your feedback; we will get back to you as soon as possible.")
            else:
                # --- Debugging Code ---
                st.error(f"Error {status}: There was an issue sending your message.")
                #Rerun the function to get the text since we didn't return it (or modify the function)
                #Actually, let's just modify the function slightly to be safe, or simpler:
                st.write("Please check your Formspree dashboard or email.")
