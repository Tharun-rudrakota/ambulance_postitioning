/**
 * AP 108 Emergency Command Center - Dashboard Logic
 * Interactive Leaflet mapping, optimization recomputation, and live accident dispatch simulation.
 */

// Global State
let map;
let baseLayers = {};
let currentBaseLayer = null;

let layers = {
  districtBoundary: L.layerGroup(),
  manualAmbulances: L.layerGroup(),
  optAmbulances: L.layerGroup(),
  coverageCircles: L.layerGroup(),
  blackspots: L.layerGroup(),
  baseline: L.layerGroup(),
  mandals: L.layerGroup(),
  villages: L.layerGroup(),
  villageDanger: L.layerGroup(),
  traumaCenters: L.layerGroup(),
  incidents: L.layerGroup()
};

let currentBlackspots = [];
let currentOptimalStations = [];
let currentReadyStations = [];
let customAmbulances = [];
let isManualPlacementMode = false;
let allMandals = [];
let currentDistrictPlaces = [];
let currentDistrictBounds = null;
let lastIncident = { lat: 16.312, lng: 80.451, label: "Emergency Scene", district: "General", mandal: "Local" };

function matchDistrict(d1, d2) {
  if (!d1 || !d2) return false;
  const aliases = {
    "nellore": "sps nellore",
    "sps nellore": "sps nellore",
    "sri potti sriramulu nellore": "sps nellore",
    "kadapa": "ysr kadapa",
    "ysr kadapa": "ysr kadapa",
    "ysr": "ysr kadapa",
    "konaseema": "dr. b.r. ambedkar konaseema",
    "dr. b.r. ambedkar konaseema": "dr. b.r. ambedkar konaseema",
    "manyam": "parvathipuram manyam",
    "parvathipuram manyam": "parvathipuram manyam",
    "alluri": "alluri sitharama raju",
    "asr": "alluri sitharama raju",
    "alluri sitharama raju": "alluri sitharama raju"
  };
  const k1 = aliases[d1.trim().toLowerCase()] || d1.trim().toLowerCase();
  const k2 = aliases[d2.trim().toLowerCase()] || d2.trim().toLowerCase();
  return k1 == k2;
}

const AP_COASTLINE_REF = [
  [13.40, 80.10], [13.60, 80.11], [13.80, 80.12], [14.00, 80.08], [14.15, 80.07],
  [14.28, 80.09], [14.45, 80.13], [14.65, 80.09], [14.90, 80.00], [15.10, 80.01],
  [15.25, 80.03], [15.45, 80.07], [15.65, 80.25], [15.80, 80.45], [15.92, 80.60],
  [16.00, 80.85], [16.18, 81.18], [16.32, 81.65], [16.50, 81.88], [16.70, 82.08],
  [16.95, 82.20], [17.15, 82.30], [17.35, 82.54], [17.55, 82.94], [17.70, 83.27],
  [17.89, 83.39], [18.12, 83.76], [18.33, 84.05], [18.55, 84.28], [18.88, 84.52],
  [19.20, 84.68]
];

