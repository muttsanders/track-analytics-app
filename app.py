import streamlit as st
import pandas as pd
import sqlite3
import math

# ============================================================
# SETUP
# ============================================================
st.set_page_config(layout="wide", page_title="St. Xavier Track Reports")

@st.cache_resource
# --- THIS IS THE NEW, CORRECT CODE ---
import os
import sqlite3
import streamlit as st

@st.cache_resource
def get_connection():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Join the script directory with the relative path to the database
    db_path = os.path.join(script_dir, "data", "track_and_field.db")
    # Connect to the database
    return sqlite3.connect(db_path, check_same_thread=False)

# Your other code follows...
conn = get_connection()
# ... etc


conn = get_connection()

# Initialize session state for cross-tab navigation
if 'selected_athlete' not in st.session_state:
    st.session_state.selected_athlete = None

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def format_time(seconds):
    try:
        seconds = float(seconds)
        if pd.isna(seconds): return ""
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}:{remaining_seconds:05.2f}"
    except (ValueError, TypeError):
        return ""

def apply_all_styles(row):
    styles = [''] * len(row)
    is_pr = row.get("is_pr_flag", False)
    lap_values = {k: v for k, v in row.items() if 'Lap ' in k and isinstance(v, (int, float)) and pd.notna(v)}
    min_lap_val = min(lap_values.values()) if lap_values else None
    max_lap_val = max(lap_values.values()) if lap_values else None
    for i, col_name in enumerate(row.index):
        if is_pr and (col_name == 'Time' or col_name == 'Final Time'):
            styles[i] = 'background-color: #FFDAB9; color: #A0522D;'
        elif 'Lap ' in str(col_name):
            cell_value = row[col_name]
            if pd.notna(cell_value):
                if cell_value == min_lap_val:
                    styles[i] = 'background-color: #D4EDDA; color: #155724;'
                elif cell_value == max_lap_val:
                    styles[i] = 'background-color: #F8D7DA; color: #721C24;'
    return styles

def highlight_laps_only(df):
    df_styled = df.copy()
    lap_cols = [col for col in df_styled.columns if 'Lap' in col]
    if not lap_cols: return df_styled.style
    format_dict = {col: "{:.2f}" for col in lap_cols}
    return df_styled.style.format(format_dict).highlight_min(
        subset=lap_cols, axis=1, props='background-color: #D4EDDA; color: #155724;'
    ).highlight_max(
        subset=lap_cols, axis=1, props='background-color: #F8D7DA; color: #721C24;'
    )

# ============================================================
# MAIN APP UI
# ============================================================
st.title("St. Xavier Track & Field Analytics")
tab1, tab2, tab3 = st.tabs(["St. X Meet Report", "Athlete Report", "Meet Results (All Teams)"])

