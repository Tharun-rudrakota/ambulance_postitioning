/**
 * AP 108 Emergency Command Center - Dashboard Logic
 * Interactive Leaflet mapping, optimization recomputation, and live accident dispatch simulation.
 */

// Global State
let map;
let baseLayers = {};
let currentBaseLayer = null;

let layers = {
  optAmbulances: L.layerGroup(),
  coverageCircles: L.layerGroup(),
  blackspots: L.layerGroup(),
  baseline: L.layerGroup(),
  mandals: L.layerGroup(),
  villages: L.layerGroup(),
  traumaCenters: L.layerGroup(),
  incidents: L.layerGroup()
};

let currentBlackspots = [];
let currentOptimalStations = [];

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  setupEventListeners();
  loadInitialData();
});

function initMap() {
  // Center of Andhra Pradesh
  map = L.map("map", {
    center: [15.9129, 79.9400],
    zoom: 7,
    zoomControl: false
  });

  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Define Basemap Providers: Street-level, Esri Roadways, Satellite, and Dark
  baseLayers = {
    streets: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }),
    esri_streets: L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
      attribution: 'Tiles &copy; Esri &mdash; DeLorme, NAVTEQ, TomTom',
      maxZoom: 19
    }),
    satellite: L.layerGroup([
      L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 19
      }),
      L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19
      })
    ]),
    dark: L.layerGroup([
      L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
        attribution: '&copy; Esri, DeLorme, NAVTEQ',
        maxZoom: 19,
        maxNativeZoom: 16
      }),
      L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        maxNativeZoom: 16
      })
    ])
  };

  // Default to Street Map showing each and every road, street, lane, and junction
  currentBaseLayer = baseLayers.streets;
  currentBaseLayer.addTo(map);

  // Add operational layer groups to map
  Object.values(layers).forEach(layer => layer.addTo(map));

  // Map Click Listener: User can click anywhere in AP to report an accident
  map.on("click", (e) => {
    handleAccidentReport(e.latlng.lat, e.latlng.lng);
  });
}

function setupEventListeners() {
  // Slider displays
  const ambSlider = document.getElementById("ambulance-slider");
  const ambVal = document.getElementById("ambulance-count-val");
  ambSlider.addEventListener("input", (e) => {
    ambVal.textContent = e.target.value;
  });

  const radSlider = document.getElementById("radius-slider");
  const radVal = document.getElementById("radius-count-val");
  radSlider.addEventListener("input", (e) => {
    radVal.textContent = `${e.target.value} km`;
  });

  // Layer toggles
  document.getElementById("layer-opt-ambulances").addEventListener("change", (e) => {
    toggleLayer(layers.optAmbulances, e.target.checked);
  });
  document.getElementById("layer-coverage-circles").addEventListener("change", (e) => {
    toggleLayer(layers.coverageCircles, e.target.checked);
  });
  document.getElementById("layer-blackspots").addEventListener("change", (e) => {
    toggleLayer(layers.blackspots, e.target.checked);
  });
  document.getElementById("layer-baseline").addEventListener("change", (e) => {
    toggleLayer(layers.baseline, e.target.checked);
  });
  document.getElementById("layer-mandals").addEventListener("change", (e) => {
    toggleLayer(layers.mandals, e.target.checked);
  });
  const layerVillagesEl = document.getElementById("layer-villages");
  if (layerVillagesEl) {
    layerVillagesEl.addEventListener("change", (e) => {
      toggleLayer(layers.villages, e.target.checked);
    });
  }
  document.getElementById("layer-trauma-centers").addEventListener("change", (e) => {
    toggleLayer(layers.traumaCenters, e.target.checked);
  });

  // Basemap Switcher (Streets, Esri Roadways, Satellite, Dark)
  const basemapSelect = document.getElementById("basemap-select");
  if (basemapSelect) {
    basemapSelect.addEventListener("change", (e) => {
      const selected = e.target.value;
      if (baseLayers[selected]) {
        map.removeLayer(currentBaseLayer);
        currentBaseLayer = baseLayers[selected];
        map.addLayer(currentBaseLayer);
      }
    });
  }

  // Bold Labels on Map Toggle
  const boldLabelsToggle = document.getElementById("layer-bold-labels");
  if (boldLabelsToggle) {
    boldLabelsToggle.addEventListener("change", (e) => {
      const mapEl = document.getElementById("map");
      if (e.target.checked) {
        mapEl.classList.remove("hide-bold-labels");
      } else {
        mapEl.classList.add("hide-bold-labels");
      }
    });
  }

  // Village Autocomplete Search Setup
  setupVillageSearch();

  // Recompute Optimization Button
  document.getElementById("btn-run-optimization").addEventListener("click", runOptimization);

  // District select change
  document.getElementById("district-select").addEventListener("change", (e) => {
    const district = e.target.value;
    if (district === "ALL") {
      document.getElementById("ambulance-slider").value = 45;
      document.getElementById("ambulance-count-val").textContent = "45";
    } else {
      document.getElementById("ambulance-slider").value = 14;
      document.getElementById("ambulance-count-val").textContent = "14";
    }
    runOptimization();
  });

  // Highway Crash Simulation Button
  document.getElementById("btn-simulate-highway-crash").addEventListener("click", () => {
    if (currentBlackspots.length > 0) {
      const randomSpot = currentBlackspots[Math.floor(Math.random() * currentBlackspots.length)];
      handleAccidentReport(randomSpot.lat, randomSpot.lng, randomSpot.location_name);
    } else {
      handleAccidentReport(16.3067, 80.4365, "Guntur Highway Stretch");
    }
  });
}