function getMaxCoastlineLng(lat) {
  const pts = AP_COASTLINE_REF;
  if (lat <= pts[0][0]) return pts[0][1];
  if (lat >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
  for (let i = 0; i < pts.length - 1; i++) {
    if (pts[i][0] <= lat && lat <= pts[i + 1][0]) {
      const t = (lat - pts[i][0]) / (pts[i + 1][0] - pts[i][0]);
      return pts[i][1] + t * (pts[i + 1][1] - pts[i][1]);
    }
  }
  return 84.0;
}

function clampCoastline(lat, lng, buffer = 0.018) {
  const maxLng = getMaxCoastlineLng(lat) - buffer;
  if (lng > maxLng) {
    const over = lng - maxLng;
    return Math.round((maxLng - Math.min(0.04, over * 0.4) - 0.005) * 100000) / 100000;
  }
  return lng;
}

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

  // Map Click Listener: User can place ambulance manually OR trigger accident dispatch
  map.on("click", (e) => {
    if (isManualPlacementMode) {
      openPlacementConfirmationPopup(e.latlng.lat, e.latlng.lng);
    } else {
      handleAccidentReport(e.latlng.lat, e.latlng.lng);
    }
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
  const layerManualAmbsEl = document.getElementById("layer-manual-ambulances");
  if (layerManualAmbsEl) {
    layerManualAmbsEl.addEventListener("change", (e) => {
      toggleLayer(layers.manualAmbulances, e.target.checked);
    });
  }

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
  const layerVillageDangerEl = document.getElementById("layer-village-danger");
  if (layerVillageDangerEl) {
    layerVillageDangerEl.addEventListener("change", (e) => {
      toggleLayer(layers.villageDanger, e.target.checked);
    });
  }
  document.getElementById("layer-trauma-centers").addEventListener("change", (e) => {
    toggleLayer(layers.traumaCenters, e.target.checked);
  });

  // Toggle Manual Placement Mode Buttons
  const btnTogglePlacement = document.getElementById("btn-toggle-manual-placement");
  if (btnTogglePlacement) {
    btnTogglePlacement.addEventListener("click", () => {
      toggleManualPlacementMode();
    });
  }

  const btnQuickPlace = document.getElementById("btn-quick-place-here");
  if (btnQuickPlace) {
    btnQuickPlace.addEventListener("click", () => {
      toggleManualPlacementMode(true);
    });
  }

  const btnCancelPlacement = document.getElementById("btn-cancel-placement");
  if (btnCancelPlacement) {
    btnCancelPlacement.addEventListener("click", () => {
      toggleManualPlacementMode(false);
    });
  }

  // Place Ambulance Position Nearer Button
  const btnPlaceNearer = document.getElementById("btn-place-ambulance-nearer");
  if (btnPlaceNearer) {
    btnPlaceNearer.addEventListener("click", () => {
      placeAmbulanceNearer(lastIncident.lat, lastIncident.lng, lastIncident.label, lastIncident.district, lastIncident.mandal);
    });
  }

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
      const distMandals = allMandals.filter(m => matchDistrict(m.district, district));
      const mCount = distMandals.length || 20;
      document.getElementById("ambulance-slider").max = Math.max(mCount + 10, 50);
      document.getElementById("ambulance-slider").value = mCount;
      document.getElementById("ambulance-count-val").textContent = `${mCount} (All Mandals Covered)`;
    }
    runOptimization();
  });

  // Places Explorer Filters
  const explorerMandalFilter = document.getElementById("explorer-mandal-filter");
  if (explorerMandalFilter) {
    explorerMandalFilter.addEventListener("change", () => {
      renderFilteredPlaces();
    });
  }

  const explorerPlaceSearch = document.getElementById("explorer-place-search");
  if (explorerPlaceSearch) {
    explorerPlaceSearch.addEventListener("input", () => {
      renderFilteredPlaces();
    });
  }

  const btnZoomDist = document.getElementById("btn-zoom-district");
  if (btnZoomDist) {
    btnZoomDist.addEventListener("click", () => {
      fitDistrictBounds();
    });
  }

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
    // 0. Load Permanent Manually Placed Ambulances from Server & localStorage
    await loadManualAmbulances();

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
    allMandals = mandalData.mandals || [];
    renderMandals(allMandals);

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
      currentReadyStations = data.optimization.ready_mandal_stations || [];
      renderOptimalAmbulances(currentOptimalStations, currentReadyStations, radiusKm);
      renderManualAmbulances(customAmbulances);
      updateKPIs(data);

      // Load blackspots for this district or state
      const bsRes = await fetch(`/api/blackspots?district=${encodeURIComponent(district)}`);
      const bsData = await bsRes.json();
      currentBlackspots = bsData.blackspots || [];
      renderBlackspots(currentBlackspots);

      // Load mandals specifically for this district (or all if statewide)
      const mRes = await fetch(`/api/mandals?district=${encodeURIComponent(district)}`);
      const mData = await mRes.json();
      const districtMandals = mData.mandals || [];
      renderMandals(districtMandals);

      // Load baseline ambulances for this district (or all if statewide)
      const bRes = await fetch(`/api/baseline?district=${encodeURIComponent(district)}`);
      const bData = await bRes.json();
      renderBaselineAmbulances(bData.ambulances || []);

      // Load villages for this district (load 100% of all villages without cut-off)
      const vLimit = district === "ALL" ? 400 : 10000;
      const vRes = await fetch(`/api/villages?district=${encodeURIComponent(district)}&limit=${vLimit}`);
      const vData = await vRes.json();
      const districtVillages = vData.villages || [];
      renderVillages(districtVillages);

      // Load village danger spots for this district (100% of all danger zones)
      const vdRes = await fetch(`/api/village_danger_spots?district=${encodeURIComponent(district)}&limit=${vLimit}`);
      const vdData = await vdRes.json();
      const districtDangerSpots = vdData.danger_spots || [];
      renderVillageDangerSpots(districtDangerSpots);

      // Load district details & perimeter boundary hull
      const ddRes = await fetch(`/api/district_details?district=${encodeURIComponent(district)}`);
      const ddData = await ddRes.json();
      if (ddData.status === "success" && !ddData.is_statewide && ddData.boundary_hull) {
        renderDistrictBoundary(ddData.boundary_hull, ddData.district, ddData.total_mandals, ddData.total_villages);
      } else {
        layers.districtBoundary.clearLayers();
      }

      // Update Places Explorer in sidebar with each and every place
      updateDistrictPlacesExplorer(ddData, districtMandals, districtVillages, districtDangerSpots);

      // Adjust map bounds to encompass all places in the total selected district
      if (district !== "ALL") {
        const boundsCoords = [];
        currentOptimalStations.forEach(s => boundsCoords.push([s.lat, clampCoastline(s.lat, s.lng)]));
        currentReadyStations.forEach(s => boundsCoords.push([s.lat, clampCoastline(s.lat, s.lng)]));
        districtMandals.forEach(m => boundsCoords.push([m.lat, clampCoastline(m.lat, m.lng)]));
        districtVillages.forEach(v => boundsCoords.push([v.lat, clampCoastline(v.lat, v.lng)]));
        if (boundsCoords.length > 0) {
          currentDistrictBounds = L.latLngBounds(boundsCoords);
          map.fitBounds(currentDistrictBounds, { padding: [40, 40] });
        }
      } else {
        currentDistrictBounds = L.latLngBounds([[12.6, 76.8], [19.2, 84.7]]);
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

function renderOptimalAmbulances(stations, readyStations = [], radiusKm = 12.0) {
  layers.optAmbulances.clearLayers();
  layers.coverageCircles.clearLayers();

  const radiusMeters = radiusKm * 1000;

  // 1. Render Priority ALS Stations
  stations.forEach((stn, idx) => {
    const isALS = stn.allocated_vehicle_type && stn.allocated_vehicle_type.includes("ALS");
    const markerColor = isALS ? "#10b981" : "#06b6d4";
    const safeLng = clampCoastline(stn.lat, stn.lng);

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

    const marker = L.marker([stn.lat, safeLng], { icon: customIcon });
    marker.bindTooltip(`<b>${stn.name}</b> <span class="amb-type-badge">${stn.allocated_vehicle_type || 'ALS'}</span>`, {
      permanent: true,
      direction: "bottom",
      className: "bold-map-label ambulance-label",
      offset: [0, 8]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:190px;">
        <strong style="color:${markerColor}; font-size:13px;"><i class="fa-solid fa-truck-medical"></i> ${stn.name}</strong><br>
        <strong>District:</strong> ${stn.district}<br>
        <strong>Mandal:</strong> ${stn.mandal}<br>
        <strong>Vehicle Class:</strong> <span style="font-weight:700; color:${markerColor};">${stn.allocated_vehicle_type || 'ALS'}</span><br>
        <strong>Paramedic Crew:</strong> ${stn.paramedic_crew || 3} Officers<br>
        <strong>Equipment:</strong> ${(stn.equipment || []).join(", ") || 'Ventilator, Defibrillator, Cardiac Monitor'}<br>
        <strong>Coverage Radius:</strong> ${radiusKm} km (~15 min response)<br>
        <span style="background:#dcfce7; color:#15803d; font-weight:700; padding:1px 6px; border-radius:4px; font-size:10px;">Primary ALS Corridor Interceptor</span>
      </div>
    `);
    layers.optAmbulances.addLayer(marker);

    // Coverage Circle Buffer
    const circle = L.circle([stn.lat, safeLng], {
      radius: radiusMeters,
      color: markerColor,
      weight: 1.5,
      opacity: 0.8,
      fillColor: markerColor,
      fillOpacity: 0.12
    });
    layers.coverageCircles.addLayer(circle);
  });

  // 2. Render Ready Mandal Stations (guarantees every mandal including Duttalur has a stationed ready ambulance)
  readyStations.forEach(stn => {
    const safeLng = clampCoastline(stn.lat, stn.lng);
    const customIcon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div style="background:#0284c7; width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; border:2px solid #fff; box-shadow:0 0 10px rgba(2, 132, 199, 0.8);">
          <i class="fa-solid fa-truck-medical" style="font-size:12px;"></i>
        </div>
      `,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    const marker = L.marker([stn.lat, safeLng], { icon: customIcon });
    marker.bindTooltip(`<b>${stn.name}</b> <span class="amb-type-badge ready-badge">Ready 108 Post</span>`, {
      permanent: true,
      direction: "bottom",
      className: "bold-map-label ambulance-label ready-ambulance-label",
      offset: [0, 8]
    });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:200px;">
        <strong style="color:#0284c7; font-size:13px;"><i class="fa-solid fa-truck-medical"></i> ${stn.name}</strong><br>
        <strong>Class:</strong> Basic Life Support (BLS) - Ready Post<br>
        <strong>District:</strong> ${stn.district} | <strong>Mandal:</strong> ${stn.mandal}<br>
        <strong>Status:</strong> <span style="background:#dcfce7; color:#15803d; font-weight:700; padding:1px 6px; border-radius:4px;">Active & Ready</span><br>
        <strong>Paramedic Crew:</strong> 2 EMT Officers<br>
        <strong>Equipment:</strong> Oxygen Cylinder, Stretcher, First Aid Kit, Suction Unit<br>
        <hr style="margin:5px 0; border:0; border-top:1px solid #e2e8f0;">
        <small style="color:#64748b;">Permanently stationed at ${stn.mandal} Mandal HQ for &lt; 15 min rapid village response.</small>
      </div>
    `);
    layers.optAmbulances.addLayer(marker);
  });
}

function renderBlackspots(blackspots) {
  layers.blackspots.clearLayers();

  blackspots.forEach((bs) => {
    const safeLng = clampCoastline(bs.lat, bs.lng);
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

    const marker = L.marker([bs.lat, safeLng], { icon: customIcon });
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
        <button onclick="handleAccidentReport(${bs.lat}, ${safeLng}, '${bs.location_name.replace(/'/g, "\\'")}')" style="margin-top:6px; background:#ef4444; color:#fff; border:none; border-radius:4px; padding:4px 8px; font-size:11px; cursor:pointer;">
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
    const safeLng = clampCoastline(tc.lat, tc.lng);
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

    const marker = L.marker([tc.lat, safeLng], { icon: icon });
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
    const safeLng = clampCoastline(amb.lat, amb.lng);
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

    const marker = L.marker([amb.lat, safeLng], { icon: icon });
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
    const safeLng = clampCoastline(m.lat, m.lng);
    const circle = L.circleMarker([m.lat, safeLng], {
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
    const safeLng = clampCoastline(v.lat, v.lng);
    const circle = L.circleMarker([v.lat, safeLng], {
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

    const dsInfo = v.danger_spot || { name: `${v.village_name} Highway Crossroad`, hazard_type: 'Blind Intersection' };
    circle.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:190px;">
        <strong style="color:${color}; font-size:13px;"><i class="fa-solid fa-tree-city"></i> ${v.village_name}</strong><br>
        <strong>Gram Panchayat:</strong> ${v.gram_panchayat || v.village_name}<br>
        <strong>Mandal:</strong> ${v.mandal}<br>
        <strong>District:</strong> ${v.district}<br>
        <strong>Population:</strong> ${v.population.toLocaleString()}<br>
        <strong>Healthcare:</strong> ${isPhc ? '<span style="color:#10b981; font-weight:600;">PHC / Sub-Center</span>' : 'ASHA Network'}<br>
        <div style="margin-top:6px; padding-top:4px; border-top:1px dashed #cbd5e1;">
          <strong style="color:#dc2626;"><i class="fa-solid fa-triangle-exclamation"></i> Danger Spot:</strong> ${dsInfo.name}<br>
          <strong>Hazard:</strong> ${dsInfo.hazard_type}<br>
        </div>
        <div style="margin-top:6px; padding:4px 6px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:4px;">
          <strong style="color:#15803d;"><i class="fa-solid fa-truck-medical"></i> Ready 108 Station:</strong><br>
          <span style="color:#166534; font-weight:600;">${v.mandal} Mandal HQ Station</span> (< 5 min response)
        </div>
        <div style="margin-top:8px; display:flex; flex-direction:column; gap:5px;">
          <button onclick="handleAccidentReport(${v.lat}, ${safeLng}, '${v.village_name.replace(/'/g, "\\'")} (${v.mandal} Mdl)', '${v.district.replace(/'/g, "\\'")}', '${v.mandal.replace(/'/g, "\\'")}')" style="background:#ef4444; color:#fff; border:none; border-radius:4px; padding:6px 8px; font-size:11px; font-weight:700; cursor:pointer; width:100%;">
            <i class="fa-solid fa-truck-medical"></i> 🚨 Test Emergency Dispatch Here
          </button>
          <button onclick="saveManualAmbulance(${v.lat}, ${safeLng}, '${v.village_name.replace(/'/g, "\\'")} 108 Base', '${v.district.replace(/'/g, "\\'")}', '${v.mandal.replace(/'/g, "\\'")}', 'Advanced Life Support (ALS) - Custom Base')" style="background:#f59e0b; color:#0f172a; border:none; border-radius:4px; padding:5px 8px; font-size:11px; font-weight:700; cursor:pointer; width:100%; display:flex; align-items:center; justify-content:center; gap:5px;">
            <i class="fa-solid fa-star"></i> ⭐ Station Permanent 108 Ambulance Here
          </button>
        </div>
      </div>
    `);
    layers.villages.addLayer(circle);
  });
}

function renderVillageDangerSpots(dangerSpots) {
  layers.villageDanger.clearLayers();

  dangerSpots.forEach(ds => {
    const isCritical = ds.severity === "Critical Risk";
    const zoneColor = isCritical ? "#dc2626" : "#ea580c";
    const safeLat = ds.lat;
    const safeLng = clampCoastline(ds.lat, ds.lng);

    // 1. Visible Danger Zone Hazard Perimeter Circle (650m radius)
    const zoneCircle = L.circle([safeLat, safeLng], {
      radius: 650,
      color: zoneColor,
      weight: 1.8,
      dashArray: "4, 4",
      fillColor: isCritical ? "#ef4444" : "#f97316",
      fillOpacity: 0.22
    });
    layers.villageDanger.addLayer(zoneCircle);

    // 2. Center Danger Warning Icon Marker
    const icon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div class="marker-village-danger ${isCritical ? 'critical' : 'high'}" style="width:22px; height:22px;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:11px;"></i>
        </div>
      `,
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    });

    const marker = L.marker([safeLat, safeLng], { icon: icon });
    marker.bindTooltip(`<b>⚠️ ${ds.village_name} Danger Zone</b><br><small style="color:#fca5a5;">${ds.hazard_type} (${ds.severity})</small>`, {
      direction: "top",
      className: "bold-map-label danger-label",
      offset: [0, -8]
    });

    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:230px;">
        <strong style="color:#dc2626; font-size:13px;"><i class="fa-solid fa-triangle-exclamation"></i> Village Danger Zone</strong><br>
        <span style="font-weight:700; color:#b91c1c; font-size:13px;">${ds.village_name}</span> (${ds.mandal} Mandal, ${ds.district})<br>
        <hr style="margin:5px 0; border:0; border-top:1px solid #fee2e2;">
        <strong>Hazard Zone:</strong> <span style="font-weight:600; color:#ea580c;">${ds.hazard_type}</span><br>
        <strong>Risk Severity:</strong> <span style="background:#fee2e2; color:#991b1b; padding:1px 6px; border-radius:4px; font-weight:700;">${ds.severity}</span><br>
        <strong>Crash Metrics:</strong> ${ds.annual_accidents} accidents/yr | ${ds.fatalities} fatalities<br>
        <strong>Causes:</strong> ${ds.causes || 'Blind curve / high-speed intersection'}<br>
        <div style="margin-top:6px; padding:4px 6px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:4px;">
          <strong style="color:#15803d;"><i class="fa-solid fa-truck-medical"></i> Stationed Ready Ambulance:</strong><br>
          <span style="color:#166534; font-weight:600;">${ds.mandal} 108 Ready Emergency Station</span> (< 5 min response)
        </div>
        <div style="margin-top:8px; display:flex; flex-direction:column; gap:5px;">
          <button onclick="handleAccidentReport(${safeLat}, ${safeLng}, '${ds.village_name.replace(/'/g, "\\'")} Danger Zone (${ds.mandal} Mdl)', '${ds.district.replace(/'/g, "\\'")}', '${ds.mandal.replace(/'/g, "\\'")}')" style="background:#dc2626; color:#fff; border:none; border-radius:4px; padding:6px 10px; font-size:11px; font-weight:700; cursor:pointer; width:100%;">
            <i class="fa-solid fa-truck-medical"></i> 🚨 Test Emergency Dispatch to Danger Zone
          </button>
          <button onclick="saveManualAmbulance(${safeLat}, ${safeLng}, '${ds.village_name.replace(/'/g, "\\'")} 108 Base', '${ds.district.replace(/'/g, "\\'")}', '${ds.mandal.replace(/'/g, "\\'")}', 'Advanced Life Support (ALS) - Custom Base')" style="background:#f59e0b; color:#0f172a; border:none; border-radius:4px; padding:5px 10px; font-size:11px; font-weight:700; cursor:pointer; width:100%; display:flex; align-items:center; justify-content:center; gap:5px;">
            <i class="fa-solid fa-star"></i> ⭐ Station Permanent 108 Ambulance Here
          </button>
        </div>
      </div>
    `);
    layers.villageDanger.addLayer(marker);
  });
}

async function placeAmbulanceNearer(lat, lng, locationLabel = "Danger Spot", district = "General", mandal = "Local") {
  try {
    const res = await fetch("/api/place_ambulance_nearer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: lat,
        lng: lng,
        location_name: locationLabel,
        district: district,
        mandal: mandal
      })
    });

    const data = await res.json();
    if (data.status === "success" && data.station) {
      const stn = data.station;

      // Reload & render manual ambulances so this newly placed station is preserved across reloads
      await loadManualAmbulances();

      // Trigger instant accident dispatch at this spot to show immediate < 2 min response!
      handleAccidentReport(lat, lng, `${locationLabel} (Nearer Ambulance Deployed)`, district, mandal);
    }
  } catch (err) {
    console.error("Error placing ambulance nearer:", err);
  }
}