# ============================================================
# TAB 1: ST. X MEET REPORT
# ============================================================
with tab1:
    st.header("St. Xavier Performance Report")
    selected_race_id_tab1 = None
    try:
        location_filter_tab1 = st.radio("Filter by Location:", ('All', 'Indoor', 'Outdoor'), horizontal=True, key='location_filter_tab1')
        race_list_query_tab1 = "SELECT DISTINCT race_id, race_date, race_name FROM v_all_results"
        params_tab1 = []
        if location_filter_tab1 != 'All':
            race_list_query_tab1 += " WHERE location = ?"
            params_tab1.append(location_filter_tab1)
        race_list_query_tab1 += " ORDER BY race_date DESC"
        race_list_df_tab1 = pd.read_sql_query(race_list_query_tab1, conn, params=tuple(params_tab1))
        if not race_list_df_tab1.empty:
            race_list_df_tab1['display_name'] = race_list_df_tab1['race_date'] + " | " + race_list_df_tab1['race_name']
            race_id_map_tab1 = pd.Series(race_list_df_tab1.race_id.values, index=race_list_df_tab1.display_name).to_dict()
            selected_display_name_tab1 = st.selectbox("Select a Meet (Date | Name)", options=race_list_df_tab1['display_name'].tolist(), key='meet_select_tab1')
            if selected_display_name_tab1:
                selected_race_id_tab1 = race_id_map_tab1[selected_display_name_tab1]
                selected_race_date = race_list_df_tab1[race_list_df_tab1['race_id'] == selected_race_id_tab1]['race_date'].iloc[0]
        else:
            st.warning(f"No '{location_filter_tab1}' meets found.")
    except Exception as e:
        st.error(f"Could not load meet list: {e}")
        st.stop()

    if selected_race_id_tab1:
        query_tab1 = "SELECT * FROM v_all_results WHERE race_id = ? AND team_name_adj = 'St Xavier (KY)'"
        race_df_tab1 = pd.read_sql_query(query_tab1, conn, params=(selected_race_id_tab1,))
        
        if not race_df_tab1.empty:
            athletes_in_meet = race_df_tab1['competitor_name'].dropna().unique().tolist()
            pr_df = pd.DataFrame()

            if athletes_in_meet:
                # --- FIX #2: This now correctly formats the parameters for the PR query ---
                pr_query = f"SELECT competitor_name, event, MIN(total_time_sec) as pr_sec FROM v_all_results WHERE competitor_name IN ({','.join('?' for _ in athletes_in_meet)}) AND race_date < ? GROUP BY competitor_name, event"
                params_for_pr = tuple(athletes_in_meet + [selected_race_date])
                pr_df = pd.read_sql_query(pr_query, conn, params=params_for_pr)
                # --- END OF FIX ---

            custom_event_order = ['800 Meters', '1600 Meters', '1 Mile', '3200 Meters', '2 Miles', '4x400 Relay', '4x800 Relay']
            events_present = race_df_tab1['event'].unique()
            final_sorted_events = [e for e in custom_event_order if e in events_present] + sorted([e for e in events_present if e not in custom_event_order])
            
            for event in final_sorted_events:
                st.subheader(event)
                event_df = race_df_tab1[race_df_tab1['event'] == event].copy()
                if not pr_df.empty:
                    event_df = pd.merge(event_df, pr_df, on=['competitor_name', 'event'], how='left')
                else:
                    event_df['pr_sec'] = None
                
                event_df['is_pr_flag'] = (event_df['pr_sec'].notna()) & (event_df['total_time_sec'] < event_df['pr_sec'])
                event_df['Previous PR'] = event_df['pr_sec'].apply(format_time)
                
                cols_to_display = ['competitor_name', 'Previous PR', 'place_in_level', 'total_time_text']
                rename_map = {'competitor_name': 'Athlete', 'place_in_level': 'Place', 'total_time_text': 'Time'}
                
                for i in range(1, 17):
                    col_name = f'split{i}'
                    if col_name in event_df.columns and event_df[col_name].notna().any():
                        cols_to_display.append(col_name)
                        rename_map[col_name] = f'Lap {i}'
                
                if 'split8' in cols_to_display and ('3200' in event or '2 Mile' in event):
                    event_df['mile1_time_sec'] = event_df[['split1', 'split2', 'split3', 'split4']].sum(axis=1)
                    event_df['Mile 1 Time'] = event_df['mile1_time_sec'].apply(format_time)
                    cols_to_display.insert(4, 'Mile 1 Time')
                    rename_map['total_time_text'] = 'Final Time'

                cols_to_display.append('is_pr_flag')
                display_df = event_df[cols_to_display].rename(columns=rename_map)
                
                lap_cols = [col for col in display_df.columns if 'Lap ' in str(col)]
                for col in lap_cols:
                    display_df[col] = pd.to_numeric(display_df[col], errors='coerce')
                
                format_dict = {col: "{:.2f}" for col in lap_cols}
                styler = display_df.style.apply(apply_all_styles, axis=1).format(format_dict)
                st.dataframe(styler, hide_index=True, use_container_width=True, column_config={"is_pr_flag": None})
                
                st.write("---")
                event_athletes = event_df['competitor_name'].dropna().unique().tolist()
                if event_athletes:
                    col1, col2 = st.columns([1, 3])
                    athlete_to_view = col1.selectbox("View full report for athlete:", options=event_athletes, key=f"select_{selected_race_id_tab1}_{event}", label_visibility="collapsed")
                    if col2.button(f"Go to {athlete_to_view}'s Report", key=f"btn_{selected_race_id_tab1}_{event}"):
                        st.session_state.selected_athlete = athlete_to_view
                        st.info(f"'{athlete_to_view}' selected. Click the 'Athlete Report' tab to see their profile.")
                st.write("")
        else:
            st.warning(f"No results for St. Xavier in this meet.")

