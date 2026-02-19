import streamlit as st
from streamlit_folium import st_folium
import folium
import matplotlib.pyplot as plt
import time

# IMPORT BACKEND CLASS / ІМПОРТ КЛАСУ БЕКЕНДУ
from delivery_optimization import UrbanDeliveryOptimizer

# Page Config / Налаштування сторінки
st.set_page_config(page_title="Last Mile Optimization", layout="wide", page_icon="🚚")

# Title / Заголовок
st.title("🚚 Оптимізація Останньої Милі (Last Mile Delivery)")
st.markdown("Optimization using **Simulated Annealing** on OpenStreetMap data.")

# Session State / Стан сесії
if 'optimizer' not in st.session_state:
    st.session_state.optimizer = None
if 'route' not in st.session_state:
    st.session_state.route = None
if 'cost' not in st.session_state:
    st.session_state.cost = None
if 'history' not in st.session_state:
    st.session_state.history = None

# --- SIDEBAR / БІЧНА ПАНЕЛЬ ---
st.sidebar.header("⚙️ Settings / Налаштування")

# Input for Place / Введення місця
place_name = st.sidebar.text_input("Area / Район (OSM)", "Korabelnyi District, Kherson, Ukraine")
num_orders = st.sidebar.slider("Orders Count / Кількість замовлень", 5, 30, 10)

st.sidebar.markdown("---")
st.sidebar.subheader("Controls / Керування")

# Button 1: Load Map
if st.sidebar.button("1. Load Map / Завантажити карту", use_container_width=True):
    with st.spinner('Downloading graph & calculating matrix...'):
        try:
            # Call Backend
            opt = UrbanDeliveryOptimizer(place_name, num_orders)
            opt.precalculate_distances()
            
            # Save to session
            st.session_state.optimizer = opt
            st.session_state.route = None 
            st.session_state.cost = None
            st.session_state.history = None
            
            st.success("✅ Map Loaded!")
        except Exception as e:
            st.error(f"Error: {e}")

# Button 2: Find Route
if st.sidebar.button("2. Optimize Route / Знайти маршрут", use_container_width=True):
    if st.session_state.optimizer:
        with st.spinner('Running Simulated Annealing...'):
            opt = st.session_state.optimizer
            
            start_time = time.time() 
            route, cost, hist = opt.simulated_annealing()
            exec_time = time.time() - start_time 
            
            st.session_state.route = route
            st.session_state.cost = cost
            st.session_state.history = hist
            st.sidebar.success(f"Час конвергенції: {exec_time:.3f} сек") # Виводимо час!
    else:
        st.warning("Please load the map first!")

# Button 3: Add Dynamic Order
if st.sidebar.button("3. ➕ Add Order / Додати замовлення", use_container_width=True):
    if st.session_state.optimizer and st.session_state.route:
        with st.spinner('Adding order & recalculating...'):
            opt = st.session_state.optimizer
            new_idx = opt.add_dynamic_order()
            
            if new_idx:
                current_route = st.session_state.route + [new_idx]
                
                start_time = time.time() 
                route, cost, hist = opt.simulated_annealing(
                    initial_route=current_route, 
                    initial_temp=200, 
                    max_iter=1000
                )
                exec_time = time.time() - start_time 
                
                st.session_state.route = route
                st.session_state.cost = cost
                st.session_state.history.extend(hist)
                st.sidebar.success(f"Час адаптації (Hot Start): {exec_time:.3f} сек")

# --- MAIN DASHBOARD / ГОЛОВНА ПАНЕЛЬ ---

# Metrics Display
if st.session_state.route and st.session_state.cost:
    st.markdown("### 📊 Критерії оцінки ефективності")
    m1, m2, m3, m4 = st.columns(4)
    
    # 1. Поточна дистанція
    m1.metric(
        label="📏 Оптимальна дистанція", 
        value=f"{st.session_state.cost / 1000:.2f} км"
    )
    
    # 2. Якість маршруту 
    initial_cost = st.session_state.history[0]
    final_cost = st.session_state.history[-1]
    improvement = ((initial_cost - final_cost) / initial_cost) * 100
    
    m2.metric(
        label="💎 Якість (Покращення)", 
        value=f"{improvement:.1f}%",
        delta=f"-{initial_cost/1000 - final_cost/1000:.1f} км",
        delta_color="inverse" 
    )
    
    # 3. Кількість точок
    m3.metric(
        label="📍 Кількість зупинок", 
        value=len(st.session_state.route) + 1
    )
    
    # 4. Час конвергенції (приблизна оцінка швидкодії)
    total_iterations = len(st.session_state.history)
    m4.metric(
        label="⚡ Ітерацій до конвергенції", 
        value=f"{total_iterations}"
    )

    st.markdown("---")
# Layout for Map and Graph
col_map, col_graph = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ Live Map")
    if st.session_state.optimizer:
        opt = st.session_state.optimizer
        
        # Center map on Depot
        depot_node = opt.targets[0]
        start_lat = opt.G.nodes[depot_node]['y']
        start_lon = opt.G.nodes[depot_node]['x']
        
        m = folium.Map(location=[start_lat, start_lon], zoom_start=14)

        # Draw Markers
        markers = opt.get_markers()
        for marker in markers:
            if marker['type'] == 'depot':
                folium.Marker(
                    [marker['lat'], marker['lon']],
                    popup="Depot",
                    icon=folium.Icon(color="green", icon="home")
                ).add_to(m)
            else:
                folium.CircleMarker(
                    location=[marker['lat'], marker['lon']],
                    radius=6,
                    popup=f"Order #{marker['id']}",
                    color="blue",
                    fill=True,
                    fill_color="blue"
                ).add_to(m)

        # Draw Route Polyline
        if st.session_state.route:
            route_coords = opt.get_route_coordinates(st.session_state.route)
            if route_coords:
                folium.PolyLine(
                    locations=route_coords,
                    color="red",
                    weight=4,
                    opacity=0.8,
                    tooltip="Optimal Path"
                ).add_to(m)

        # Render Map
        st_folium(m, width=800, height=500, returned_objects=[])
    else:
        st.info("👈 Use Sidebar to start.")

with col_graph:
    st.subheader("📈 Algorithm Convergence")
    if st.session_state.history:
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.plot(st.session_state.history, color='orange', linewidth=2)
        ax.set_xlabel("Iterations")
        ax.set_ylabel("Cost (meters)")
        ax.grid(True, linestyle='--', alpha=0.6)
        st.pyplot(fig)
    else:
        st.write("Graph will appear after calculation.")