function toggleLayer(layer, isVisible) {
  if (isVisible) {
    map.addLayer(layer);
  } else {
    map.removeLayer(layer);
  }
}

async function loadInitialData() {
  try {
    // 1. Load Trauma Centers
    const traumaRes = await fetch("/api/trauma_centers");
    const traumaData = await traumaRes.json();
    renderTraumaCenters(traumaData.trauma_centers || []);

    // 2. Load Baseline Ambulances
    const baseRes = await fetch("/api/baseline?district=ALL");
    const baseData = await baseRes.json();
    renderBaselineAmbulances(baseData.ambulances || []);

    // 3. Load Mandals
    const mandalRes = await fetch("/api/mandals?district=ALL");
    const mandalData = await mandalRes.json();
    renderMandals(mandalData.mandals || []);

    // 4. Run initial optimization
    await runOptimization();
  } catch (err) {
    console.error("Error loading initial data:", err);
  }
}

async function runOptimization() {
  const district = document.getElementById("district-select").value;
  const algorithm = document.getElementById("algorithm-select").value;
  const numAmbulances = parseInt(document.getElementById("ambulance-slider").value);
  const radiusKm = parseFloat(document.getElementById("radius-slider").value);

  const btn = document.getElementById("btn-run-optimization");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Optimizing Positioning...';

  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        district: district,
        algorithm: algorithm,
        num_ambulances: numAmbulances,
        radius_km: radiusKm
      })
    });

    const data = await res.json();
    if (data.status === "success") {
      currentOptimalStations = data.optimization.selected_stations || [];
      renderOptimalAmbulances(currentOptimalStations, radiusKm);
      updateKPIs(data);

      // Load blackspots for this district or state
      const bsRes = await fetch(`/api/blackspots?district=${encodeURIComponent(district)}`);
      const bsData = await bsRes.json();
      currentBlackspots = bsData.blackspots || [];
      renderBlackspots(currentBlackspots);

      // Load villages for this district (or state sample)
      const vLimit = district === "ALL" ? 400 : 1000;
      const vRes = await fetch(`/api/villages?district=${encodeURIComponent(district)}&limit=${vLimit}`);
      const vData = await vRes.json();
      renderVillages(vData.villages || []);

      // Adjust map bounds
      if (district !== "ALL" && currentOptimalStations.length > 0) {
        const bounds = L.latLngBounds(currentOptimalStations.map(s => [s.lat, s.lng]));
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    }
  } catch (err) {
    console.error("Optimization failed:", err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Recompute Optimal Positioning';
  }
}

