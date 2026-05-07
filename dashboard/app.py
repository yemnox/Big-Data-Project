import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 0. DASHBOARD CONFIGURATION
# ==========================================
st.set_page_config(page_title="Emissions Executive Dashboard", layout="wide")
st.title("🌍 Building Emissions Executive Dashboard")
st.markdown("Advanced analytics, KPIs, and distributions for building emissions.")

# ==========================================
# 1. DATA LOADING & TRANSFORMATION
# ==========================================
@st.cache_data
def load_and_transform_data():
    # Load dataset
    df = pd.read_csv("data.csv")
    
    # Clean data
    df.columns = df.columns.str.strip()
    df['Total_Emissions'] = pd.to_numeric(df['Total_Emissions'], errors='coerce').fillna(0)
    
    # Sort descending for analytical ranking
    df = df.sort_values(by='Total_Emissions', ascending=False).reset_index(drop=True)
    
    # CALCULATED FIELDS
    total_emissions = df['Total_Emissions'].sum()
    df['Percent_Contribution'] = (df['Total_Emissions'] / total_emissions) * 100
    df['Cumulative_Emissions_%'] = df['Percent_Contribution'].cumsum()
    df['Rank'] = df.index + 1
    
    # Emission Tier Classification
    def get_tier(val):
        if val < 100000: return 'Low (<100k)'
        elif val <= 1000000: return 'Medium (100k–1M)'
        elif val <= 5000000: return 'High (1M–5M)'
        else: return 'Critical (>5M)'
        
    df['Tier'] = df['Total_Emissions'].apply(get_tier)
    
    return df, total_emissions

df, total_emissions = load_and_transform_data()

# ==========================================
# 2. ADVANCED KPIs
# ==========================================
mean_emissions = df['Total_Emissions'].mean()
median_emissions = df['Total_Emissions'].median()
std_dev = df['Total_Emissions'].std()
max_em = df['Total_Emissions'].max()
min_em = df['Total_Emissions'].min()

top_5_pct = df.head(5)['Percent_Contribution'].sum()
pareto_count = len(df[df['Cumulative_Emissions_%'] < 80]) + 1
min_max_ratio = min_em / max_em if max_em > 0 else 0
top_vs_avg_ratio = max_em / mean_emissions if mean_emissions > 0 else 0
above_avg_count = len(df[df['Total_Emissions'] > mean_emissions])
below_avg_count = len(df[df['Total_Emissions'] <= mean_emissions])

# Display KPIs in rows
st.subheader("📊 Executive KPIs")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Median Emissions", f"{median_emissions:,.0f}", help="Reduces noise from massive emitters")
col1.metric("Avg (Mean) Emissions", f"{mean_emissions:,.0f}")
col1.metric("Standard Deviation", f"{std_dev:,.0f}", help="Spread/Inequality in emissions")

col2.metric("Emission Concentration (Top 5)", f"{top_5_pct:.1f}%", help="Contribution of top 5 building types")
col2.metric("80/20 Pareto Index", f"{pareto_count} Categories", help=f"Only {pareto_count} out of {len(df)} types generate 80% of emissions")
col2.metric("Min / Max Ratio", f"{min_max_ratio:.6f}")

col3.metric("Top Emitter vs Average", f"{top_vs_avg_ratio:.1f}x", help="Max compared to the mean")
col3.metric("Clean Categories", f"{below_avg_count}", help="Categories below average emissions")
col3.metric("Polluting Categories", f"{above_avg_count}", help="Categories above average emissions")

with col4:
    # Gauge Chart for Top 5 Concentration
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = top_5_pct,
        title = {'text': "Top 5 Contribution %"},
        gauge = {'axis': {'range': [0, 100]},
                 'bar': {'color': "darkred"},
                 'steps': [
                     {'range': [0, 50], 'color': "lightgreen"},
                     {'range': [50, 80], 'color': "gold"},
                     {'range': [80, 100], 'color': "salmon"}]}))
    fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

st.divider()

# ==========================================
# 3. VISUALIZATIONS
# ==========================================

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.subheader("1. Pareto Chart (Cumulated 80/20 Impact)")
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df['Primary Property Type'], y=df['Total_Emissions'], name='Emissions', marker_color='rgb(55, 83, 109)'))
    fig_pareto.add_trace(go.Scatter(x=df['Primary Property Type'], y=df['Cumulative_Emissions_%'], name='Cumulative %', yaxis='y2', line=dict(color='red', width=3)))
    fig_pareto.update_layout(
        yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 105]),
        showlegend=False, margin=dict(t=30), height=400
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

with row1_col2:
    st.subheader("2. Treemap (Categorical Dominance)")
    fig_tree = px.treemap(df, path=['Tier', 'Primary Property Type'], values='Total_Emissions', 
                          color='Total_Emissions', color_continuous_scale='Reds')
    fig_tree.update_layout(margin=dict(t=30), height=400)
    st.plotly_chart(fig_tree, use_container_width=True)

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("3. Distribution (Histogram & Tiers)")
    fig_hist = px.histogram(df, x="Total_Emissions", nbins=50, 
                            color="Tier", title="Count of Categories by Emission Volume",
                            color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_hist.update_layout(margin=dict(t=30), height=400)
    st.plotly_chart(fig_hist, use_container_width=True)

with row2_col2:
    st.subheader("4. Bubble Chart (Executive View)")
    fig_bubble = px.scatter(df, x="Rank", y="Total_Emissions", 
                            size="Percent_Contribution", color="Tier", 
                            hover_name="Primary Property Type", size_max=60,
                            title="Rank vs Emissions (Bubble = % Contribution)")
    fig_bubble.update_layout(margin=dict(t=30), height=400)
    st.plotly_chart(fig_bubble, use_container_width=True)

row3_col1, row3_col2 = st.columns(2)

with row3_col1:
    st.subheader("5. Top 10 Emitters (Pie + Table hybrid)")
    top10 = df.head(10)
    fig_pie = px.pie(top10, values='Total_Emissions', names='Primary Property Type', hole=0.4,
                     title="Top 10 Categories Focus")
    fig_pie.update_layout(margin=dict(t=30), height=400)
    st.plotly_chart(fig_pie, use_container_width=True)

with row3_col2:
    st.subheader("6. Radar Chart (Avg vs Top Categories)")
    # Select average + 4 prominent arbitrary categories to compare
    radar_cats = df.head(5)['Primary Property Type'].tolist()
    radar_vals = df.head(5)['Total_Emissions'].tolist()
    
    # Append Mean for comparison
    radar_cats.append("AVERAGE (All)")
    radar_vals.append(mean_emissions)
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_vals, theta=radar_cats, fill='toself', name='Emissions Profile',
        line_color='tomato'
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=False, margin=dict(t=30), height=400)
    st.plotly_chart(fig_radar, use_container_width=True)

# ==========================================
# 4. HEATMAP DATA TABLE
# ==========================================
st.subheader("7. Deep-Dive Metrics Table (Heatmapped)")
# Using Pandas Styler to create heatmap effect natively in Streamlit
display_df = df[['Primary Property Type', 'Total_Emissions', 'Percent_Contribution', 'Cumulative_Emissions_%', 'Tier']].copy()
# Format percentages
display_df['Percent_Contribution'] = display_df['Percent_Contribution'].round(2)
display_df['Cumulative_Emissions_%'] = display_df['Cumulative_Emissions_%'].round(2)

styled_df = display_df.style.background_gradient(subset=['Total_Emissions', 'Percent_Contribution'], cmap='Reds')
st.dataframe(styled_df, use_container_width=True, height=400)