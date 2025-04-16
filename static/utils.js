function buildMap()  {const bucket_name = 'cse6242-project-team81';

    const state_year_data = `s3://${bucket_name}/state_year_data.csv`;
    const location_counts = `s3://${bucket_name}/filtered_location_counts.csv`;
    const us_states = `s3://${bucket_name}/us-states.json`;
    
    // Load and parse the data
    Promise.all([
        fetch(state_year_data).then(res => res.text()).then(d3.csvParse),
        fetch(location_counts).then(res => res.text()).then(d3.csvParse),
        fetch(us_states).then(res => res.json())
    ])
    .then(([state_year_data, location_counts, us_states]) => {
    
        var map = L.map('map').setView([37.8, -96], 4);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
          }).addTo(map);
    
          // ----- Choropleth Layer Setup -----
          // Define a function to choose colors based on the feature's property
          function getColor(d) {
            return d > 1000 ? '#800026' :
                   d > 500  ? '#BD0026' :
                   d > 200  ? '#E31A1C' :
                   d > 100  ? '#FC4E2A' :
                   d > 50   ? '#FD8D3C' :
                   d > 20   ? '#FEB24C' :
                   d > 10   ? '#FED976' :
                              '#FFEDA0';
          }
    
          // Apply style to each feature in the GeoJSON
          function style(feature) {
            return {
              fillColor: getColor(feature.properties.value), // Adjust 'value' to match your property name
              weight: 2,
              opacity: 1,
              color: 'white',
              dashArray: '3',
              fillOpacity: 0.7
            };
          }
    
          // Create the choropleth layer and add popups
          var choroplethLayer = L.geoJson(us_states, {
            style: style,
            onEachFeature: function(feature, layer) {
              layer.bindPopup("Value: " + feature.properties.value);
            }
          }).addTo(map);
    
          // ----- Heatmap Layer Setup -----
          // Convert CSV data into an array of points for leaflet.heat.
          // Each point should be in the form: [latitude, longitude, intensity]
          var heatArray = location_counts.map(d => [
            parseFloat(d.Start_Lat), 
            parseFloat(d.Start_Lng), 
            parseFloat(d.Count) || 1  // default weight to 1 if not provided
          ]);
    
          // Create the heatmap layer with desired options and add it to the map.
          var heat = L.heatLayer(heatArray, {
            radius: 25,
            blur: 15,
            maxZoom: 17,
          }).addTo(map);
        
    })
    .catch(error => {
        console.error('Error loading files:', error);
    });
}

// function formatHeatMapData(data) {
//     return data.map(item => [item.Start_Lat, item.Start_Lng, item.Count]);
// }

// function formatChoroplethData(data) {
//     return data.map(item => ({
//         code: item.code,
//         count: item.Count
//     }));
// }