function updateKPIs(data) {
  const evalData = data.evaluation || {};
  const optMetrics = evalData.optimized || {};
  const deltas = evalData.deltas || {};

  // Coverage KPI
  const covVal = optMetrics.golden_hour_mandal_coverage_pct || 0;
  document.getElementById("kpi-coverage").textContent = `${covVal}%`;
  const covDeltaEl = document.getElementById("kpi-coverage-delta");
  covDeltaEl.innerHTML = `<i class="fa-solid fa-arrow-trend-up"></i> <span>+${deltas.coverage_gain_pct || 0}% vs Baseline</span>`;

  // Response Time KPI
  const timeVal = optMetrics.average_response_time_minutes || 0;
  document.getElementById("kpi-response-time").textContent = `${timeVal} min`;
  const timeDeltaEl = document.getElementById("kpi-time-delta");
  timeDeltaEl.innerHTML = `<i class="fa-solid fa-arrow-trend-down"></i> <span>-${deltas.response_time_reduction_minutes || 0} min faster</span>`;

  // Blackspot Protection KPI
  const bsVal = optMetrics.blackspot_coverage_pct || 0;
  document.getElementById("kpi-blackspot-coverage").textContent = `${bsVal}%`;
  document.getElementById("kpi-blackspot-delta").textContent = `${optMetrics.covered_blackspots_count || 0}/${optMetrics.total_blackspots || 0} Corridor Hotspots`;

  // Blindspots
  const blindspotsVal = optMetrics.severely_delayed_mandals_count || 0;
  document.getElementById("kpi-blindspots").textContent = blindspotsVal;
  document.getElementById("kpi-blindspots-delta").textContent = `${deltas.blindspots_eliminated || 0} Blindspots Resolved`;
}