// ==========================================================================
// Manual Ambulance Placement & Multi-Session Persistence Implementation
// ==========================================================================

// Toggle Manual Placement Mode
function toggleManualPlacementMode(forceState = null) {
  if (forceState !== null) {
    isManualPlacementMode = forceState;
  } else {
    isManualPlacementMode = !isManualPlacementMode;
  }

  const btn = document.getElementById("btn-toggle-manual-placement");
  const banner = document.getElementById("placement-mode-banner");

  if (isManualPlacementMode) {
    document.body.classList.add("manual-placement-mode");
    if (btn) {
      btn.classList.add("active");
      btn.innerHTML = '<i class="fa-solid fa-crosshairs pulse-icon"></i> 📍 Click Map to Station 108 Base';
    }
    if (banner) banner.classList.remove("hidden");
  } else {
    document.body.classList.remove("manual-placement-mode");
    if (btn) {
      btn.classList.remove("active");
      btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> 📍 Place Ambulance Manually';
    }
    if (banner) banner.classList.add("hidden");
  }
}

// Client-side helper to find nearest mandal for detected coordinates
function findNearestMandalClient(lat, lng) {
  if (!allMandals || allMandals.length === 0) return null;
  let bestM = null;
  let minD = Infinity;
  for (const m of allMandals) {
    const d = Math.pow(m.lat - lat, 2) + Math.pow(m.lng - lng, 2);
    if (d < minD) {
      minD = d;
      bestM = m;
    }
  }
  return bestM;
}

