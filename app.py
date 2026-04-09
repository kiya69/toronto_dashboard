import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
from plotly.colors import qualitative

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Business Location Recommendation - Toronto",
    layout="wide"
)

# --------------------------------------------------
# App title
# --------------------------------------------------
st.title("Business Location Recommendation - Toronto")

# --------------------------------------------------
# Data source
# Replace with the NEW Google Drive file ID
# --------------------------------------------------
FILE_ID = "1KxoJgSIGEGnHoLUTR7Vd1VyyT2fPQRtM"
CSV_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"

# --------------------------------------------------
# Cached data loader
# --------------------------------------------------
@st.cache_data(ttl=10)
def load_data():
    df = pd.read_csv(CSV_URL)
    return df

# --------------------------------------------------
# Manual refresh button
# --------------------------------------------------
if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# Load data
# --------------------------------------------------
df = load_data()

# --------------------------------------------------
# Basic cleanup
# --------------------------------------------------
df.columns = [col.strip() for col in df.columns]

required_cols = [
    "neighborhood_id",
    "total_active_businesses",
    "neighborhood_name",
    "latitude",
    "longitude",
    "population",
    "median_income",
    "Category",
    "category_business_count"
]

missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    st.error(f"Missing required columns in source data: {missing_cols}")
    st.stop()

# Convert numeric columns
numeric_cols = [
    "neighborhood_id",
    "total_active_businesses",
    "latitude",
    "longitude",
    "population",
    "median_income",
    "category_business_count"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(subset=required_cols)

def prettify_category(text):
    if pd.isna(text):
        return text

    mapping = {
        "TAKE-OUT OR RETAIL FOOD ESTABLISHMENT": "Take-Out or Retail Food Establishment",
        "EATING OR DRINKING ESTABLISHMENT": "Eating or Drinking Establishment",
        "PUBLIC GARAGE": "Public Garage",
        "HOLISTIC CENTRE": "Holistic Centre",
        "PERSONAL SERVICES SETTINGS": "Personal Services Settings",
        "COMMERCIAL PARKING LOT": "Commercial Parking Lot",
        "TAXICAB OWNER": "Taxicab Owner"
    }
    return mapping.get(text, str(text).title())

df["Category_Display"] = df["Category"].apply(prettify_category)

# --------------------------------------------------
# Helper function for normalization
# --------------------------------------------------
def normalize(series):
    max_val = series.max()
    min_val = series.min()
    if max_val == min_val:
        return pd.Series([1.0] * len(series), index=series.index)
    return (series - min_val) / (max_val - min_val)

# --------------------------------------------------
# Opportunity score calculation
# Weighted score:
# 35% total_active_businesses
# 25% category_business_count
# 20% population
# 20% median_income
# --------------------------------------------------
df["norm_total_businesses"] = normalize(df["total_active_businesses"])
df["norm_category_businesses"] = normalize(df["category_business_count"])
df["norm_population"] = normalize(df["population"])
df["norm_income"] = normalize(df["median_income"])

df["opportunity_score"] = (
    0.35 * df["norm_total_businesses"] +
    0.25 * df["norm_category_businesses"] +
    0.20 * df["norm_population"] +
    0.20 * df["norm_income"]
) * 100

df["opportunity_score"] = df["opportunity_score"].round(1)

# --------------------------------------------------
# High opportunity flag
# --------------------------------------------------
high_op_threshold = df["opportunity_score"].quantile(0.75)
df["high_opportunity_flag"] = df["opportunity_score"] >= high_op_threshold
# --------------------------------------------------
# Rule-based segmentation for storytelling
# --------------------------------------------------
def assign_cluster(score):
    if score >= 85:
        return "Underserved Opportunity Areas"
    elif score >= 70:
        return "Growing Commercial Areas"
    elif score >= 50:
        return "Balanced Residential Zones"
    else:
        return "High Density / Competitive"

df["cluster_name"] = df["opportunity_score"].apply(assign_cluster)

# --------------------------------------------------
# Dynamic category color generation
# No hardcoding
# --------------------------------------------------
unique_categories = sorted(df["Category_Display"].unique().tolist())

plotly_palette = (
    qualitative.Plotly +
    qualitative.Dark24 +
    qualitative.G10 +
    qualitative.T10
)

# Ensure enough colors
while len(plotly_palette) < len(unique_categories):
    plotly_palette = plotly_palette + plotly_palette

category_hex = {
    cat: plotly_palette[i]
    for i, cat in enumerate(unique_categories)
}

def hex_to_rgba(hex_color, alpha=160):
    hex_color = hex_color.lstrip("#")
    return [
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
        alpha
    ]

category_rgba = {
    cat: hex_to_rgba(color, alpha=160)
    for cat, color in category_hex.items()
}

# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
st.sidebar.header("Filters")

selected_neighborhoods = st.sidebar.multiselect(
    "Neighborhood",
    options=sorted(df["neighborhood_name"].unique()),
    default=sorted(df["neighborhood_name"].unique())
)

st.sidebar.markdown("### Business Type")

selected_categories = []

for category in unique_categories:
    color = category_hex.get(category, "#999999")

    col_swatch, col_check = st.sidebar.columns([1, 6])

    with col_swatch:
        st.markdown(
            f"""
            <div style="
                width: 16px;
                height: 16px;
                background-color: {color};
                border-radius: 3px;
                margin-top: 8px;
            "></div>
            """,
            unsafe_allow_html=True
        )

    with col_check:
        is_selected = st.checkbox(
            category,
            value=True,
            key=f"cat_{category}"
        )

    if is_selected:
        selected_categories.append(category)

income_range = st.sidebar.slider(
    "Median Income",
    min_value=int(df["median_income"].min()),
    max_value=int(df["median_income"].max()),
    value=(int(df["median_income"].min()), int(df["median_income"].max()))
)

only_high_opportunity = st.sidebar.checkbox(
    "Only high opportunity areas (score >= 80)",
    value=False
)

# --------------------------------------------------
# Apply filters
# --------------------------------------------------
filtered_df = df[
    (df["neighborhood_name"].isin(selected_neighborhoods)) &
    (df["Category_Display"].isin(selected_categories)) &
    (df["median_income"].between(income_range[0], income_range[1]))
].copy()

if only_high_opportunity:
    filtered_df = filtered_df[filtered_df["high_opportunity_flag"]]

if filtered_df.empty:
    st.warning("No data available with the selected filters.")
    st.stop()

# --------------------------------------------------
# Business explanation
# --------------------------------------------------
st.info(
    "Opportunity Score is a normalized composite indicator based on total business activity, "
    "category concentration, population, and median income."
)

# --------------------------------------------------
# KPI calculations
# --------------------------------------------------
top_category = (
    filtered_df["Category_Display"].mode()[0]
    if not filtered_df["Category_Display"].mode().empty
    else "N/A"
)

high_op_count = int(filtered_df["high_opportunity_flag"].sum())

top_area_name = (
    filtered_df.sort_values("opportunity_score", ascending=False)
    .iloc[0]["neighborhood_name"]
)

# --------------------------------------------------
# KPI row
# --------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Neighborhoods", len(filtered_df))
col2.metric("Total Businesses", int(filtered_df["total_active_businesses"].sum()))
col3.metric("Top Category", top_category)
col4.metric("High Opportunity Areas", high_op_count)

st.markdown("---")
st.success(f"Top opportunity area: {top_area_name}")

# --------------------------------------------------
# Prepare map data
# --------------------------------------------------
filtered_df["color"] = filtered_df["Category_Display"].map(
    lambda x: category_rgba.get(x, [180, 180, 180, 160])
)
filtered_df["radius"] = filtered_df["opportunity_score"] * 120

# --------------------------------------------------
# Map + Best Opportunity panel
# --------------------------------------------------
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Opportunity Map")

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position="[longitude, latitude]",
        get_radius="radius",
        get_fill_color="color",
        pickable=True,
        stroked=True,
        filled=True,
        radius_min_pixels=8,
        radius_max_pixels=45,
        line_width_min_pixels=1
    )

    view_state = pdk.ViewState(
        latitude=float(filtered_df["latitude"].mean()),
        longitude=float(filtered_df["longitude"].mean()),
        zoom=9,
        pitch=0
    )

    tooltip = {
        "html": """
            <b>{neighborhood_name}</b><br/>
            Opportunity Score: {opportunity_score}<br/>
            Category: {Category_Display}<br/>
            Cluster: {cluster_name}<br/>
            Population: {population}<br/>
            Median Income: ${median_income}<br/>
            Total Businesses: {total_active_businesses}<br/>
            Category Business Count: {category_business_count}
        """,
        "style": {
            "backgroundColor": "#111111",
            "color": "white",
            "border": "1px solid #cc3333"
        }
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip
    )

    st.pydeck_chart(deck)