# ============================================================
# TAB 2: ATHLETE REPORT
# ============================================================
with tab2:
    st.header("Individual Athlete Report")
    try:
        athlete_query = "SELECT DISTINCT competitor_name FROM v_all_results WHERE team_name_adj = 'St Xavier (KY)' ORDER BY competitor_name ASC"
        athlete_list_df = pd.read_sql_query(athlete_query, conn)
        athlete_names = athlete_list_df['competitor_name'].tolist()
        try:
            default_index = athlete_names.index(st.session_state.selected_athlete)
        except (ValueError, TypeError):
            default_index = 0
        selected_athlete = st.selectbox("Select an Athlete", options=athlete_names, index=default_index, key='athlete_select_tab2')
    except Exception as e:
        st.error(f"Could not load athlete list: {e}")
        st.stop()
    if selected_athlete:
        st.header(f"{selected_athlete}")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Indoor Personal Records")
            pr_indoor_query = "SELECT event, MIN(total_time_sec) as mark FROM v_all_results WHERE competitor_name = ? AND location = 'Indoor' GROUP BY event ORDER BY event"
            pr_indoor_df = pd.read_sql_query(pr_indoor_query, conn, params=(selected_athlete,))
            if not pr_indoor_df.empty:
                pr_indoor_df['Mark'] = pr_indoor_df['mark'].apply(format_time)
                st.dataframe(pr_indoor_df[['event', 'Mark']].rename(columns={'event':'Event'}), hide_index=True, use_container_width=True)
            else:
                st.write("No indoor records found.")
        with col2:
            st.subheader("Outdoor Personal Records")
            pr_outdoor_query = "SELECT event, MIN(total_time_sec) as mark FROM v_all_results WHERE competitor_name = ? AND location = 'Outdoor' GROUP BY event ORDER BY event"
            pr_outdoor_df = pd.read_sql_query(pr_outdoor_query, conn, params=(selected_athlete,))
            if not pr_outdoor_df.empty:
                pr_outdoor_df['Mark'] = pr_outdoor_df['mark'].apply(format_time)
                st.dataframe(pr_outdoor_df[['event', 'Mark']].rename(columns={'event':'Event'}), hide_index=True, use_container_width=True)
            else:
                st.write("No outdoor records found.")
        st.divider()
        st.subheader("All Results")
        all_results_base_query = "SELECT race_date, race_name, event, location, total_time_text, place_in_level FROM v_all_results WHERE competitor_name = ?"
        final_query = all_results_base_query + " ORDER BY race_date DESC"
        all_results_df = pd.read_sql_query(final_query, conn, params=(selected_athlete,))
        if not all_results_df.empty:
            display_df = all_results_df.rename(columns={'race_date': 'Date', 'race_name': 'Meet', 'event': 'Event', 'location': 'Location', 'total_time_text': 'Mark', 'place_in_level': 'Place'})
            st.dataframe(display_df, hide_index=True, use_container_width=True)
        else:
            st.warning("No results found for this athlete.")