// Opens placement confirmation popup on map click during placement mode
function openPlacementConfirmationPopup(rawLat, rawLng) {
  const safeLat = Math.round(rawLat * 100000) / 100000;
  const safeLng = clampCoastline(safeLat, rawLng);
  const nearestM = findNearestMandalClient(safeLat, safeLng);
  const mandalName = nearestM ? nearestM.mandal_name : "Local";
  const districtName = nearestM ? nearestM.district : "Andhra Pradesh";
  const defaultStnName = `${mandalName} Custom 108 Base`;

  const popupContent = document.createElement("div");
  popupContent.className = "manual-placement-popup";
  popupContent.innerHTML = `
    <h4><i class="fa-solid fa-star" style="color:#fbbf24;"></i> Station Permanent 108 Base</h4>
    <div style="font-size:11px; color:#475569; margin-bottom:6px; background:#f8fafc; padding:4px 6px; border-radius:4px; border:1px solid #e2e8f0;">
      <strong>Zone:</strong> ${mandalName} Mandal, ${districtName}<br>
      <span style="font-size:10px; color:#64748b;">Coordinates: ${safeLat.toFixed(4)}, ${safeLng.toFixed(4)}</span>
    </div>
    <div class="form-group-sm">
      <label for="input-custom-stn-name">Station / Unit Name:</label>
      <input type="text" id="input-custom-stn-name" value="${defaultStnName}" style="font-weight:600;" />
    </div>
    <div class="form-group-sm">
      <label for="select-custom-stn-type">Vehicle Class & Equipment:</label>
      <select id="select-custom-stn-type">
        <option value="Advanced Life Support (ALS) - Custom Base" selected>ALS (ICU Ventilator, Defibrillator, Paramedic Crew of 3)</option>
        <option value="Basic Life Support (BLS) - Custom Post">BLS (Oxygen Cylinder, First Aid, Paramedic Crew of 2)</option>
      </select>
    </div>
    <button id="btn-popup-save-manual" class="btn-confirm-save">
      <i class="fa-solid fa-floppy-disk"></i> Confirm & Save Permanently
    </button>
  `;

  const popup = L.popup({ minWidth: 260 })
    .setLatLng([safeLat, safeLng])
    .setContent(popupContent)
    .openOn(map);

  setTimeout(() => {
    const saveBtn = document.getElementById("btn-popup-save-manual");
    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const nameInput = document.getElementById("input-custom-stn-name");
        const typeSelect = document.getElementById("select-custom-stn-type");
        const stnName = (nameInput && nameInput.value.trim()) ? nameInput.value.trim() : defaultStnName;
        const vehicleType = typeSelect ? typeSelect.value : "Advanced Life Support (ALS) - Custom Base";

        map.closePopup();
        toggleManualPlacementMode(false);
        await saveManualAmbulance(safeLat, safeLng, stnName, districtName, mandalName, vehicleType);
      });
    }
  }, 80);
}

