// Global variables for map
let map;
let routeLayer;
let heatLayer;
let legend;
let lastRouteData;
let lastWeatherData;
let startMarker, endMarker, routeLine;
let startLoc, endLoc;

// Base layers
let lightLayer, darkLayer, streetLayer;
let baseLayers;

// Theme colors
let currentTheme = 'dark'; // Default theme

function getThemeColors() {
    return {
        accent: currentTheme === 'dark' ? '#FFCC00' : '#10B981', 
        low:    currentTheme === 'dark' ? '#FFEB3B' : '#10B981', 
        medium: currentTheme === 'dark' ? '#FFC107' : '#059669', 
        high:   currentTheme === 'dark' ? '#FF9800' : '#047857', 
        severe: currentTheme === 'dark' ? '#FF5722' : '#065F46', 
        background: currentTheme === 'dark' ? '#1e1e1e' : '#FFFFFF',
        text: currentTheme === 'dark' ? '#FFFFFF' : '#333333'
    };
}

let incidentLayerGroup;

function initMap() {
    routeLayer = L.layerGroup();

    map = L.map('map').setView([40.7128, -74.0060], 12);

    lightLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19
    });

    darkLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19
    });

    streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    });

    baseLayers = {
        "Light": lightLayer,
        "Dark": darkLayer,
        "Street": streetLayer
    };

    applyTheme();
    routeLayer.addTo(map);
    L.control.layers(baseLayers).addTo(map);

    incidentLayerGroup = L.layerGroup().addTo(map);
}

function applyTheme() {
    document.documentElement.className = currentTheme + '-mode';
    updateMapBaseLayer();
    if (map && legend) {
        updateMapLegend();
    }
    if (lastRouteData && lastWeatherData) {
        displayRoute(lastRouteData, lastWeatherData);
    }
    if (heatLayer && map.hasLayer(heatLayer)) {
        map.removeLayer(heatLayer);
        if (lastRouteData) {
            createHeatmapLayer(lastRouteData);
        }
    }
}

function toggleTheme() {
    const html = document.documentElement;
    if (html.classList.contains('light-mode')) {
        html.classList.remove('light-mode');
        localStorage.setItem('theme', 'dark');
        currentTheme = 'dark';
        updateMapBaseLayer('dark');
    } else {
        html.classList.add('light-mode');
        localStorage.setItem('theme', 'light');
        currentTheme = 'light';
        updateMapBaseLayer('light');
    }
    applyTheme();
}

function updateMapBaseLayer(theme) {
    if (theme === 'light') {
        if (map.hasLayer(darkLayer)) map.removeLayer(darkLayer);
        if (!map.hasLayer(lightLayer)) map.addLayer(lightLayer);
    } else {
        if (map.hasLayer(lightLayer)) map.removeLayer(lightLayer);
        if (!map.hasLayer(darkLayer)) map.addLayer(darkLayer);
    }
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'light' || (!savedTheme && !prefersDarkMode)) {
        document.documentElement.classList.add('light-mode');
        currentTheme = 'light';
        updateMapBaseLayer('light');
    } else {
        document.documentElement.classList.remove('light-mode');
        currentTheme = 'dark';
        updateMapBaseLayer('dark');
    }
}

function updateMapLegend() {
    if (legend) {
        map.removeControl(legend);
        legend = null;
    }
}

function setDefaultDate() {
    const today = new Date();
    const formattedDate = today.toISOString().slice(0, 10);
    const dateSelect = document.getElementById('date-select');
    if (dateSelect) {
        dateSelect.value = formattedDate;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setDefaultDate();
    initializeTheme();

    map.on('moveend', () => {
        getIncidents(map.getBounds());
    });

    document.getElementById('incident-filter').addEventListener('change', () => {
        getIncidents(map.getBounds());
    });

    const calculateRouteBtn = document.getElementById('calculate-route');
    if (calculateRouteBtn) {
        calculateRouteBtn.addEventListener('click', calculateRoute);
        calculateRouteBtn.style.backgroundColor = getThemeColors().accent;
        calculateRouteBtn.style.color = currentTheme === 'dark' ? '#121212' : '#FFFFFF';
    }

    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
});

// Route calculation
function calculateRoute() {
    const start = document.getElementById('start-input').value;
    const end = document.getElementById('end-input').value;
    const date = document.getElementById('date-select').value;
    const time = document.getElementById('time-select').value;
    
    if (!start || !end) {
        showError("Please enter both start and end locations");
        return;
    }
    
    showLoading();
    
    fetch('/api/route', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            start: start,
            end: end,
            date: date,
            time: time
        })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            lastRouteData = data.route;
            
            // Get weather data to enhance the route display
            getWeatherData()
                .then(weatherData => {
                    lastWeatherData = weatherData;
                    displayRoute(data.route, weatherData);
                })
                .catch(error => {
                    displayRoute(data.route, null);
                });
        } else {
            showError(data.error || "Error calculating route");
        }
    })
    .catch(error => {
        hideLoading();
        showError("Network error. Please try again.");
        console.error("Error:", error);
    });
}

