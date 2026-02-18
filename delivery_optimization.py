import osmnx as ox
import networkx as nx
import random
import math
import matplotlib.pyplot as plt
import numpy as np
import time
import warnings

warnings.filterwarnings("ignore")

class UrbanDeliveryOptimizer:
    def __init__(self, place_name, num_orders=10):
        """
        Ініціалізація оптимізатора.
        """
        print(f"[INIT] Завантаження карти для: {place_name}...")
        
        # 1. Завантажуємо граф дорожньої мережі
        self.G = ox.graph_from_place(place_name, network_type='drive')
        
        print("[INIT] Фільтрація ізольованих ділянок...")
        largest_cc = max(nx.strongly_connected_components(self.G), key=len)
        self.G = self.G.subgraph(largest_cc).copy()
        
        # Проектуємо граф в метри
        try:
            self.G = ox.project_graph(self.G)
        except AttributeError:
             self.G = ox.projection.project_graph(self.G)
        
        self.nodes = list(self.G.nodes())
        
        # Перевірка на достатню кількість вузлів
        if len(self.nodes) < num_orders + 1:
            raise ValueError("Замало вузлів на карті для такої кількості замовлень!")

        self.depot = random.choice(self.nodes) # Депо (старт)
        
        # Генеруємо випадкові точки доставки (виключаючи депо)
        available_nodes = [n for n in self.nodes if n != self.depot]
        self.orders = random.sample(available_nodes, num_orders)
        
        # Список всіх точок: Депо + Замовлення
        self.targets = [self.depot] + self.orders
        self.num_targets = len(self.targets)
        
        # Кеш для матриці відстаней
        self.dist_matrix = np.zeros((self.num_targets, self.num_targets))
        print(f"[INIT] Карта підготовлена. Вузлів у графі: {len(self.nodes)}")

    def precalculate_distances(self):
        """
        Розрахунок матриці відстаней між усіма точками доставки.
        """
        print("[INFO] Розрахунок матриці відстаней (це може зайняти час)...")
        for i in range(self.num_targets):
            for j in range(self.num_targets):
                if i != j:
                    try:
                        # Розрахунок найкоротшого шляху по дорогах
                        length = nx.shortest_path_length(
                            self.G, 
                            self.targets[i], 
                            self.targets[j], 
                            weight='length'
                        )
                        # Симуляція трафіку
                        traffic_factor = random.uniform(1.0, 1.2)
                        self.dist_matrix[i][j] = length * traffic_factor
                    except nx.NetworkXNoPath:
                        self.dist_matrix[i][j] = 1e9 # Велика відстань
        print("[INFO] Матрицю розраховано.")

    def total_route_cost(self, route_indices):
        """Функція енергії: загальна довжина маршруту"""
        cost = 0
        # Від депо до першої точки
        cost += self.dist_matrix[0][route_indices[0]]
        
        # Між точками маршруту
        for i in range(len(route_indices) - 1):
            u = route_indices[i]
            v = route_indices[i+1]
            cost += self.dist_matrix[u][v]
            
        # Назад в депо
        cost += self.dist_matrix[route_indices[-1]][0]
        return cost

    def simulated_annealing(self, initial_route=None, initial_temp=1000, cooling_rate=0.995, max_iter=5000):
        """
        Основний алгоритм Симульованого Відпалу.
        """
        if initial_route is None:
            current_route = list(range(1, self.num_targets))
            random.shuffle(current_route)
        else:
            current_route = initial_route[:]

        current_cost = self.total_route_cost(current_route)
        
        best_route = current_route[:]
        best_cost = current_cost
        
        temp = initial_temp
        costs_history = [] 

        start_time = time.time()

        for i in range(max_iter):
            new_route = current_route[:]
            
            # ЕВРИСТИКА: Swap
            idx1, idx2 = random.sample(range(len(new_route)), 2)
            new_route[idx1], new_route[idx2] = new_route[idx2], new_route[idx1]

            new_cost = self.total_route_cost(new_route)
            
            delta = new_cost - current_cost
            acceptance_prob = math.exp(-delta / temp) if delta > 0 else 1.0
            
            if random.random() < acceptance_prob:
                current_route = new_route
                current_cost = new_cost
                
                if current_cost < best_cost:
                    best_cost = current_cost
                    best_route = current_route[:]
            
            costs_history.append(best_cost)
            temp *= cooling_rate 
            
            if temp < 1:
                break
                
        elapsed_time = time.time() - start_time
        return best_route, best_cost, costs_history, elapsed_time

    def add_dynamic_order(self):
        """Симуляція динамічного додавання замовлення"""
        print("\n[DYNAMIC] Надійшло нове замовлення!")
        
        # Вибираємо нову точку, якої ще немає в списку
        available_nodes = [n for n in self.nodes if n not in self.targets]
        if not available_nodes:
            print("Немає вільних точок для нового замовлення.")
            return None

        new_node = random.choice(available_nodes)
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
                    dist_to = nx.shortest_path_length(self.G, self.targets[i], self.targets[new_idx], weight='length')
                    dist_from = nx.shortest_path_length(self.G, self.targets[new_idx], self.targets[i], weight='length')
                    new_matrix[i][new_idx] = dist_to * 1.2 
                    new_matrix[new_idx][i] = dist_from * 1.2
                except:
                    new_matrix[i][new_idx] = 1e9
                    new_matrix[new_idx][i] = 1e9

        self.dist_matrix = new_matrix
        return new_idx

    def visualize_route(self, route_indices, title="Маршрут"):
        """
        Візуалізація маршруту на карті.
        """
        full_path_indices = [0] + route_indices + [0]
        
        routes_to_plot = []
        print("[INFO] Підготовка візуалізації...")
        
        for i in range(len(full_path_indices) - 1):
            u = self.targets[full_path_indices[i]]
            v = self.targets[full_path_indices[i+1]]
            try:
                path = nx.shortest_path(self.G, u, v, weight='length')
                routes_to_plot.append(path)
            except nx.NetworkXNoPath:
                pass

        if not routes_to_plot:
            print("Неможливо побудувати маршрут для відображення.")
            return

        # Малюємо множину маршрутів
        # У нових версіях це зазвичай ox.plot.graph_routes, але старий аліас часто працює.
        # Якщо впаде, ми спробуємо імпортувати явно.
        try:
            fig, ax = ox.plot_graph_routes(
                self.G, 
                routes_to_plot, 
                route_colors='r', 
                route_linewidth=3, 
                node_size=0, 
                show=False, 
                close=False
            )
        except AttributeError:
             # Fallback для найновіших версій v2.0+
             fig, ax = ox.plot.plot_graph_routes(
                self.G, 
                routes_to_plot, 
                route_colors='r', 
                route_linewidth=3, 
                node_size=0, 
                show=False, 
                close=False
            )
        
        # Маркери
        lats = [self.G.nodes[n]['y'] for n in self.targets]
        lons = [self.G.nodes[n]['x'] for n in self.targets]
        
        ax.scatter(lons[0], lats[0], c='lime', s=120, edgecolors='black', label='Депо', zorder=10)
        ax.scatter(lons[1:], lats[1:], c='cyan', s=60, edgecolors='black', label='Замовлення', zorder=10)
        
        plt.title(title)
        plt.legend()
        plt.show()