// Saves a manual ambulance permanently to disk and updates localStorage
async function saveManualAmbulance(lat, lng, name = "Custom 108 Base", district = "", mandal = "", vehicleType = "Advanced Life Support (ALS) - Custom Base") {
  try {
    const res = await fetch("/api/manual_ambulances", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: lat,
        lng: lng,
        name: name,
        district: district,
        mandal: mandal,
        vehicle_type: vehicleType,
        radius_km: 12.0
      })
    });

    const data = await res.json();
    if (data.status === "success" && data.ambulance) {
      const newAmb = data.ambulance;
      // Filter out duplicate ID and prepend
      customAmbulances = customAmbulances.filter(a => a.station_id !== newAmb.station_id);
      customAmbulances.unshift(newAmb);

      // Save to localStorage backup
      try {
        localStorage.setItem("ap_manual_ambulances", JSON.stringify(customAmbulances));
      } catch (e) {}

      // Render updated custom ambulances
      renderManualAmbulances(customAmbulances);

      // Pan & fly map to newly stationed ambulance
      map.flyTo([newAmb.lat, newAmb.lng], 13, { duration: 1.0 });

      return newAmb;
    }
  } catch (err) {
    console.error("Error saving manual ambulance:", err);
  }
}

// Loads manual ambulances from server with localStorage fallback
async function loadManualAmbulances() {
  try {
    const res = await fetch("/api/manual_ambulances");
    const data = await res.json();
    if (data.status === "success" && Array.isArray(data.ambulances) && data.ambulances.length > 0) {
      customAmbulances = data.ambulances;
      try {
        localStorage.setItem("ap_manual_ambulances", JSON.stringify(customAmbulances));
      } catch (e) {}
    } else {
      // Check localStorage backup
      const cached = localStorage.getItem("ap_manual_ambulances");
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            // Re-sync back to server
            for (const amb of parsed) {
              await fetch("/api/manual_ambulances", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(amb)
              });
            }
            customAmbulances = parsed;
          }
        } catch (e) {}
      }
    }
    renderManualAmbulances(customAmbulances);
  } catch (err) {
    console.error("Error loading manual ambulances:", err);
  }
}

