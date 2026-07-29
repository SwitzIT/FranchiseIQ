import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from app.utils import get_logger

log = get_logger("real_estate_service")

def load_and_preprocess_real_estate(file_path: str) -> gpd.GeoDataFrame:
    """
    Loads real estate data from an Excel file, standardises columns, handles missing values,
    and calculates base metrics and indices.
    """
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        log.error(f"Failed to load real estate data from {file_path}: {e}")
        return gpd.GeoDataFrame()

    # Standardize column names
    df.columns = df.columns.astype(str).str.strip().str.lower()
    
    rename_map = {
        'commercial_sale_price': 'price',
        'price (lkr) min': 'price',
        'avg price (₹/sqft)': 'price',
        'approx. usd (mid)': 'price_usd',
        'commercial_rent': 'rent',
        'yoy change': 'annual_appreciation',
        'market trend': 'market_trend',
        'vacancy_rate': 'vacancy_rate',
        'latitude': 'lat',
        'longitude': 'lon',
        'city / area': 'city',
        'locality / city': 'city',
        'district / region': 'district',
        'district': 'district',
        'property type': 'property_type',
        'unit': 'unit'
    }
    df.rename(columns=rename_map, inplace=True)
    
    # Ensure geospatial columns exist
    if 'lat' not in df.columns or 'lon' not in df.columns:
        log.error("Real estate data missing latitude or longitude.")
        return gpd.GeoDataFrame()
        
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df.dropna(subset=['lat', 'lon'], inplace=True)
    
    # Extract numerical values from strings if needed (e.g. "12% YoY" -> 12.0)
    if 'annual_appreciation' in df.columns:
        df['annual_appreciation'] = df['annual_appreciation'].astype(str).str.extract(r'([+-]?\d+\.?\d*)')[0].astype(float)
        
    # Clean currency symbols and commas before converting to numeric
    for col in ['price', 'rent']:
        if col in df.columns:
            # Keep digits and decimals, replace everything else
            cleaned = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True).replace('', '0')
            df[col] = cleaned

    # Fill missing values defensively
    cols_to_fill = ['price', 'rent', 'annual_appreciation', 'vacancy_rate', 'market_trend', 'property_size']
    for col in cols_to_fill:
        if col not in df.columns:
            df[col] = 0.0
        else:
            num_series = pd.to_numeric(df[col], errors='coerce')
            df[col] = num_series.fillna(num_series.median() if num_series.notna().any() else 0.0)

    # 1. Property Cost Index (0-100)
    # Computed within each city (or district) if available, otherwise globally.
    group_col = 'city' if 'city' in df.columns and df['city'].notna().any() else 'district' if 'district' in df.columns else None
    
    if group_col:
        df['property_cost_index'] = df.groupby(group_col)['price'].rank(pct=True) * 100
    else:
        df['property_cost_index'] = df['price'].rank(pct=True) * 100
        
    df['property_cost_index'] = df['property_cost_index'].fillna(50.0)

    # 2. Property Growth Score (0-100)
    appreciation_min = df['annual_appreciation'].min()
    appreciation_max = df['annual_appreciation'].max()
    
    if appreciation_max > appreciation_min:
        df['property_growth_score'] = ((df['annual_appreciation'] - appreciation_min) / (appreciation_max - appreciation_min)) * 100
    else:
        df['property_growth_score'] = 50.0

    # Convert to GeoDataFrame
    geometry = [Point(xy) for xy in zip(df['lon'], df['lat'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    
    log.info(f"Loaded {len(gdf)} real estate records with indices.")
    return gdf

def enrich_with_real_estate(df: pd.DataFrame, re_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Enriches candidate or store dataframe with real estate spatial features.
    """
    if re_gdf.empty or df.empty or 'Latitude' not in df.columns or 'Longitude' not in df.columns:
        # Provide default 0 values if no real estate data
        cols = ['avg_property_price_1km', 'avg_rent_1km', 'commercial_count_1km', 'property_growth_1km',
                'avg_property_price_3km', 'avg_rent_3km', 'commercial_count_3km', 'commercial_density_3km', 'property_growth_3km', 'vacancy_rate_3km',
                'avg_property_price_5km', 'avg_rent_5km', 'commercial_count_5km', 'property_growth_5km', 'vacancy_rate_5km']
        for col in cols:
            df[col] = 0.0
        return df

    # Convert df to GeoDataFrame (using a projected CRS for accurate buffer in meters)
    target_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']), crs="EPSG:4326")
    
    # Project both to Web Mercator (EPSG:3857) for distance in meters
    target_gdf = target_gdf.to_crs(epsg=3857)
    re_gdf_proj = re_gdf.to_crs(epsg=3857)
    
    radii = [1000, 3000, 5000]
    
    # We will use spatial joins with buffers
    for radius in radii:
        km = int(radius / 1000)
        
        # Buffer candidates
        target_gdf['geometry_buffer'] = target_gdf.geometry.buffer(radius)
        target_buffer_gdf = target_gdf.set_geometry('geometry_buffer')
        
        # Join with real estate points
        joined = gpd.sjoin(target_buffer_gdf, re_gdf_proj, how='left', predicate='intersects')
        
        # Aggregate
        agg_df = joined.groupby(joined.index).agg({
            'price': 'mean',
            'rent': 'mean',
            'index_right': 'count', # count of commercial properties
            'property_growth_score': 'mean',
            'vacancy_rate': 'mean'
        }).rename(columns={
            'price': f'avg_property_price_{km}km',
            'rent': f'avg_rent_{km}km',
            'index_right': f'commercial_count_{km}km',
            'property_growth_score': f'property_growth_{km}km',
            'vacancy_rate': f'vacancy_rate_{km}km'
        })
        
        # Fill missing
        agg_df.fillna(0.0, inplace=True)
        
        # Merge back to df
        for col in agg_df.columns:
            df[col] = agg_df[col]
            
        # Commercial density score at 3km
        if km == 3:
            max_cnt = df[f'commercial_count_3km'].max()
            if max_cnt > 0:
                df['commercial_density_3km'] = (df[f'commercial_count_3km'] / max_cnt) * 100
            else:
                df['commercial_density_3km'] = 0.0

    # Create Interaction Features
    if 'Income' in df.columns:
        df['income_property_ratio'] = np.where(df['avg_property_price_3km'] > 0, df['Income'] / df['avg_property_price_3km'], 0)
    else:
        df['income_property_ratio'] = 0.0
        
    df['amenity_growth_score'] = (df.get('Total_Amenities', 0)) * df.get('property_growth_3km', 0)
    
    if 'Population' in df.columns:
        df['population_commercial_score'] = df['Population'] * df.get('commercial_density_3km', 0)
    else:
        df['population_commercial_score'] = 0.0
        
    df['franchise_density_score'] = (df.get('stores_2km', 0) + df.get('stores_5km', 0)) * df.get('commercial_density_3km', 0)
    
    # Market Saturation Score
    df['market_saturation_score'] = np.clip(
        (df.get('stores_2km', 0) * 10) + df.get('commercial_density_3km', 0) - df.get('property_growth_3km', 0),
        0, 100
    )
    
    return df