// Marker creation
function createMarkers(start, end) {
    if (startMarker) map.removeLayer(startMarker);
    if (endMarker) map.removeLayer(endMarker);
    
    const colors = getThemeColors();
    
    // Create start icon (circular shape)
    const startIcon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="width: 20px; height: 20px; border-radius: 50%; background-color: ${colors.accent}; border: 3px solid #FFFFFF;"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    // Create end icon (diamond shape)
    const endIcon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="width: 20px; height: 20px; transform: rotate(45deg); background-color: ${colors.accent}; border: 3px solid #FFFFFF;"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    startMarker = L.marker(start, {icon: startIcon}).addTo(routeLayer);
    endMarker = L.marker(end, {icon: endIcon}).addTo(routeLayer);
    
    startLoc = start;
    endLoc = end;
}

// Route display
function displayRoute(routeData, weatherData) {
    clearMap();
    
    if (!routeData) return;
    
    const start = routeData.route_coords[0];
    const end = routeData.route_coords[routeData.route_coords.length - 1];
    
    createMarkers(start, end);
    createHeatmapLayer(routeData);
    updateRouteInfo(routeData, weatherData);
    
    // Adjust map to fit the route
    if (routeData.route_coords.length > 0) {
        const bounds = L.latLngBounds(routeData.route_coords);
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Heatmap creation
function createHeatmapLayer(routeData) {
    if (heatLayer && map.hasLayer(heatLayer)) {
        map.removeLayer(heatLayer);
    }
    
    if (!routeData || !routeData.edges || routeData.edges.length === 0) return;
    
    const colors = getThemeColors();
    const congestionSegments = routeData.edges;
    
    heatLayer = L.layerGroup();
    
    congestionSegments.forEach(segment => {
        const congestionLevel = segment.congestion_level; // 0-1 scale
        
        let color;
        if (congestionLevel < 0.25) {
            color = colors.low;
        } else if (congestionLevel < 0.5) {
            color = colors.medium;
        } else if (congestionLevel < 0.75) {
            color = colors.high;
        } else {
            color = colors.severe;
        }
        
        const line = L.polyline([segment.start, segment.end], {
            color: color,
            weight: 5,
            opacity: 0.8
        }).addTo(heatLayer);
        
        // Popup with congestion info
        line.bindPopup(`<div class="popup-content">
            <h3>Segment Info</h3>
            <p>Distance: ${segment.distance.toFixed(2)} miles</p>
            <p>Base travel time: ${segment.base_time.toFixed(1)} min</p>
            <p>Actual travel time: ${segment.actual_time.toFixed(1)} min</p>
            <p>Delay due to congestion: ${segment.congestion_impact.toFixed(1)} min</p>
        </div>`);
    });
    
    heatLayer.addTo(map);
}

// UI Updates
function clearMap() {
    if (routeLayer) {
        routeLayer.clearLayers();
    }
    
    if (heatLayer && map.hasLayer(heatLayer)) {
        map.removeLayer(heatLayer);
    }
    
    startMarker = null;
    endMarker = null;
    routeLine = null;
}

function showLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.style.display = 'flex';
    }
}

function hideLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

function showError(message) {
    const errorElement = document.getElementById('error-message');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 5000);
    }
}

function updateThemeColors() {
    const colors = getThemeColors();
    
    document.documentElement.style.setProperty('--accent-color', colors.accent);
    document.documentElement.style.setProperty('--bg-color', colors.background);
    document.documentElement.style.setProperty('--text-color', colors.text);
    
    const calculateBtn = document.getElementById('calculate-route');
    if (calculateBtn) {
        calculateBtn.style.backgroundColor = colors.accent;
        calculateBtn.style.color = currentTheme === 'dark' ? '#121212' : '#FFFFFF';
    }
}