function renderOptimalAmbulances(stations, radiusKm) {
  layers.optAmbulances.clearLayers();
  layers.coverageCircles.clearLayers();

  const radiusMeters = radiusKm * 1000;

  stations.forEach((stn, idx) => {
    const isALS = stn.allocated_vehicle_type && stn.allocated_vehicle_type.includes("ALS");
    const markerColor = isALS ? "#10b981" : "#06b6d4";

    const customIcon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div style="background:${markerColor}; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; border:2px solid #fff; box-shadow:0 0 12px ${markerColor};">
          <i class="fa-solid fa-truck-medical" style="font-size:13px;"></i>
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    const marker = L.marker([stn.lat, stn.lng], { icon: customIcon });
    marker.bindTooltip(`<b>${stn.name}</b> <span class="amb-type-badge">${stn.allocated_vehicle_type || 'BLS'}</span>`, {
      permanent: true,
      direction: "bottom",
      className: "bold-map-label ambulance-label",
      offset: [0, 8]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:180px;">
        <strong style="color:${markerColor}; font-size:13px;">${stn.name}</strong><br>
        <strong>District:</strong> ${stn.district}<br>
        <strong>Mandal:</strong> ${stn.mandal}<br>
        <strong>Vehicle Class:</strong> <span style="font-weight:700; color:${markerColor};">${stn.allocated_vehicle_type || 'BLS'}</span><br>
        <strong>Paramedic Crew:</strong> ${stn.paramedic_crew || 2} Officers<br>
        <strong>Coverage Radius:</strong> ${radiusKm} km (~15 min response)<br>
        <strong>Covered Nodes:</strong> ${stn.covered_demand_count || 0}
      </div>
    `);
    layers.optAmbulances.addLayer(marker);

    // Coverage Circle Buffer
    const circle = L.circle([stn.lat, stn.lng], {
      radius: radiusMeters,
      color: markerColor,
      weight: 1.5,
      opacity: 0.8,
      fillColor: markerColor,
      fillOpacity: 0.12
    });
    layers.coverageCircles.addLayer(circle);
  });
}

function renderBlackspots(blackspots) {
  layers.blackspots.clearLayers();

  blackspots.forEach((bs) => {
    const customIcon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div class="marker-blackspot" style="width:20px; height:20px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px;">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    const marker = L.marker([bs.lat, bs.lng], { icon: customIcon });
    marker.bindTooltip(`<b>⚠️ ${bs.location_name}</b> <small style="color:#fca5a5;">(${bs.corridor})</small>`, {
      direction: "top",
      className: "bold-map-label blackspot-label",
      offset: [0, -8]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:200px;">
        <strong style="color:#ef4444; font-size:13px;"><i class="fa-solid fa-triangle-exclamation"></i> Blackspot: ${bs.location_name}</strong><br>
        <strong>Corridor:</strong> ${bs.corridor}<br>
        <strong>District:</strong> ${bs.district}<br>
        <strong>Annual Fatalities:</strong> ${bs.fatalities_annual}<br>
        <strong>Annual Injuries:</strong> ${bs.injuries_annual}<br>
        <strong>Severity Index:</strong> ${bs.severity_index}<br>
        <strong>Primary Cause:</strong> ${bs.accident_causes}<br>
        <strong>High Risk Window:</strong> ${bs.peak_time_window}<br>
        <button onclick="handleAccidentReport(${bs.lat}, ${bs.lng}, '${bs.location_name.replace(/'/g, "\\'")}')" style="margin-top:6px; background:#ef4444; color:#fff; border:none; border-radius:4px; padding:4px 8px; font-size:11px; cursor:pointer;">
          <i class="fa-solid fa-truck-medical"></i> Test Dispatch Here
        </button>
      </div>
    `);
    layers.blackspots.addLayer(marker);
  });
}

function renderTraumaCenters(traumaCenters) {
  layers.traumaCenters.clearLayers();

  traumaCenters.forEach(tc => {
    const icon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div class="marker-trauma" style="width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px;">
          <i class="fa-solid fa-hospital"></i>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });

    const marker = L.marker([tc.lat, tc.lng], { icon: icon });
    marker.bindTooltip(`<b>🏥 ${tc.name}</b>`, {
      permanent: true,
      direction: "bottom",
      className: "bold-map-label trauma-label",
      offset: [0, 8]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a;">
        <strong style="color:#8b5cf6; font-size:13px;"><i class="fa-solid fa-hospital"></i> ${tc.name}</strong><br>
        <strong>Level:</strong> ${tc.level}<br>
        <strong>District:</strong> ${tc.district}
      </div>
    `);
    layers.traumaCenters.addLayer(marker);
  });
}

function renderBaselineAmbulances(ambulances) {
  layers.baseline.clearLayers();

  ambulances.forEach(amb => {
    const icon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div class="marker-baseline" style="width:18px; height:18px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:9px;">
          <i class="fa-solid fa-truck-medical"></i>
        </div>
      `,
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });

    const marker = L.marker([amb.lat, amb.lng], { icon: icon });
    marker.bindTooltip(`<b>${amb.station_name}</b>`, {
      direction: "top",
      className: "bold-map-label",
      offset: [0, -6]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a;">
        <strong>Baseline 108 Base: ${amb.station_name}</strong><br>
        <strong>District:</strong> ${amb.district}<br>
        <strong>Status:</strong> Pre-Optimization Static Base
      </div>
    `);
    layers.baseline.addLayer(marker);
  });
}

function renderMandals(mandals) {
  layers.mandals.clearLayers();

  mandals.forEach(m => {
    const circle = L.circleMarker([m.lat, m.lng], {
      radius: 3.5,
      color: "#3b82f6",
      fillColor: "#3b82f6",
      fillOpacity: 0.6,
      weight: 1
    });

    circle.bindTooltip(`<b>${m.mandal_name} Mandal</b>`, {
      direction: "top",
      className: "bold-map-label mandal-label",
      offset: [0, -4]
    });

    circle.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a;">
        <strong>${m.mandal_name} Mandal</strong><br>
        <strong>District:</strong> ${m.district}<br>
        <strong>Population:</strong> ${m.population.toLocaleString()}<br>
        <strong>Risk Score:</strong> ${m.risk_score} / 10.0<br>
        <strong>Annual Accidents:</strong> ${m.annual_accidents}
      </div>
    `);
    layers.mandals.addLayer(circle);
  });
}

