import osmnx as ox
import networkx as nx
import random
import math
import numpy as np
import time
import warnings

# Suppress warnings / Приховуємо попередження
warnings.filterwarnings("ignore")

class UrbanDeliveryOptimizer:
    def __init__(self, place_name, num_orders=10):
        """
        Backend initialization. Loads graph and prepares data.
        Ініціалізація бекенду. Завантаження графа та підготовка даних.
        """
        print(f"[BACKEND] Loading map: {place_name}...")
        
        strict_filter = (
            '["highway"]["area"!~"yes"]'
            '["access"!~"private|no|customers"]'
            '["motor_vehicle"!~"no"]'
            '["highway"!~"pedestrian|path|footway|steps|track|construction"]'
        )

        # 1. Load Graph / Завантаження графа
        self.G = ox.graph_from_place(place_name, network_type='drive', custom_filter=strict_filter)
        
        # 2. Filter isolated nodes / Фільтрація ізольованих вузлів
        largest_cc = max(nx.strongly_connected_components(self.G), key=len)
        self.G = self.G.subgraph(largest_cc).copy()
        
        # 3. Project to meters (for calculations) / Проекція в метри (для розрахунків)
        # We keep self.G (lat/lon) for markers and self.G_proj (meters) for distances
        try:
            self.G_proj = ox.project_graph(self.G)
        except AttributeError:
            self.G_proj = ox.projection.project_graph(self.G)
        
        self.nodes = list(self.G_proj.nodes())
        
        if len(self.nodes) < num_orders + 1:
            raise ValueError("Not enough nodes for this number of orders!")

        # 4. Generate Orders / Генерація замовлень
        self.depot = random.choice(self.nodes)
        available = [n for n in self.nodes if n != self.depot]
        self.orders = random.sample(available, min(len(available), num_orders))
        
        self.targets = [self.depot] + self.orders
        self.num_targets = len(self.targets)
        
        # Matrix Cache / Кеш матриці
        self.dist_matrix = np.zeros((self.num_targets, self.num_targets))
        print(f"[BACKEND] Ready. Nodes: {len(self.nodes)}")

    def precalculate_distances(self):
        """Calculates distance matrix / Розрахунок матриці відстаней"""
        for i in range(self.num_targets):
            for j in range(self.num_targets):
                if i != j:
                    try:
                        # Use projected graph (meters) / Використовуємо проектований граф (метри)
                        length = nx.shortest_path_length(
                            self.G_proj, self.targets[i], self.targets[j], weight='length'
                        )
                        # Traffic noise / Шум трафіку
                        traffic_factor = random.uniform(1.0, 1.2)
                        self.dist_matrix[i][j] = length * traffic_factor
                    except nx.NetworkXNoPath:
                        self.dist_matrix[i][j] = 1e9

    def total_route_cost(self, route_indices):
        """Calculate total cost / Розрахунок повної вартості"""
        cost = 0
        cost += self.dist_matrix[0][route_indices[0]]
        for i in range(len(route_indices) - 1):
            cost += self.dist_matrix[route_indices[i]][route_indices[i+1]]
        cost += self.dist_matrix[route_indices[-1]][0]
        return cost

    def simulated_annealing(self, initial_route=None, initial_temp=1000, cooling_rate=0.995, max_iter=2000):
        """Simulated Annealing Algorithm / Алгоритм симульованого відпалу"""
        if initial_route is None:
            current_route = list(range(1, self.num_targets))
            random.shuffle(current_route)
        else:
            current_route = initial_route[:]
        
        current_cost = self.total_route_cost(current_route)
        best_route = current_route[:]
        best_cost = current_cost
        temp = initial_temp
        history = []
        
        for i in range(max_iter):
            new_route = current_route[:]
            if len(new_route) < 2: break
            
            # Swap Logic
            idx1, idx2 = random.sample(range(len(new_route)), 2)
            new_route[idx1], new_route[idx2] = new_route[idx2], new_route[idx1]
            new_cost = self.total_route_cost(new_route)
            
            # Acceptance Probability
            delta = new_cost - current_cost
            if delta < 0 or random.random() < math.exp(-delta / temp):
                current_route = new_route
                current_cost = new_cost
                if current_cost < best_cost:
                    best_cost = current_cost
                    best_route = current_route[:]
                    
            history.append(best_cost)
            temp *= cooling_rate
            if temp < 1: break
            
        return best_route, best_cost, history

    def add_dynamic_order(self):
        """Adds a new order dynamically / Динамічне додавання замовлення"""
        available = [n for n in self.nodes if n not in self.targets]
        if not available: return None
        
        new_node = random.choice(available)
        self.orders.append(new_node)
        self.targets.append(new_node)
        
        old_size = self.num_targets
        self.num_targets += 1
        new_matrix = np.zeros((self.num_targets, self.num_targets))
        new_matrix[:old_size, :old_size] = self.dist_matrix
        
        new_idx = old_size
        for i in range(self.num_targets):
            if i != new_idx:
                try:
                    d1 = nx.shortest_path_length(self.G_proj, self.targets[i], self.targets[new_idx], weight='length')
                    d2 = nx.shortest_path_length(self.G_proj, self.targets[new_idx], self.targets[i], weight='length')
                    new_matrix[i][new_idx] = d1 * 1.2
                    new_matrix[new_idx][i] = d2 * 1.2
                except:
                    new_matrix[i][new_idx] = 1e9
                    new_matrix[new_idx][i] = 1e9
                    
        self.dist_matrix = new_matrix
        return new_idx

    def get_route_coordinates(self, route_indices):
        """
        Returns list of [lat, lon] for Folium.
        Повертає координати [lat, lon] для малювання ліній.
        """
        full_indices = [0] + route_indices + [0]
        coordinates = []
        
        for i in range(len(full_indices) - 1):
            u = self.targets[full_indices[i]]
            v = self.targets[full_indices[i+1]]
            
            try:
                path_nodes = nx.shortest_path(self.G_proj, u, v, weight='length')
                
                # Проходимося по кожному відрізку (вулиці)
                for k in range(len(path_nodes) - 1):
                    n1 = path_nodes[k]
                    n2 = path_nodes[k+1]
                    
                    edges = self.G.get_edge_data(n1, n2)
                    if not edges: continue
                    
                    # Вибираємо найкоротший сегмент
                    min_edge = min(edges.values(), key=lambda d: d.get('length', float('inf')))
                    
                    if 'geometry' in min_edge:
                        for lon, lat in min_edge['geometry'].coords:
                            coordinates.append([lat, lon])
                    else:
                        coordinates.append([self.G.nodes[n1]['y'], self.G.nodes[n1]['x']])
                        coordinates.append([self.G.nodes[n2]['y'], self.G.nodes[n2]['x']])
                        
            except nx.NetworkXNoPath:
                pass
                
        return coordinates
    
    def get_markers(self):
        """Returns data for map markers / Повертає дані для маркерів"""
        markers = []
        # Depot
        d_node = self.targets[0]
        markers.append({
            "lat": self.G.nodes[d_node]['y'],
            "lon": self.G.nodes[d_node]['x'],
            "type": "depot"
        })
        # Orders
        for i, node in enumerate(self.targets[1:]):
            markers.append({
                "lat": self.G.nodes[node]['y'],
                "lon": self.G.nodes[node]['x'],
                "type": "order",
                "id": i + 1
            })
        return markers