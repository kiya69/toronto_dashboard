import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk

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
# --------------------------------------------------
FILE_ID = "1DM6YmMK4_C_Dk4YPWWQwRJLryeHwKxum"
CSV_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"

# --------------------------------------------------
# Cached data loader
# TTL is set to 10 seconds for testing refresh behavior
# Increase later if needed (for example, 300 seconds)
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
# Cluster label mapping
# This makes the cluster output easier to explain
# --------------------------------------------------
cluster_names = {
    0: "High Density / Competitive",
    1: "Growing Commercial Areas",
    2: "Balanced Residential Zones",
    3: "Underserved Opportunity Areas"
}

df["cluster_name"] = df["cluster_label"].map(cluster_names)

# --------------------------------------------------
# Business category color definitions
# Hex colors are used for charts and sidebar swatches
# RGBA colors are used for the map points
# --------------------------------------------------
category_hex = {
    "Fitness & Wellness": "#dc3232",
    "Pet Services": "#ff8c00",
    "Specialty Retail": "#4682b4",
    "Cafes & Bakeries": "#ffd700",
    "Professional Services": "#a050dc",
    "Tech & Gadgets": "#00c8aa"
}

category_rgba = {
    "Fitness & Wellness": [220, 50, 50, 160],
    "Pet Services": [255, 140, 0, 160],
    "Specialty Retail": [70, 130, 180, 160],
    "Cafes & Bakeries": [255, 215, 0, 160],
    "Professional Services": [160, 80, 220, 160],
    "Tech & Gadgets": [0, 200, 170, 160]
}

# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
st.sidebar.header("Filters")

# Neighborhood filter
selected_neighborhoods = st.sidebar.multiselect(
    "Neighborhood",
    options=sorted(df["neighborhood_name"].unique()),
    default=sorted(df["neighborhood_name"].unique())
)

# --------------------------------------------------
# Business Type filter with color swatches
# Using checkboxes with a colored square beside each label
# This is more controllable than styling multiselect items
# --------------------------------------------------
st.sidebar.markdown("### Business Type")

category_order = [
    category for category in category_hex.keys()
    if category in df["recommended_business_type"].unique()
]

selected_categories = []

for category in category_order:
    col_swatch, col_check = st.sidebar.columns([1, 6])

    with col_swatch:
        st.markdown(
            f"""
            <div style="
                width: 16px;
                height: 16px;
                background-color: {category_hex[category]};
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

# Median income filter
income_range = st.sidebar.slider(
    "Median Income",
    min_value=int(df["median_income"].min()),
    max_value=int(df["median_income"].max()),
    value=(int(df["median_income"].min()), int(df["median_income"].max()))
)

# High opportunity filter
only_high_opportunity = st.sidebar.checkbox(
    "Only high opportunity areas (score >= 80)",
    value=False
)

# --------------------------------------------------
# Apply filters
# --------------------------------------------------
filtered_df = df[
    (df["neighborhood_name"].isin(selected_neighborhoods)) &
    (df["recommended_business_type"].isin(selected_categories)) &
    (df["median_income"].between(income_range[0], income_range[1]))
]

if only_high_opportunity:
    filtered_df = filtered_df[filtered_df["opportunity_score"] >= 80]

# --------------------------------------------------
# Handle empty results
# --------------------------------------------------
if filtered_df.empty:
    st.warning("No data available with the selected filters.")
    st.stop()

# --------------------------------------------------
# Business explanation of the score
# --------------------------------------------------
st.info(
    "Opportunity Score is a composite indicator based on business density, "
    "population, median income, and development activity."
)

# --------------------------------------------------
# KPI calculations
# --------------------------------------------------
top_category = (
    filtered_df["recommended_business_type"].mode()[0]
    if not filtered_df["recommended_business_type"].mode().empty
    else "N/A"
)

high_op_count = int((filtered_df["opportunity_score"] >= 80).sum())

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

# --------------------------------------------------
# Top area highlight
# --------------------------------------------------
st.success(f"Top opportunity area: {top_area_name}")

# --------------------------------------------------
# Prepare map data
# --------------------------------------------------
filtered_df = filtered_df.copy()
filtered_df["color"] = filtered_df["recommended_business_type"].map(category_rgba)
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
            Recommended Business: {recommended_business_type}<br/>
            Cluster: {cluster_name}<br/>
            Population: {population}<br/>
            Median Income: ${median_income}<br/>
            Businesses: {total_active_businesses}
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
    st.write(f"**Recommended Business:** {top['recommended_business_type']}")
    st.write(f"**Cluster:** {top['cluster_name']}")
    st.write(f"**Population:** {int(top['population']):,}")
    st.write(f"**Median Income:** ${int(top['median_income']):,}")
    st.write(f"**Businesses:** {int(top['total_active_businesses'])}")
    st.write(f"**Top Business Category:** {top['top_business_category']}")
    st.write(f"**Construction Count:** {int(top['construction_count'])}")

st.markdown("---")

# --------------------------------------------------
# Charts
# --------------------------------------------------
chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.subheader("Business Type Distribution")

    category_counts = (
        filtered_df["recommended_business_type"]
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
    st.subheader("Opportunity vs Density")

    fig_scatter = px.scatter(
        filtered_df,
        x="business_density_score",
        y="opportunity_score",
        color="recommended_business_type",
        size="population",
        hover_name="neighborhood_name",
        color_discrete_map=category_hex
    )

    fig_scatter.update_layout(
        template="plotly_dark",
        xaxis_title="Business Density Score",
        yaxis_title="Opportunity Score"
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# --------------------------------------------------
# Final dataset preview
# --------------------------------------------------
st.subheader("Final Dataset")
st.dataframe(filtered_df, use_container_width=True)