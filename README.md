🚚 Urban Delivery Optimizer
An intelligent tool for optimizing "last-mile" delivery routes using Simulated Annealing metaheuristic and real-world OpenStreetMap data.

Інтелектуальний інструмент для оптимізації маршрутів доставки «останньої милі» за допомогою метаевристики симульованого відпалу та реальних даних OpenStreetMap.

How to Run

Method 1: Docker (Recommended)

Build the image:

docker build -t delivery-optimizer .

Run the container:

docker run -p 8501:8501 delivery-optimizer

Method 2: Local Installation

Install dependencies:

pip install -r requirements.txt

Start the application:

streamlit run app.py

Як запустити

Спосіб 1: Docker (Рекомендовано)

Зберіть образ:

docker build -t delivery-optimizer .

Запустіть контейнер:

docker run -p 8501:8501 delivery-optimizer

Спосіб 2: Локальне встановлення

Встановіть залежності:

pip install -r requirements.txt

Запустіть додаток:
streamlit run app.py