# ============================================================
# TAB 3: MEET RESULTS (ALL TEAMS)
# ============================================================
with tab3:
    st.header("Full Meet Results")
    selected_race_id_tab3 = None
    try:
        location_filter_tab3 = st.radio("Filter by Location:", ('All', 'Indoor', 'Outdoor'), horizontal=True, key='location_filter_tab3')
        race_list_query_tab3 = "SELECT DISTINCT race_id, race_date, race_name FROM v_all_results"
        params_tab3 = []
        if location_filter_tab3 != 'All':
            race_list_query_tab3 += " WHERE location = ?"
            params_tab3.append(location_filter_tab3)
        race_list_query_tab3 += " ORDER BY race_date DESC"
        race_list_df_tab3 = pd.read_sql_query(race_list_query_tab3, conn, params=tuple(params_tab3))
        if not race_list_df_tab3.empty:
            race_list_df_tab3['display_name'] = race_list_df_tab3['race_date'] + " | " + race_list_df_tab3['race_name']
            race_id_map_tab3 = pd.Series(race_list_df_tab3.race_id.values, index=race_list_df_tab3.display_name).to_dict()
            selected_display_name_tab3 = st.selectbox("Select a Meet (Date | Name)", options=race_list_df_tab3['display_name'].tolist(), key='meet_select_tab3')
            if selected_display_name_tab3:
                selected_race_id_tab3 = race_id_map_tab3[selected_display_name_tab3]
        else:
            st.warning(f"No '{location_filter_tab3}' meets found.")
    except Exception as e:
        st.error(f"Could not load meet list for Tab 3: {e}")
        st.stop()
    if selected_race_id_tab3:
        query_tab3 = "SELECT * FROM v_all_results WHERE race_id = ?"
        race_df_tab3 = pd.read_sql_query(query_tab3, conn, params=(selected_race_id_tab3,))
        if not race_df_tab3.empty:
            custom_event_order = ['800 Meters', '1600 Meters', '1 Mile', '3200 Meters', '2 Miles', '4x400 Relay', '4x800 Relay']
            events_present_tab3 = race_df_tab3['event'].unique()
            final_sorted_events_tab3 = [e for e in custom_event_order if e in events_present_tab3] + sorted([e for e in events_present_tab3 if e not in custom_event_order])
            event_filter_options = ['All'] + final_sorted_events_tab3
            selected_event = st.radio("Filter by Event:", options=event_filter_options, horizontal=True, key='event_filter_tab3')
            events_to_display = final_sorted_events_tab3 if selected_event == 'All' else [selected_event]
            for event in events_to_display:
                st.subheader(event)
                event_df_tab3_event = race_df_tab3[race_df_tab3['event'] == event].copy()
                cols_to_display = ['competitor_name', 'team_name_adj', 'place_in_level', 'total_time_text']
                rename_map = {'competitor_name': 'Athlete', 'team_name_adj': 'Team', 'place_in_level': 'Place', 'total_time_text': 'Time'}
                for i in range(1, 17):
                    col_name = f'split{i}'
                    if col_name in event_df_tab3_event.columns and event_df_tab3_event[col_name].notna().any():
                        cols_to_display.append(col_name)
                        rename_map[col_name] = f'Lap {i}'
                if 'split8' in cols_to_display and ('3200' in event or '2 Mile' in event):
                    event_df_tab3_event['mile1_time_sec'] = event_df_tab3_event[['split1', 'split2', 'split3', 'split4']].sum(axis=1)
                    event_df_tab3_event['Mile 1 Time'] = event_df_tab3_event['mile1_time_sec'].apply(format_time)
                    cols_to_display.insert(3, 'Mile 1 Time')
                    rename_map['total_time_text'] = 'Final Time'
                display_df = event_df_tab3_event[cols_to_display].rename(columns=rename_map)
                st.dataframe(highlight_laps_only(display_df), hide_index=True, use_container_width=True)

