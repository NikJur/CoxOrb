<div align="center">
  <img src="logo.png" alt="CoxOrb Data Visualiser Logo" width="800">
</div>

# 🚣 CoxOrb Data Visualiser

**[Access the Web Application Here](https://coxorb.streamlit.app/)** (it might take a few seconds to wake up sometimes) 

A powerful, interactive web application for visualising and analysing rowing performance data. Built with Python and Streamlit, this tool combines GPS data (GPX) and performance metrics (CSV) to provide synchronised replay maps, deep-dive performance graphs, and audio-synced analysis for coxswains and coaches.

## ✨ Key Features
### 1. 🗺️ Route Visualisation
Upload GPX files to view the exact course steered on an interactive map.

Comparison Mode: Upload up to 3 different GPX tracks (e.g., different pieces or different days) to compare steering lines side-by-side (and make your trialling coxes' lives hell).

### 2. 📈 Performance Metrics
Upload CSV files (exported from CoxOrb or similar devices) to visualise critical rowing metrics.

Static Plot: High-resolution analysis.

Metrics Supported: Stroke Rate, Split (s/500m), Speed (m/s), Distance Per Stroke, and Check.

Multi-Select: Toggle specific metrics on or off to focus your analysis.

### 3. 🎬 Interactive Replay
Merge map and rowing data directly in the browser, letting you follow all essential metrics as you drag the slider.

Synchronised View: Watch the boat marker move on the map while a vertical line tracks the exact stroke on the performance chart.

Data Trimming: Includes "Crop Start" and "Crop End" sliders. This allows you to trim stationary periods at the beginning or end of a piece, automatically rescaling the graph axes to focus on the active rowing.

### 4. 🎧 Audio Analysis
Upload an audio recording (MP3/WAV) alongside your data.

Auto-Sync: The application synchronises the audio playback with the boat's position on the map.

Dashboard: Displays real-time stats (Rate, Split, Distance) that update as the audio plays.

### 5. 📝 Feedback
Found a bug or have a feature request? Use the Contact & Feedback form built directly into the bottom of the application! However, if you already find yourself on this GitHub repo - you might as well open an "issue", increasing your chances of a quick fix coming your way.


---
### 📂 Project Structure
app.py: The main entry point. Handles the Streamlit UI, file uploads, data parsing (GPX/CSV), caching logic, and the server-side calculations.

html_utils.py: Contains the complex HTML/JavaScript generators for the interactive components (Audio Player and Client-Side Replay). This keeps the main Python file clean.

---

## ⭐️ Support the Project
If this tool enhances your coxing, coaching, or rowing analysis, please consider giving this repository a star ⭐️. It costs nothing, helps track community engagement, and encourages future development and updates.