# ================= ЗАПУСК =================
if __name__ == "__main__":
    place = "Korabelnyi District, Kherson, Ukraine"
    
    try:
        optimizer = UrbanDeliveryOptimizer(place, num_orders=10)
        
        optimizer.precalculate_distances()
        
        print("\n--- Етап 1: Статична оптимізація ---")
        best_route, cost, history, t_static = optimizer.simulated_annealing()
        
        if cost > 1e8:
             print("УВАГА: Маршрут неоптимальний через недосяжні точки.")
        else:
            print(f"Оптимальний маршрут (індекси): {best_route}")
            print(f"Довжина маршруту: {cost:.2f} м")
            print(f"Час конвергенції: {t_static:.4f} сек")
        
        # Графік
        plt.figure(figsize=(10, 5))
        plt.plot(history)
        plt.title("Конвергенція")
        plt.xlabel("Ітерації")
        plt.ylabel("Вартість")
        plt.show()
        
        # Карта
        optimizer.visualize_route(best_route, title="Початковий маршрут")

        # Динаміка
        print("\n--- Етап 2: Динамічні зміни ---")
        new_idx = optimizer.add_dynamic_order()
        
        if new_idx:
            current_best_route = best_route + [new_idx] 
            
            print("Перерахунок маршруту...")
            dyn_route, dyn_cost, _, t_dyn = optimizer.simulated_annealing(
                initial_route=current_best_route, 
                initial_temp=200, 
                max_iter=3000
            )
            
            print(f"Нова довжина: {dyn_cost:.2f} м")
            optimizer.visualize_route(dyn_route, title="Оновлений маршрут")
            
    except Exception as e:
        print(f"Сталася помилка: {e}")