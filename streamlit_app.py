import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
import folium
from streamlit_folium import folium_static
import io

st.set_page_config(layout="wide", page_title="Water Quality Data Explorer")

st.title("Water Quality Data Explorer")

# Function to load and preprocess data
@st.cache_data
def load_data(result_file, station_file):
    # Load data
    results_df = pd.read_csv(result_file)
    stations_df = pd.read_csv(station_file)
    
    # Convert date column to datetime
    results_df['ActivityStartDate'] = pd.to_datetime(results_df['ActivityStartDate'])
    
    # Ensure ResultMeasureValue is numeric
    results_df['ResultMeasureValue'] = pd.to_numeric(results_df['ResultMeasureValue'], errors='coerce')
    
    return results_df, stations_df

# File upload section
st.header("Upload Data Files")
col1, col2 = st.columns(2)

with col1:
    result_file = st.file_uploader("Upload narrowresult.csv", type=["csv"])
    
with col2:
    station_file = st.file_uploader("Upload station.csv", type=["csv"])

# Main app logic
if result_file is not None and station_file is not None:
    # Load data
    results_df, stations_df = load_data(result_file, station_file)
    
    # Get list of unique contaminants
    contaminants = sorted(results_df['CharacteristicName'].unique())
    
    # Sidebar for filters
    st.sidebar.header("Filters")
    
    # Contaminant selection
    selected_contaminant = st.sidebar.selectbox(
        "Select Contaminant", 
        contaminants
    )
    
    # Filter data for selected contaminant
    filtered_results = results_df[results_df['CharacteristicName'] == selected_contaminant]
    
    if filtered_results.empty:
        st.warning(f"No data found for {selected_contaminant}")
    else:
        # Get min and max values for the selected contaminant
        min_value = float(filtered_results['ResultMeasureValue'].min())
        max_value = float(filtered_results['ResultMeasureValue'].max())
        
        # Value range slider
        value_range = st.sidebar.slider(
            f"Range of {selected_contaminant} Values",
            min_value, max_value, (min_value, max_value)
        )
        
        # Date range slider
        min_date = filtered_results['ActivityStartDate'].min().date()
        max_date = filtered_results['ActivityStartDate'].max().date()
        
        date_range = st.sidebar.date_input(
            "Date Range",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        
        # Ensure we have two dates
        if len(date_range) == 2:
            start_date, end_date = date_range
            
            # Filter data based on selected ranges
            filtered_data = filtered_results[
                (filtered_results['ResultMeasureValue'] >= value_range[0]) &
                (filtered_results['ResultMeasureValue'] <= value_range[1]) &
                (filtered_results['ActivityStartDate'].dt.date >= start_date) &
                (filtered_results['ActivityStartDate'].dt.date <= end_date)
            ]
            
            # Get unique stations in filtered data
            unique_stations = filtered_data['MonitoringLocationIdentifier'].unique()
            
            # Filter stations dataframe to only include stations in our filtered data
            filtered_stations = stations_df[stations_df['MonitoringLocationIdentifier'].isin(unique_stations)]
            
            # Display results
            st.header(f"Results for {selected_contaminant}")
            
            # Display stats
            st.subheader("Statistics")
            col1, col2, col3 = st.columns(3)
            col1.metric("Number of Measurements", len(filtered_data))
            col2.metric("Number of Stations", len(unique_stations))
            col3.metric("Date Range", f"{start_date} to {end_date}")
            
            # Create two columns for map and trend
            map_col, trend_col = st.columns([1, 1])
            
            with map_col:
                st.subheader("Station Map")
                
                # Check if we have latitude and longitude in the stations data
                if 'LatitudeMeasure' in filtered_stations.columns and 'LongitudeMeasure' in filtered_stations.columns:
                    # Create a map centered at the mean lat/long
                    m = folium.Map(
                        location=[
                            filtered_stations['LatitudeMeasure'].mean(),
                            filtered_stations['LongitudeMeasure'].mean()
                        ],
                        zoom_start=10
                    )
                    
                    # Add markers for each station
                    for idx, row in filtered_stations.iterrows():
                        # Get the average value for this station
                        station_data = filtered_data[filtered_data['MonitoringLocationIdentifier'] == row['MonitoringLocationIdentifier']]
                        avg_value = station_data['ResultMeasureValue'].mean()
                        
                        # Create popup text
                        popup_text = f"""
                        <b>Station:</b> {row['MonitoringLocationIdentifier']}<br>
                        <b>Name:</b> {row.get('MonitoringLocationName', 'N/A')}<br>
                        <b>Average {selected_contaminant}:</b> {avg_value:.2f}<br>
                        <b>Measurements:</b> {len(station_data)}
                        """
                        
                        # Add marker
                        folium.Marker(
                            location=[row['LatitudeMeasure'], row['LongitudeMeasure']],
                            popup=folium.Popup(popup_text, max_width=300),
                            tooltip=row['MonitoringLocationIdentifier']
                        ).add_to(m)
                    
                    # Display the map
                    folium_static(m)
                else:
                    st.error("Station data does not contain latitude and longitude information.")
            
            with trend_col:
                st.subheader("Trend Over Time")
                
                # Create a figure for the trend
                fig = plt.figure(figsize=(10, 6))
                
                # Group by station and plot
                for station, group in filtered_data.groupby('MonitoringLocationIdentifier'):
                    group_sorted = group.sort_values('ActivityStartDate')
                    plt.plot(
                        group_sorted['ActivityStartDate'], 
                        group_sorted['ResultMeasureValue'], 
                        'o-', 
                        label=station,
                        alpha=0.7
                    )
                
                plt.xlabel('Date')
                plt.ylabel(f'{selected_contaminant} Value')
                plt.title(f'{selected_contaminant} Trend Over Time')
                plt.grid(True)
                plt.xticks(rotation=45)
                
                # Only show legend if there are not too many stations
                if len(unique_stations) <= 10:
                    plt.legend(title='Station', bbox_to_anchor=(1.05, 1), loc='upper left')
                
                plt.tight_layout()
                st.pyplot(fig)
            
            # Show data table
            st.subheader("Data Table")
            st.dataframe(filtered_data[['MonitoringLocationIdentifier', 'ActivityStartDate', 'ResultMeasureValue']])
            
            # Download button for filtered data
            csv = filtered_data.to_csv(index=False)
            st.download_button(
                label="Download filtered data as CSV",
                data=csv,
                file_name=f"{selected_contaminant}_filtered_data.csv",
                mime="text/csv"
            )