// Route information
function updateRouteInfo(routeData, weatherData) {
    const infoPanel = document.getElementById('route-info');
    if (!infoPanel) return;
    
    // Make the route info panel visible
    infoPanel.style.display = 'block';
    
    // Update distance
    const distanceEl = document.getElementById('distance');
    if (distanceEl) {
        distanceEl.textContent = routeData.distance_miles ? routeData.distance_miles + ' mi' : '-';
    }
    
    // Update duration
    const durationEl = document.getElementById('duration');
    if (durationEl) {
        const hours = Math.floor(routeData.estimated_travel_time / 60);
        const minutes = Math.round(routeData.estimated_travel_time % 60);
        let timeDisplay = '';
        if (hours > 0) {
            timeDisplay = `${hours}h ${minutes}m`;
        } else {
            timeDisplay = `${minutes} min`;
        }
        durationEl.textContent = timeDisplay;
    }
    
    // Update congestion delay
    const delayEl = document.getElementById('congestion-delay');
    if (delayEl) {
        const delay = Math.round(routeData.congestion_delay);
        delayEl.textContent = delay + ' min';
    }
    
    // Update base duration
    const baseDurationEl = document.getElementById('base-duration');
    if (baseDurationEl) {
        const baseDuration = Math.round(routeData.base_travel_time);
        baseDurationEl.textContent = baseDuration + ' min';
    }
    
    // Update weather condition
    const weatherEl = document.getElementById('weather-condition');
    if (weatherEl && weatherData && weatherData.weather) {
        weatherEl.textContent = weatherData.weather.Conditions || '-';
    }
}

// Weather data
function getWeatherData() {
    return fetch('/api/weather')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const weather = data.weather;
                const formattedWeather = {
                    Temperature: weather['Temperature(F)'],
                    WindSpeed: weather['WindSpeed(mph)'],
                    Conditions: weather['Weather_Conditions'],
                    Humidity: weather['Humidity(%)'],
                    Visibility: weather['Visibility(mi)'],
                    Precipitation: weather['Precipitation(in)']
                };
                return { weather: formattedWeather };
            } else {
                throw new Error(data.error || "Failed to fetch weather data");
            }
        });
}

// Real time traffic with tom tom 

const tomtom_key = 'dxMYB1Al4a8PQe5hdMYriseUZWnxP36t';

const ic = {
    0: 'Unknown',
    1: 'Accident',
    2: 'Fog',
    3: 'Dangerous Conditions',
    4: 'Rain',
    5: 'Ice',
    6: 'Jam',
    7: 'Lane Closed',
    8: 'Road Closed',
    9: 'Road Works',
    10: 'Wind',
    11: 'Flooding',
    12: 'Detour',
    13: 'Cluster',
    14: 'Broken Down Vehicle'
};

const ty = {
    0: ['Unknown', 'rgba(0,0,0,0.25)'],
    1: ['Minor', 'rgba(0,153,0,0.25)'],
    2: ['Moderate', 'rgba(255,102,0,0.25)'],
    3: ['Major', 'rgba(255,0,0,0.25)'],
    4: ['Undefined', 'rgba(102,204,255,0.25)']
};

function getIncidents(bounds) {
    const boundsArr = [bounds.getSouthWest().lat, bounds.getSouthWest().lng, bounds.getNorthEast().lat, bounds.getNorthEast().lng];
    const query = `https://api.tomtom.com/traffic/services/4/incidentDetails/s3/${boundsArr.join()}/13/-1/json?projection=EPSG4326&key=${tomtom_key}`;

    fetch(query)
        .then(response => response.json())
        .then(data => renderIncidents(data.tm.poi))
        .catch(error => console.error('Error fetching traffic incidents:', error));
}

function renderIncidents(data) {
    incidentLayerGroup.clearLayers(); 
    const selectedType = document.getElementById('incident-filter').value;


    data.forEach(item => {
        if (item.p && item.p.y !== undefined && item.p.x !== undefined) {
            if (selectedType !="all" && item.ic.toString() != selectedType) return;
            const lat = item.p.y;
            const lon = item.p.x;

            const incidentType = ic[item.ic] || 'Unknown';
            const severity = ty[item.ty] || ['Unknown', 'rgba(0,0,0,0.25)'];
            const description = item.d || 'No description provided';

            const pinIcon = L.divIcon({
                className: 'custom-pin',
                html: `<div style="
                    background: ${severity[1]};
                    width: 16px;
                    height: 16px;
                    border-radius: 50% 50% 50% 0;
                    transform: rotate(-45deg);
                    box-shadow: 0 0 3px #000;
                    border: 1px solid black;
                "></div>`,
                iconSize: [16, 16],
                iconAnchor: [8, 16]
            });

            L.marker([lat, lon], { icon: pinIcon })
                .addTo(incidentLayerGroup)
                .bindPopup(`
                    <b>Type:</b> ${incidentType}<br>
                    <b>Description:</b> ${description}<br>
                    <b>Severity:</b> ${severity[0]}
                `);
        } 
    });
};