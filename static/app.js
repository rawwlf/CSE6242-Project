// Initialize the map
const map = L.map('map').setView([40.7128, -74.0060], 12); //Fixed to NYC Coordinates

// Add base layers
const lightLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19
}).addTo(map);

const darkLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19
});

const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
});

// Initialize layer groups
const routeLayer = L.layerGroup().addTo(map);
let startMarker = null;
let endMarker = null;
let heatLayer = null;

// Add layer control
const baseLayers = {
    "Light Mode": lightLayer,
    "Dark Mode": darkLayer,
    "Street Map": streetLayer
};

L.control.layers(baseLayers, null, {position: 'topleft'}).addTo(map);

// Legend for traffic congestion heatmap
const legend = L.control({position: 'bottomright'});
legend.onAdd = function(map) {
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = `
        <h4>Traffic Congestion</h4>
        <div style="background: linear-gradient(to right, blue, lime, yellow, red); height: 20px; margin-bottom: 5px;"></div>
        <span>Low</span>
        <span style="float: right;">High</span>
    `;
    return div;
};
legend.addTo(map);

//************************************* NEED TO UPDATE WITH ROUTING ALGORITHM *************************************

// Function to calculate a sample route (this is a placeholder used to create a route for display)
function calculateSampleRoute(start, end, weather, time, date) {

    return new Promise((resolve) => {

        // Generate sample route data around NYC
        const startPoint = [40.7580, -73.9855]; // Times Square
        const endPoint = [40.7829, -73.9654];   // Central Park

        // Create a winding route
        const routeCoords = [
            startPoint,
            [40.7600, -73.9800],
            [40.7650, -73.9750],
            [40.7700, -73.9700],
            [40.7750, -73.9680],
            [40.7800, -73.9670],
            endPoint
        ];

        // Create GeoJSON LineString
        const routeGeoJSON = {
            type: "Feature",
            properties: {
                distance: (Math.random() * 2 + 1.5).toFixed(1),
                duration: (Math.random() * 10 + 15).toFixed(0),
                weatherImpact: weather === 'clear' ? 0 : (weather === 'rain' ? 25 : weather === 'snow' ? 40 : 15)
            },
            geometry: {
                type: "LineString",
                coordinates: routeCoords.map(coord => [coord[1], coord[0]])
            }
        };

        // Generate random coordinates with traffic congestion severity
        const trafficSeverity = [];
        for (let i = 0; i < routeCoords.length - 1; i++) {
            const steps = 50;
            for (let j = 0; j < steps; j++) {
                const lat = routeCoords[i][0] + (routeCoords[i+1][0] - routeCoords[i][0]) * (Math.random() * 10);
                const lng = routeCoords[i][1] + (routeCoords[i+1][1] - routeCoords[i][1]) * (Math.random() * 10);
                const severity = 0.2 + (Math.random() * 0.6);
                trafficSeverity.push([lat, lng, severity]);
            }
        }

        resolve({
            route: routeGeoJSON,
            trafficSeverity: trafficSeverity,
            start: startPoint,
            end: endPoint
        });
    });
}
//******************************************************* END ******************************************************

// Function to display the route on the map
function displayRoute(routeData, weather) {

    // Add new route
    const routeLine = L.geoJSON(routeData.route, {
        style: getRouteStyle(weather),
        onEachFeature: function(feature, layer) {
            layer.bindPopup(`
                <b>Route Information</b><br>
                Distance: ${feature.properties.distance} miles<br>
                Estimated duration: ${feature.properties.duration} min<br>
                Weather impact: ${feature.properties.weatherImpact}%
            `);
        }
    }).addTo(routeLayer);

    // Add start and end markers
    if (startMarker) map.removeLayer(startMarker);
    if (endMarker) map.removeLayer(endMarker);

    // Create custom pinpoint icons
    const startPinIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
        shadowSize: [41, 41]
    });

    const endPinIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
        shadowSize: [41, 41]
    });

    // Add new pinpoint markers
    startMarker = L.marker(routeData.start, {
        icon: startPinIcon
    }).addTo(map).bindPopup(`
        <b>Start Point</b><br>
        ${document.getElementById('start-input').value}
    `);

    endMarker = L.marker(routeData.end, {
        icon: endPinIcon
    }).addTo(map).bindPopup(`
        <b>End Point</b><br>
        ${document.getElementById('end-input').value}
    `);

    // Add traffic congestion layer
    if (heatLayer) map.removeLayer(heatLayer);
    heatLayer = L.heatLayer(routeData.trafficSeverity, {
        radius: 25,
        blur: 15,
        maxZoom: 17,
        gradient: {0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 1: 'red'}
    }).addTo(map);


    // Update route info panel
    document.getElementById('distance').textContent = routeData.route.properties.distance;
    document.getElementById('duration').textContent = routeData.route.properties.duration;
    document.getElementById('weather-impact').textContent = routeData.route.properties.weatherImpact;
    document.getElementById('route-info').style.display = 'block';

    // Fit map to route bounds
    map.fitBounds(routeLine.getBounds(), {padding: [50, 50]});
}

// Get style for route based on weather
function getRouteStyle(weather) {
    const styles = {
        clear: {color: '#1E90FF', weight: 6, opacity: 0.9},
        rain: {color: '#4682B4', weight: 8, dashArray: '5, 5', opacity: 0.8},
        snow: {color: '#B0E0E6', weight: 8, dashArray: '10, 10', opacity: 0.7},
        fog: {color: '#A9A9A9', weight: 6, opacity: 0.6}
    };
    return styles[weather] || styles.clear;
}

// Event listener for calculate button
document.getElementById('calculate-route').addEventListener('click', function() {
    const start = document.getElementById('start-input').value;
    const end = document.getElementById('end-input').value;
    const weather = document.getElementById('weather-select').value;
    const date = document.getElementById('date-select').value;
    const time = document.getElementById('time-select').value;

    if (!start || !end) {
        alert('Please enter both start and end locations');
        return;
    }

    // Show loading state
    const button = this;
    button.disabled = true;
    button.textContent = 'Calculating...';

    //************************************* NEED TO UPDATE WITH ROUTING CALCULATOR **************************************
    
    // Calculate route (We would need to add connection to our route calculator)
    calculateSampleRoute(start, end, weather, time, date)
        .then(routeData => {
            displayRoute(routeData, weather);
        })
        .catch(error => {
            console.error('Error calculating route:', error);
            alert('Error calculating route. Please try again.');
        })
        .finally(() => {
            button.disabled = false;
            button.textContent = 'Calculate Route';
        });
        //******************************************************* END ******************************************************
});