with right_col:
    st.subheader("Best Opportunity")

    top = filtered_df.sort_values("opportunity_score", ascending=False).iloc[0]

    st.write(f"**Neighborhood:** {top['neighborhood_name']}")
    st.write(f"**Opportunity Score:** {top['opportunity_score']}")
    st.write(f"**Category:** {top['Category_Display']}")
    st.write(f"**Cluster:** {top['cluster_name']}")
    st.write(f"**Population:** {int(top['population']):,}")
    st.write(f"**Median Income:** ${int(top['median_income']):,}")
    st.write(f"**Total Businesses:** {int(top['total_active_businesses'])}")
    st.write(f"**Category Business Count:** {int(top['category_business_count'])}")

st.markdown("---")

# --------------------------------------------------
# Charts
# --------------------------------------------------
chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.subheader("Business Type Distribution")

    category_counts = (
        filtered_df["Category_Display"]
        .value_counts()
        .reset_index()
    )
    category_counts.columns = ["business_type", "count"]

    fig_bar = px.bar(
        category_counts,
        x="business_type",
        y="count",
        text="count",
        color="business_type",
        color_discrete_map=category_hex
    )

    fig_bar.update_layout(
        template="plotly_dark",
        xaxis_title="Business Type",
        yaxis_title="Count",
        showlegend=False
    )

    st.plotly_chart(fig_bar, use_container_width=True)

with chart_col_2:
    st.subheader("Opportunity vs Total Active Businesses")

    fig_scatter = px.scatter(
        filtered_df,
        x="total_active_businesses",
        y="opportunity_score",
        color="Category_Display",
        size="category_business_count",
        hover_name="neighborhood_name",
        color_discrete_map=category_hex
    )

    fig_scatter.update_layout(
        template="plotly_dark",
        xaxis_title="Total Active Businesses",
        yaxis_title="Opportunity Score"
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# --------------------------------------------------
# Final dataset preview
# --------------------------------------------------
st.subheader("Final Dataset")
st.dataframe(filtered_df, use_container_width=True)