function renderVillages(villages) {
  layers.villages.clearLayers();

  villages.forEach(v => {
    const isPhc = v.has_phc;
    const color = isPhc ? "#10b981" : "#eab308";
    const circle = L.circleMarker([v.lat, v.lng], {
      radius: isPhc ? 3.5 : 2.5,
      color: color,
      fillColor: color,
      fillOpacity: 0.75,
      weight: 1
    });

    circle.bindTooltip(`<b>${v.village_name}</b> <small style="color:#fef08a;">(${v.mandal})</small>`, {
      direction: "top",
      className: "bold-map-label village-label",
      offset: [0, -4]
    });

    circle.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:180px;">
        <strong style="color:${color}; font-size:13px;"><i class="fa-solid fa-tree-city"></i> ${v.village_name}</strong><br>
        <strong>Gram Panchayat:</strong> ${v.gram_panchayat || v.village_name}<br>
        <strong>Mandal:</strong> ${v.mandal}<br>
        <strong>District:</strong> ${v.district}<br>
        <strong>Population:</strong> ${v.population.toLocaleString()}<br>
        <strong>Healthcare:</strong> ${isPhc ? '<span style="color:#10b981; font-weight:600;">PHC / Sub-Center</span>' : 'ASHA / Sub-center Network'}<br>
        <button onclick="handleAccidentReport(${v.lat}, ${v.lng}, '${v.village_name.replace(/'/g, "\\'")} (${v.mandal} Mdl)')" style="margin-top:6px; background:#ef4444; color:#fff; border:none; border-radius:4px; padding:4px 8px; font-size:11px; cursor:pointer;">
          <i class="fa-solid fa-truck-medical"></i> Dispatch Emergency Here
        </button>
      </div>
    `);
    layers.villages.addLayer(circle);
  });
}

function setupVillageSearch() {
  const searchInput = document.getElementById("village-search-input");
  const resultsDropdown = document.getElementById("village-search-results");
  if (!searchInput || !resultsDropdown) return;

  let debounceTimer = null;

  searchInput.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    clearTimeout(debounceTimer);

    if (val.length < 2) {
      resultsDropdown.innerHTML = "";
      resultsDropdown.classList.add("hidden");
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search_village?q=${encodeURIComponent(val)}`);
        const data = await res.json();
        const results = data.results || [];

        if (results.length === 0) {
          resultsDropdown.innerHTML = '<div style="padding:10px; color:var(--text-muted); font-size:12px; text-align:center;">No matching villages found</div>';
          resultsDropdown.classList.remove("hidden");
          return;
        }

        resultsDropdown.innerHTML = results.map(v => `
          <div class="village-search-item" data-lat="${v.lat}" data-lng="${v.lng}" data-name="${v.village_name}" data-mandal="${v.mandal}" data-district="${v.district}">
            <div class="v-name">
              <span><i class="fa-solid fa-tree-city" style="color:#eab308; margin-right:6px;"></i>${v.village_name}</span>
              ${v.has_phc ? '<span class="badge-phc">PHC</span>' : ''}
            </div>
            <div class="v-meta">
              <span>Mandal: <strong>${v.mandal}</strong> | District: <strong>${v.district}</strong> | Pop: ${v.population.toLocaleString()}</span>
            </div>
          </div>
        `).join("");

        resultsDropdown.classList.remove("hidden");

        // Add click listeners to items
        resultsDropdown.querySelectorAll(".village-search-item").forEach(item => {
          item.addEventListener("click", () => {
            const lat = parseFloat(item.dataset.lat);
            const lng = parseFloat(item.dataset.lng);
            const vName = item.dataset.name;
            const mandal = item.dataset.mandal;
            const district = item.dataset.district;

            searchInput.value = `${vName} (${mandal}, ${district})`;
            resultsDropdown.classList.add("hidden");

            // Pan and zoom map to village
            map.flyTo([lat, lng], 13, { duration: 1.2 });

            // Trigger emergency accident / dispatch test for this village
            handleAccidentReport(lat, lng, `${vName} Village (${mandal} Mandal, ${district})`);
          });
        });
      } catch (err) {
        console.error("Village search failed:", err);
      }
    }, 250);
  });

  // Close dropdown on click outside
  document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !resultsDropdown.contains(e.target)) {
      resultsDropdown.classList.add("hidden");
    }
  });
}