// Deletes a manually placed ambulance from disk and memory
async function deleteManualAmbulance(stationId) {
  if (!confirm("Are you sure you want to permanently delete this custom 108 ambulance station?")) {
    return;
  }
  try {
    const res = await fetch(`/api/manual_ambulances/${encodeURIComponent(stationId)}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (data.status === "success") {
      customAmbulances = customAmbulances.filter(a => a.station_id !== stationId && a.ambulance_id !== stationId);
      try {
        localStorage.setItem("ap_manual_ambulances", JSON.stringify(customAmbulances));
      } catch (e) {}
      renderManualAmbulances(customAmbulances);
    }
  } catch (err) {
    console.error("Error deleting manual ambulance:", err);
  }
}

// Renders all saved manual ambulances onto map and sidebar
function renderManualAmbulances(ambulances) {
  layers.manualAmbulances.clearLayers();

  const totalCount = ambulances ? ambulances.length : 0;

  // Update counters
  const statPillEl = document.getElementById("stat-manual-amb");
  if (statPillEl) statPillEl.textContent = totalCount;

  const badgeEl = document.getElementById("custom-amb-badge");
  if (badgeEl) badgeEl.textContent = `${totalCount} Saved`;

  const legendCountEl = document.getElementById("legend-custom-count");
  if (legendCountEl) legendCountEl.textContent = totalCount;

  // Render Sidebar List
  const listContainer = document.getElementById("custom-ambulances-list");
  if (listContainer) {
    if (totalCount === 0) {
      listContainer.innerHTML = `
        <div class="custom-empty-state" style="text-align:center; padding: 12px 8px; background: rgba(15, 23, 42, 0.4); border-radius:6px; border: 1px dashed var(--border-color);">
          <i class="fa-solid fa-truck-medical" style="font-size: 1.4rem; color: #64748b; margin-bottom: 4px;"></i>
          <p style="font-size: 0.75rem; color: var(--text-muted); margin: 0;">No custom ambulances placed yet.<br>Click <strong>"Place Ambulance Manually"</strong> or click any village to station one.</p>
        </div>
      `;
    } else {
      listContainer.innerHTML = ambulances.map(stn => {
        const safeLng = clampCoastline(stn.lat, stn.lng);
        return `
          <div class="custom-amb-card" id="manual-card-${stn.station_id}">
            <div class="custom-amb-header">
              <span class="custom-amb-name"><i class="fa-solid fa-star" style="color:#fbbf24;"></i> ${stn.name}</span>
              <span style="font-size:0.68rem; background:rgba(251, 191, 36, 0.2); color:#fbbf24; padding:1px 5px; border-radius:3px; font-weight:700;">108 BASE</span>
            </div>
            <div class="custom-amb-meta">
              <span><i class="fa-solid fa-location-dot"></i> ${stn.mandal} Mdl, ${stn.district}</span><br>
              <span style="color:#94a3b8;"><i class="fa-solid fa-crosshairs"></i> ${stn.lat.toFixed(4)}, ${safeLng.toFixed(4)} (12 km Golden Hour)</span>
            </div>
            <div class="custom-amb-actions">
              <button class="btn-amb-fly" onclick="focusAmbulance(${stn.lat}, ${safeLng}, '${stn.name.replace(/'/g, "\\'")}')">
                <i class="fa-solid fa-expand"></i> Fly To
              </button>
              <button class="btn-amb-fly" style="background:rgba(239, 68, 68, 0.15); border-color:#ef4444; color:#f87171;" onclick="handleAccidentReport(${stn.lat}, ${safeLng}, '${stn.name.replace(/'/g, "\\'")}', '${stn.district.replace(/'/g, "\\'")}', '${stn.mandal.replace(/'/g, "\\'")}')">
                <i class="fa-solid fa-truck-medical"></i> Test Dispatch
              </button>
              <button class="btn-amb-delete" title="Permanently delete this station" onclick="deleteManualAmbulance('${stn.station_id}')">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Render on Map
  if (!ambulances || ambulances.length === 0) return;

  ambulances.forEach(stn => {
    const safeLng = clampCoastline(stn.lat, stn.lng);

    // 1. Golden Hour 12 km Coverage Zone Circle (Gold/Emerald)
    const halo = L.circle([stn.lat, safeLng], {
      radius: (stn.coverage_radius_km || 12.0) * 1000,
      color: "#fbbf24",
      weight: 2,
      dashArray: "6, 6",
      fillColor: "#f59e0b",
      fillOpacity: 0.14
    });
    layers.manualAmbulances.addLayer(halo);

    // 2. Custom Station Marker with Star Badge
    const customIcon = L.divIcon({
      className: "custom-div-icon",
      html: `
        <div class="marker-manual-ambulance">
          <i class="fa-solid fa-truck-medical"></i>
          <div class="star-badge">★</div>
        </div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 18]
    });

    const marker = L.marker([stn.lat, safeLng], { icon: customIcon });

    marker.bindTooltip(`<b>⭐ CUSTOM 108: ${stn.name}</b>`, {
      permanent: true,
      direction: "bottom",
      className: "bold-map-label ambulance-label",
      offset: [0, 10]
    });

    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:240px;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
          <strong style="color:#059669; font-size:13px;"><i class="fa-solid fa-star" style="color:#fbbf24;"></i> Permanently Stationed 108 Unit</strong>
        </div>
        <strong style="font-size:13px; color:#0f172a;">${stn.name}</strong><br>
        <strong>Mandal:</strong> ${stn.mandal} | <strong>District:</strong> ${stn.district}<br>
        <strong>Coordinates:</strong> ${stn.lat.toFixed(4)}, ${safeLng.toFixed(4)}<br>
        <strong>Vehicle Class:</strong> <span style="background:#dcfce7; color:#166534; padding:1px 5px; border-radius:3px; font-weight:700;">${stn.allocated_vehicle_type || 'ALS - Custom Base'}</span><br>
        <strong>Paramedic Crew:</strong> ${stn.paramedic_crew || 3} Certified Personnel<br>
        <strong>Life Support Equipment:</strong> ${(stn.equipment || ['ICU Ventilator', 'Defibrillator', 'Oxygen']).join(', ')}<br>
        <strong>Coverage Radius:</strong> ${stn.coverage_radius_km || 12.0} km (Golden Hour Shield)<br>
        <div style="margin-top:6px; padding:4px 6px; background:#fef3c7; border:1px solid #fde68a; border-radius:4px; font-size:11px; color:#92400e;">
          <i class="fa-solid fa-shield-halved"></i> <strong>Permanent Unit:</strong> Persists across website reloads & server restarts.
        </div>
        <div style="margin-top:8px; display:flex; gap:6px;">
          <button onclick="handleAccidentReport(${stn.lat}, ${safeLng}, '${stn.name.replace(/'/g, "\\'")}', '${stn.district.replace(/'/g, "\\'")}', '${stn.mandal.replace(/'/g, "\\'")}')" style="flex:1; background:#ef4444; color:#fff; border:none; border-radius:4px; padding:6px 8px; font-size:11px; font-weight:700; cursor:pointer;">
            <i class="fa-solid fa-truck-medical"></i> Test Dispatch
          </button>
          <button onclick="deleteManualAmbulance('${stn.station_id}')" style="background:#fee2e2; color:#991b1b; border:1px solid #f87171; border-radius:4px; padding:6px 8px; font-size:11px; font-weight:700; cursor:pointer;">
            <i class="fa-solid fa-trash-can"></i> Delete
          </button>
        </div>
      </div>
    `);

    layers.manualAmbulances.addLayer(marker);
  });
}

function focusAmbulance(lat, lng, name) {
  const safeLng = clampCoastline(lat, lng);
  map.flyTo([lat, safeLng], 14, { duration: 1.2 });

  const halo = L.circleMarker([lat, safeLng], {
    radius: 20,
    color: '#fbbf24',
    fillColor: '#fbbf24',
    fillOpacity: 0.45,
    weight: 3
  }).addTo(map);

  halo.bindTooltip(`<b>⭐ ${name}</b>`, {
    permanent: true,
    direction: 'top',
    className: 'bold-map-label'
  }).openTooltip();

  setTimeout(() => {
    map.removeLayer(halo);
  }, 5000);
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
            handleAccidentReport(lat, lng, `${vName} Village (${mandal} Mandal, ${district})`, district, mandal);
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

async function handleAccidentReport(lat, lng, locationLabel = "", district = "General", mandal = "Local") {
  lastIncident = { lat: lat, lng: lng, label: locationLabel || "Emergency Crash Site", district: district, mandal: mandal };
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
        <div style="font-family:'Inter', sans-serif; font-size:12px; color:#0f172a; min-width:225px;">
          <strong style="color:#ef4444; font-size:13px;"><i class="fa-solid fa-car-burst"></i> Emergency Incident Scene</strong><br>
          ${locationLabel ? `<strong>Location:</strong> ${locationLabel}<br>` : ''}
          <strong>Dispatched Unit:</strong> ${amb.name} (${metrics.road_distance_km} km)<br>
          <strong>Ambulance Arrival:</strong> <span style="font-weight:700; color:${metrics.status_color};">${metrics.estimated_eta_minutes} min</span> (${metrics.status_label})<br>
          <div style="margin-top:5px; padding:4px 6px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:4px; font-size:11px; color:#15803d;">
            <i class="fa-solid fa-shield-check"></i> <strong>Stationed Ready 108 Unit:</strong> Assigned from ${amb.mandal || 'Local'} HQ
          </div>
          <hr style="margin:5px 0; border:0; border-top:1px solid #e2e8f0;">
          <strong style="color:#8b5cf6;"><i class="fa-solid fa-hospital"></i> Referral Facility:</strong> ${nearestHosp.name}<br>
          <strong>Transfer Route:</strong> ${nearestHosp.distance_km} km (~${nearestHosp.eta_minutes} min)<br>
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

// -------------------------------------------------------------
// Total District Places Directory & Boundary Renderer
// -------------------------------------------------------------

function renderDistrictBoundary(hullCoords, districtName, mandalsCount, villagesCount) {
  layers.districtBoundary.clearLayers();
  if (!hullCoords || hullCoords.length < 3) return;

  const clampedHull = hullCoords.map(pt => [pt[0], clampCoastline(pt[0], pt[1])]);

  const polygon = L.polygon(clampedHull, {
    color: "#0284c7",
    weight: 2.8,
    dashArray: "6, 6",
    fillColor: "#0284c7",
    fillOpacity: 0.06
  });

  polygon.bindTooltip(
    `<b>🏛️ ${districtName} District</b><br><small style="color:#93c5fd;">Total Coverage: ${mandalsCount} Mandals | ${villagesCount} Villages | 100% Covered</small>`,
    {
      permanent: true,
      direction: "center",
      className: "district-boundary-tooltip"
    }
  );

  layers.districtBoundary.addLayer(polygon);
}

function updateDistrictPlacesExplorer(distDetails, mandals, villages, dangerSpots) {
  const isAll = distDetails.is_statewide || !distDetails.district || distDetails.district === "ALL";

  if (isAll) {
    document.getElementById("explorer-total-badge").textContent = "Statewide View";
    document.getElementById("explorer-district-name").textContent = "All 26 AP Districts";
    document.getElementById("explorer-hq-info").textContent = "Select a specific district to view each and every place";
    document.getElementById("chip-mandals").textContent = "679";
    document.getElementById("chip-villages").textContent = villages.length.toLocaleString();
    document.getElementById("chip-danger").textContent = dangerSpots.length.toLocaleString();
    document.getElementById("chip-amb").textContent = "236";
    document.getElementById("places-display-count").textContent = "Showing 26 AP Districts";

    const mandalSelect = document.getElementById("explorer-mandal-filter");
    if (mandalSelect) {
      mandalSelect.innerHTML = '<option value="ALL">Statewide (Select a district above)</option>';
    }

    const container = document.getElementById("district-places-list");
    if (container) {
      container.innerHTML = `
        <div class="places-empty-state">
          <i class="fa-solid fa-map-location-dot"></i>
          <p>Select a specific district from the <strong>Select District</strong> dropdown above to view and explore each and every mandal, village, and danger zone in that district.</p>
        </div>
      `;
    }
    currentDistrictPlaces = [];
    return;
  }

  const dName = distDetails.district;
  const hq = distDetails.headquarters || dName;
  const highways = (distDetails.highways || []).join(", ");
  const mCount = distDetails.total_mandals || mandals.length;
  const vCount = distDetails.total_villages || villages.length;
  const dsCount = distDetails.total_danger_spots || dangerSpots.length;
  const ambCount = mCount;

  document.getElementById("explorer-total-badge").textContent = `${mCount + vCount} Places`;
  document.getElementById("explorer-district-name").textContent = `${dName} District`;
  document.getElementById("explorer-hq-info").textContent = `HQ: ${hq}${highways ? ' | Corridors: ' + highways : ''}`;
  document.getElementById("chip-mandals").textContent = mCount;
  document.getElementById("chip-villages").textContent = vCount;
  document.getElementById("chip-danger").textContent = dsCount;
  document.getElementById("chip-amb").textContent = ambCount;

  const places = [];

  // 1. Add all Mandals as primary administrative places
  mandals.forEach(m => {
    places.push({
      id: m.mandal_id,
      name: `${m.mandal_name} Mandal HQ`,
      type: "mandal",
      mandal: m.mandal_name,
      district: dName,
      lat: m.lat,
      lng: m.lng,
      population: m.population,
      tier: m.tier || "Mandal Center",
      village_count: m.village_count || 0,
      readyAmb: `${m.mandal_name} 108 Ready Emergency Station`,
      hazard: "Mandal Administrative & CHC Hub",
      severity: "HQ Stationed"
    });
  });

  // 2. Add all Villages
  villages.forEach(v => {
    const ds = v.danger_spot || {};
    places.push({
      id: v.village_id,
      name: v.village_name,
      type: "village",
      mandal: v.mandal,
      district: dName,
      lat: v.lat,
      lng: v.lng,
      population: v.population,
      has_phc: v.has_phc,
      gram_panchayat: v.gram_panchayat,
      readyAmb: `${v.mandal} 108 Ready Emergency Station`,
      hazard: ds.hazard_type || "Blind Highway Intersection",
      severity: ds.severity || "High Risk",
      annual_accidents: ds.annual_accidents || 0
    });
  });

  currentDistrictPlaces = places;

  // Populate Mandal Filter Dropdown
  const mandalSelect = document.getElementById("explorer-mandal-filter");
  if (mandalSelect) {
    const uniqueMandals = [...new Set(places.map(p => p.mandal))].sort();
    let mOptions = `<option value="ALL">All ${mCount} Mandals (${places.length} Places)</option>`;
    uniqueMandals.forEach(mName => {
      const pCount = places.filter(p => p.mandal.toLowerCase() === mName.toLowerCase()).length;
      mOptions += `<option value="${mName}">${mName} (${pCount} places)</option>`;
    });
    mandalSelect.innerHTML = mOptions;
  }

  renderFilteredPlaces();
}

function renderFilteredPlaces() {
  const container = document.getElementById("district-places-list");
  if (!container) return;

  const mandalFilterEl = document.getElementById("explorer-mandal-filter");
  const mandalFilter = mandalFilterEl ? mandalFilterEl.value : "ALL";

  const searchEl = document.getElementById("explorer-place-search");
  const searchQuery = searchEl ? searchEl.value.trim().toLowerCase() : "";

  let filtered = currentDistrictPlaces;
  if (mandalFilter && mandalFilter !== "ALL") {
    filtered = filtered.filter(p => p.mandal.toLowerCase() === mandalFilter.toLowerCase());
  }
  if (searchQuery) {
    filtered = filtered.filter(p =>
      p.name.toLowerCase().includes(searchQuery) ||
      p.mandal.toLowerCase().includes(searchQuery) ||
      (p.hazard && p.hazard.toLowerCase().includes(searchQuery))
    );
  }

  const countEl = document.getElementById("places-display-count");
  if (countEl) {
    countEl.textContent = `Showing ${filtered.length} of ${currentDistrictPlaces.length} places`;
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="places-empty-state">
        <i class="fa-solid fa-magnifying-glass"></i>
        <p>No places matched your filter query.</p>
      </div>
    `;
    return;
  }

  const displayLimit = 150;
  const itemsToRender = filtered.slice(0, displayLimit);

  let html = "";
  itemsToRender.forEach(p => {
    const isMandal = p.type === "mandal";
    const badgeClass = isMandal ? "mandal" : "village";
    const badgeText = isMandal ? "Mandal HQ" : (p.has_phc ? "PHC Village" : "Gramam");
    const safeLng = clampCoastline(p.lat, p.lng);

    html += `
      <div class="place-card-item" id="card-${p.id}">
        <div class="place-card-top">
          <span class="place-card-name">${p.name}</span>
          <span class="place-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="place-card-meta">
          <span><i class="fa-solid fa-building-columns"></i> ${p.mandal} Mdl</span>
          <span><i class="fa-solid fa-users"></i> ${p.population ? p.population.toLocaleString() : '--'}</span>
        </div>
        <div class="place-danger-preview">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>${p.hazard} (${p.severity})</span>
        </div>
        <div class="place-amb-preview">
          <i class="fa-solid fa-truck-medical"></i>
          <span>${p.readyAmb}</span>
        </div>
        <div class="place-card-actions">
          <button class="btn-place-zoom" onclick="focusOnPlace(${p.lat}, ${safeLng}, '${p.name.replace(/'/g, "\\'")}', '${p.type}')">
            <i class="fa-solid fa-crosshairs"></i> View
          </button>
          <button class="btn-place-dispatch" onclick="handleAccidentReport(${p.lat}, ${safeLng}, '${p.name.replace(/'/g, "\\'")}', '${p.district.replace(/'/g, "\\'")}', '${p.mandal.replace(/'/g, "\\'")}')">
            <i class="fa-solid fa-truck-medical"></i> Dispatch
          </button>
          <button class="btn-place-zoom" style="color:#fbbf24; border-color:rgba(245, 158, 11, 0.4); background:rgba(245, 158, 11, 0.1);" title="Permanently station a 108 Ambulance here" onclick="saveManualAmbulance(${p.lat}, ${safeLng}, '${p.name.replace(/'/g, "\\'")} 108 Base', '${p.district.replace(/'/g, "\\'")}', '${p.mandal.replace(/'/g, "\\'")}', 'Advanced Life Support (ALS) - Custom Base')">
            <i class="fa-solid fa-star"></i> Station
          </button>
        </div>
      </div>
    `;
  });

  if (filtered.length > displayLimit) {
    html += `
      <div style="text-align:center; padding:8px; font-size:0.75rem; color:var(--text-muted);">
        ... and ${filtered.length - displayLimit} more places. Type in search to narrow results.
      </div>
    `;
  }

  container.innerHTML = html;
}

function focusOnPlace(lat, lng, name, type) {
  const safeLng = clampCoastline(lat, lng);
  map.flyTo([lat, safeLng], 14, { duration: 1.2 });

  const highlightCircle = L.circleMarker([lat, safeLng], {
    radius: 18,
    color: '#38bdf8',
    fillColor: '#38bdf8',
    fillOpacity: 0.4,
    weight: 3
  }).addTo(map);

  highlightCircle.bindTooltip(`<b>📍 ${name}</b>`, {
    permanent: true,
    direction: 'top',
    className: 'bold-map-label'
  }).openTooltip();

  setTimeout(() => {
    map.removeLayer(highlightCircle);
  }, 5000);
}

function fitDistrictBounds() {
  if (currentDistrictBounds) {
    map.fitBounds(currentDistrictBounds, { padding: [40, 40] });
  }
}