async function handleAccidentReport(lat, lng, locationLabel = "") {
  layers.incidents.clearLayers();

  // Pulse accident marker
  const crashIcon = L.divIcon({
    className: "custom-div-icon",
    html: `
      <div style="background:#ef4444; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; border:3px solid #fff; box-shadow:0 0 20px #ef4444; animation:blackspotPulse 1.2s infinite ease-out;">
        <i class="fa-solid fa-car-burst" style="font-size:16px;"></i>
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17]
  });

  const incidentMarker = L.marker([lat, lng], { icon: crashIcon }).addTo(layers.incidents);
  incidentMarker.bindTooltip(`<b>🚨 ACCIDENT: ${locationLabel || 'Emergency Crash Scene'}</b>`, {
    permanent: true,
    direction: "top",
    className: "bold-map-label blackspot-label",
    offset: [0, -14]
  });

  // Dispatch API Call
  try {
    const res = await fetch("/api/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: lat, lng: lng, severity: "Critical" })
    });

    const data = await res.json();
    if (data.status === "success" && data.dispatch) {
      const d = data.dispatch;
      const amb = d.dispatched_ambulance;
      const metrics = d.response_metrics;
      const nearestHosp = d.nearest_hospital || d.recommended_trauma_center;
      const apexCenter = d.apex_referral_center || {};

      // 1. Draw Ambulance -> Crash Site Routing Polyline (Emerald Green)
      const ambWaypoints = d.route_waypoints || [[amb.lat, amb.lng], [lat, lng]];
      const ambRouteLine = L.polyline(ambWaypoints, {
        color: metrics.status_color || "#10b981",
        weight: 5,
        opacity: 0.9,
        dashArray: "8, 6"
      }).addTo(layers.incidents);

      // Add animated ambulance icon at station
      const ambIcon = L.divIcon({
        className: "custom-div-icon",
        html: `
          <div style="background:#10b981; width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; border:2px solid #fff; box-shadow:0 0 15px #10b981;">
            <i class="fa-solid fa-truck-fast" style="font-size:14px;"></i>
          </div>
        `,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
      L.marker([amb.lat, amb.lng], { icon: ambIcon }).addTo(layers.incidents);

      // 2. Draw Crash Site -> Nearest Local Referral Hospital Transfer Route (Purple)
      const hospWaypoints = d.hospital_transfer_waypoints || [[lat, lng], [nearestHosp.lat, nearestHosp.lng]];
      const hospRouteLine = L.polyline(hospWaypoints, {
        color: "#a855f7",
        weight: 4,
        opacity: 0.85,
        dashArray: "6, 8"
      }).addTo(layers.incidents);

      // Highlight the Nearest Referral Hospital with an animated pulse marker
      const hospIcon = L.divIcon({
        className: "custom-div-icon",
        html: `
          <div style="background:#8b5cf6; width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; border:2px solid #fff; box-shadow:0 0 16px #8b5cf6;">
            <i class="fa-solid fa-hospital" style="font-size:14px;"></i>
          </div>
        `,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
      const hospMarker = L.marker([nearestHosp.lat, nearestHosp.lng], { icon: hospIcon }).addTo(layers.incidents);
      hospMarker.bindTooltip(`<b>🏥 ${nearestHosp.name}</b> <small style="color:#e9d5ff;">(${nearestHosp.distance_km} km / ${nearestHosp.eta_minutes || '--'} min)</small>`, {
        permanent: true,
        direction: "top",
        className: "bold-map-label trauma-label",
        offset: [0, -10]
      });
      hospMarker.bindPopup(`
        <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:190px;">
          <strong style="color:#8b5cf6; font-size:13px;"><i class="fa-solid fa-hospital"></i> ${nearestHosp.name}</strong><br>
          <strong>Type:</strong> ${nearestHosp.level}<br>
          <strong>Town/District:</strong> ${nearestHosp.town || nearestHosp.district}<br>
          <strong>Distance from Crash:</strong> ${nearestHosp.distance_km} km<br>
          <strong>Transit ETA:</strong> ${nearestHosp.eta_minutes || '--'} mins
        </div>
      `);

      // 3. Show Dispatch Telemetry Panel
      const box = document.getElementById("dispatch-result-box");
      box.classList.remove("hidden");
      box.style.borderColor = metrics.status_color;

      const indicator = document.getElementById("dispatch-status-indicator");
      indicator.style.backgroundColor = metrics.status_color;
      indicator.style.boxShadow = `0 0 10px ${metrics.status_color}`;

      document.getElementById("dispatch-status-label").textContent = `${metrics.status_label} (Ambulance ETA: ${metrics.estimated_eta_minutes} min)`;
      document.getElementById("disp-unit-name").textContent = `${amb.name} (${amb.mandal})`;
      document.getElementById("disp-unit-type").textContent = amb.vehicle_type;
      document.getElementById("disp-distance").textContent = `${metrics.road_distance_km} km`;
      document.getElementById("disp-eta").textContent = `${metrics.estimated_eta_minutes} min`;

      // Nearest local hospital
      document.getElementById("disp-local-hospital").textContent = `${nearestHosp.name} (${nearestHosp.level})`;
      document.getElementById("disp-hospital-eta").textContent = `${nearestHosp.distance_km} km (~${nearestHosp.eta_minutes || '--'} min)`;
      document.getElementById("disp-apex-hospital").textContent = apexCenter.name ? `${apexCenter.name} (${apexCenter.distance_km} km)` : '--';

      // Incident popup on crash marker
      incidentMarker.bindPopup(`
        <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:210px;">
          <strong style="color:#ef4444; font-size:13px;"><i class="fa-solid fa-car-burst"></i> Emergency Crash Site</strong><br>
          ${locationLabel ? `<strong>Location:</strong> ${locationLabel}<br>` : ''}
          <strong>Dispatched:</strong> ${amb.name} (${metrics.road_distance_km} km)<br>
          <strong>Ambulance Arrival:</strong> <span style="font-weight:700; color:${metrics.status_color};">${metrics.estimated_eta_minutes} min</span><br>
          <hr style="margin:4px 0; border:0; border-top:1px solid #e2e8f0;">
          <strong style="color:#8b5cf6;"><i class="fa-solid fa-hospital"></i> Nearest Hospital:</strong> ${nearestHosp.name}<br>
          <strong>Hospital Transfer:</strong> ${nearestHosp.distance_km} km (~${nearestHosp.eta_minutes} min)<br>
          <strong>Golden Hour Status:</strong> ${metrics.golden_hour_status}
        </div>
      `).openPopup();

      // Fit map bounds to encompass Ambulance, Crash Site, and Nearest Hospital
      const combinedBounds = L.latLngBounds([
        [amb.lat, amb.lng],
        [lat, lng],
        [nearestHosp.lat, nearestHosp.lng]
      ]);
      map.fitBounds(combinedBounds, { padding: [60, 60] });
    }
  } catch (err) {
    console.error("Dispatch simulation error:", err);
  }
}
