// Global state
let moistureChart, tempChart;
let esp32OfflineState = false; // Tracking variable for ESP32 connectivity
let currentTab = 'ai';

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Request permission for Desktop notifications
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }

    // Determine which page we are on and initialize accordingly
    const path = window.location.pathname;
    
    // Highlight active navigation items dynamically
    if (path === '/' || path === '/dashboard') {
        document.getElementById('nav-dashboard')?.classList.add('active');
        initDashboard();
        // Poll every 1 second for dashboard
        setInterval(fetchLiveData, 1000);
        setInterval(fetchWaterStats, 10000);
        setInterval(fetchWeatherData, 15000);
    } else if (path === '/analytics') {
        document.getElementById('nav-reports')?.classList.add('active');
        initAnalytics();
    } else if (path === '/alerts') {
        document.getElementById('nav-schedule')?.classList.add('active');
        fetchLiveData(); // Initial fetch to populate UI
        setInterval(fetchLiveData, 1000);
    } else if (path === '/sensor_status') {
        document.getElementById('nav-fields')?.classList.add('active');
        document.getElementById('nav-devices')?.classList.add('active');
        fetchLiveData();
        setInterval(fetchLiveData, 1000);
    } else if (path === '/settings') {
        document.getElementById('nav-settings')?.classList.add('active');
        document.getElementById('nav-weather')?.classList.add('active');
    }
});

function initDashboard() {
    // Initialize empty charts
    const tempCtx = document.getElementById('tempChart');

    if (tempCtx) {
        // Render a gorgeous temperature curve chart
        tempChart = createChart(tempCtx, 'Temperature (°C)', '#00ff9d');
    }

    fetchLiveData();
    fetchWaterStats();
    fetchWeatherData();
}

async function fetchWeatherData() {
    try {
        const response = await fetch('/api/weather');
        if (response.ok) {
            const data = await response.json();
            
            const summaryEl = document.getElementById('weather-summary');
            const rainProbEl = document.getElementById('weather-rain-prob');
            const tempEl = document.getElementById('weather-temp');
            const toggleEl = document.getElementById('dashboard-weather-toggle');
            const statusLabelEl = document.getElementById('weather-status-label');
            const overrideBadgeEl = document.getElementById('weather-override-badge');
            const iconEl = document.getElementById('weather-icon');
            const locationNameEl = document.getElementById('weather-location-name');
            const timelineLocationEl = document.getElementById('timeline-location');
            
            if (esp32OfflineState) {
                // If ESP32 is offline, force weather cards to show dashed placeholders, but keep the location name
                if (summaryEl) summaryEl.textContent = "---------";
                if (rainProbEl) rainProbEl.textContent = "---------";
                if (tempEl) tempEl.textContent = "---------";
                if (locationNameEl) {
                    locationNameEl.textContent = (data.location_name || `${data.latitude.toFixed(4)}°, ${data.longitude.toFixed(4)}`) + " (Offline)";
                }
                if (iconEl) iconEl.className = "fa-solid fa-power-off text-red-500 animate-pulse";
                if (overrideBadgeEl) overrideBadgeEl.classList.add('hidden');
                return;
            }
            
            if (summaryEl) summaryEl.textContent = data.summary;
            if (rainProbEl) rainProbEl.textContent = `${data.precipitation_probability}%`;
            if (tempEl) tempEl.textContent = `${data.temperature.toFixed(1)}°C`;
            
            if (locationNameEl) {
                locationNameEl.textContent = data.location_name || `${data.latitude.toFixed(4)}°, ${data.longitude.toFixed(4)}`;
            }
            if (timelineLocationEl) {
                timelineLocationEl.textContent = data.location_name || 'Station';
            }
            
            if (toggleEl) {
                toggleEl.checked = data.weather_prediction_enabled;
            }
            
            if (statusLabelEl) {
                statusLabelEl.textContent = data.weather_prediction_enabled ? 'Enabled' : 'Bypassed';
                statusLabelEl.className = data.weather_prediction_enabled ? 'text-[11px] text-[#00ff9d] font-bold' : 'text-[11px] text-gray-500 font-bold';
            }
            
            if (overrideBadgeEl) {
                if (data.rain_override) {
                    overrideBadgeEl.classList.remove('hidden');
                } else {
                    overrideBadgeEl.classList.add('hidden');
                }
            }
            
            if (iconEl && data.icon) {
                iconEl.className = `fa-solid ${data.icon} text-lg text-[#00d2ff]`;
            }
        }
    } catch (error) {
        console.error('Error fetching weather data:', error);
    }
}

async function toggleDashboardWeather(checkbox) {
    try {
        const response = await fetch('/api/settings/weather', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: checkbox.checked })
        });
        
        if (response.ok) {
            fetchWeatherData();
        } else {
            checkbox.checked = !checkbox.checked;
            alert("Failed to update weather setting.");
        }
    } catch (error) {
        checkbox.checked = !checkbox.checked;
        console.error("Error updating setting:", error);
        alert("Error connecting to server.");
    }
}

async function fetchWaterStats() {
    try {
        const response = await fetch('/api/water_stats');
        if (response.ok) {
            const data = await response.json();
            const timeDayEl = document.getElementById('water-time-day');
            const waterDayEl = document.getElementById('water-day');
            const waterWeekEl = document.getElementById('water-week');
            const waterMonthEl = document.getElementById('water-month');

            if (timeDayEl) timeDayEl.textContent = data.day_minutes;
            if (waterDayEl) waterDayEl.textContent = data.day_liters;
            if (waterWeekEl) waterWeekEl.textContent = data.week_liters;
            if (waterMonthEl) waterMonthEl.textContent = data.month_liters;
        }
    } catch (error) {
        console.error('Error fetching water stats:', error);
    }
}

function createChart(ctx, label, color) {
    const canvasContext = ctx.getContext('2d');
    
    // Create soft gradient fill matching mockup glow
    const gradient = canvasContext.createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, 'rgba(0, 255, 157, 0.18)');
    gradient.addColorStop(0.5, 'rgba(0, 255, 157, 0.04)');
    gradient.addColorStop(1, 'rgba(0, 255, 157, 0.0)');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: '#00ff9d',
                borderWidth: 3,
                backgroundColor: gradient,
                fill: true,
                tension: 0.45,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#00ff9d',
                pointHoverBorderColor: '#ffffff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleFont: { family: 'Outfit', size: 10 },
                    bodyFont: { family: 'Outfit', size: 12, weight: 'bold' },
                    borderColor: 'rgba(0, 255, 157, 0.3)',
                    borderWidth: 1,
                    displayColors: false,
                    padding: 8,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            return `Today: ${context.parsed.y.toFixed(1)}°C`;
                        }
                    }
                }
            },
            scales: {
                x: { 
                    display: true,
                    grid: { display: false },
                    ticks: { color: '#5e6b7e', font: { family: 'Outfit', size: 10 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)', drawBorder: false },
                    ticks: { color: '#5e6b7e', font: { family: 'Outfit', size: 10 } }
                }
            }
        }
    });
}

async function fetchLiveData() {
    try {
        const response = await fetch('/api/live_data');
        const data = await response.json();
        updateUI(data);
        
        // Auto-detect and align coordinates with browser location if enabled
        if (data.auto_location_enabled && data.latitude && data.longitude) {
            checkAndAutoGeolocate(data.latitude, data.longitude);
        }
        
        if (currentTab === 'pump') {
            fetchPumpHistory();
        }
    } catch (error) {
        console.error('Error fetching live data:', error);
    }
}

// Circular Gauge Stroke-Dashoffset Helper
function setCircularGauge(gaugeId, value) {
    const gaugeFill = document.getElementById(gaugeId);
    if (!gaugeFill) return;
    const radius = 50;
    const circumference = 2 * Math.PI * radius; // 314.15
    const percentage = Math.min(Math.max(value, 0), 100) / 100;
    const offset = circumference - (percentage * circumference);
    gaugeFill.style.strokeDashoffset = offset;
}

function updateUI(data) {
    // Update Sensor Values
    const moistureEl = document.getElementById('live-moisture');
    const tempEl = document.getElementById('live-temp');
    const moistureGauge1 = document.getElementById('moisture-gauge-1');
    
    let liveMoistureValue = 68.0;
    let liveTempValue = 24.0;
    
    if (data.sensor) {
        liveMoistureValue = data.sensor.moisture;
        liveTempValue = data.sensor.temperature;
    }

    const isOffline = (data.sensor_status === 'Offline / Failing');

    // Global Topbar Soil Moisture
    const globalMoistureEl = document.getElementById('global-moisture');
    if (globalMoistureEl) {
        globalMoistureEl.textContent = isOffline ? '--%' : `${liveMoistureValue.toFixed(0)}%`;
    }

    // Global Topbar Surrounding Temp
    const globalTempEl = document.getElementById('global-temp');
    if (globalTempEl) {
        globalTempEl.textContent = isOffline ? '--.-°C' : `${liveTempValue.toFixed(1)}°C`;
    }

    // Dashboard Live Temp Widget
    const dashboardLiveTemp = document.getElementById('dashboard-live-temp');
    if (dashboardLiveTemp) {
        dashboardLiveTemp.textContent = isOffline ? '--.-°C' : `${liveTempValue.toFixed(1)}°C`;
    }


    const tempStatusLabel = document.getElementById('temp-status-label');
    if (tempStatusLabel) {
        if (isOffline) {
            tempStatusLabel.textContent = '● Offline';
            tempStatusLabel.className = 'text-xs font-bold text-red-500 uppercase tracking-wider';
        } else {
            // Check high temp warning
            const hasHighTemp = data.alerts && data.alerts.some(a => a.alert_type === 'High Temp');
            if (hasHighTemp) {
                tempStatusLabel.textContent = '● High Heat';
                tempStatusLabel.className = 'text-xs font-bold text-orange-500 uppercase tracking-wider';
            } else {
                tempStatusLabel.textContent = '● Normal';
                tempStatusLabel.className = 'text-xs font-bold text-[#00ff9d] uppercase tracking-wider';
            }
        }
    }

    // Sensor Status Page values
    const statusMoistureVal = document.getElementById('status-moisture-val');
    const statusTempVal = document.getElementById('status-temp-val');
    if (statusMoistureVal) {
        statusMoistureVal.textContent = isOffline ? 'Offline' : `Active (${liveMoistureValue.toFixed(1)}%)`;
        statusMoistureVal.className = isOffline ? 'font-medium text-red-500' : 'font-medium text-[#00ff9d]';
    }
    if (statusTempVal) {
        statusTempVal.textContent = isOffline ? 'Offline' : `Active (${liveTempValue.toFixed(1)}°C)`;
        statusTempVal.className = isOffline ? 'font-medium text-red-500' : 'font-medium text-[#00ff9d]';
    }

    // Node Status Badge (Online vs Offline)
    const nodeStatusEl = document.getElementById('node-status');
    if (nodeStatusEl) {
        if (isOffline) {
            nodeStatusEl.textContent = 'OFF';
            nodeStatusEl.className = 'bg-red-500/20 text-red-500 text-xs px-2 py-1 rounded border border-red-500/30';
        } else {
            nodeStatusEl.textContent = 'ON';
            nodeStatusEl.className = 'bg-[#00d27f]/20 text-[#00d27f] text-xs px-2 py-1 rounded border border-[#00d27f]/30';
        }
    }

    // Last Seen Timer
    const lastSeenEl = document.getElementById('status-last-seen');
    if (lastSeenEl) {
        if (data.seconds_since_last_seen === null || data.seconds_since_last_seen === undefined) {
            lastSeenEl.textContent = 'Never';
            lastSeenEl.className = 'font-medium text-gray-500';
        } else {
            const secs = data.seconds_since_last_seen;
            if (secs <= 2) {
                lastSeenEl.textContent = 'Just now';
                lastSeenEl.className = 'font-medium text-[#00ff9d]';
            } else if (secs < 60) {
                lastSeenEl.textContent = `${secs}s ago`;
                lastSeenEl.className = 'font-medium text-white';
            } else if (secs < 3600) {
                const mins = Math.floor(secs / 60);
                lastSeenEl.textContent = `${mins}m ago`;
                lastSeenEl.className = 'font-medium text-gray-300';
            } else {
                const hrs = Math.floor(secs / 3600);
                lastSeenEl.textContent = `${hrs}h ago`;
                lastSeenEl.className = 'font-medium text-gray-400';
            }
        }
    }

    // Connection Mode
    const connModeEl = document.getElementById('status-connection-mode');
    if (connModeEl) {
        if (isOffline) {
            connModeEl.textContent = 'Disconnected';
            connModeEl.className = 'font-medium text-red-500';
        } else {
            connModeEl.textContent = 'Wi-Fi (Wireless)';
            connModeEl.className = 'font-medium text-[#00d2ff]';
        }
    }

    // USB Serial Link
    const usbLinkEl = document.getElementById('status-usb-link');
    if (usbLinkEl) {
        if (data.usb_connected) {
            usbLinkEl.textContent = 'Connected (Active)';
            usbLinkEl.className = 'font-medium text-[#00ff9d]';
        } else {
            usbLinkEl.textContent = 'Disconnected';
            usbLinkEl.className = 'font-medium text-gray-500';
        }
    }

    // GPS Signal
    const gpsSignalEl = document.getElementById('status-gps-signal');
    if (gpsSignalEl) {
        if (isOffline) {
            gpsSignalEl.textContent = 'No Signal';
            gpsSignalEl.className = 'font-medium text-gray-500';
        } else if (data.gps_valid) {
            const src = data.location_source ? data.location_source.toUpperCase() : 'GPS';
            gpsSignalEl.textContent = `Active (${src})`;
            gpsSignalEl.className = 'font-medium text-[#00ff9d]';
        } else {
            gpsSignalEl.textContent = 'No Lock / Searching';
            gpsSignalEl.className = 'font-medium text-yellow-500';
        }
    }

    // Device Location Address
    const devLocationEl = document.getElementById('status-device-location');
    if (devLocationEl) {
        if (data.location_name) {
            const coordsStr = ` (${data.latitude.toFixed(4)}°, ${data.longitude.toFixed(4)}°)`;
            devLocationEl.textContent = data.location_name + coordsStr;
            devLocationEl.title = data.location_name + coordsStr;
        } else if (data.latitude && data.longitude) {
            devLocationEl.textContent = `${data.latitude.toFixed(6)}°, ${data.longitude.toFixed(6)}°`;
        } else {
            devLocationEl.textContent = 'Unknown / No Lock';
        }
    }

    // Live Pump Status Badge & Trigger Button Update
    const livePumpStatusBadge = document.getElementById('live-pump-status-badge');
    const pumpIsActive = data.sensor && data.sensor.pump_status;

    if (livePumpStatusBadge) {
        if (isOffline) {
            livePumpStatusBadge.textContent = 'OFFLINE';
            livePumpStatusBadge.className = 'text-[10px] font-extrabold text-red-500 uppercase';
        } else if (pumpIsActive) {
            livePumpStatusBadge.textContent = 'ON / RUNNING';
            livePumpStatusBadge.className = 'text-[10px] font-extrabold text-[#00ff9d] uppercase animate-pulse';
        } else {
            livePumpStatusBadge.textContent = 'OFF';
            livePumpStatusBadge.className = 'text-[10px] font-extrabold text-gray-500 uppercase';
        }
    }

    const triggerBtn = document.querySelector('button[onclick="triggerManualPump()"]');
    const stopBtn = document.querySelector('button[onclick="stopManualPump()"]');

    if (triggerBtn) {
        if (isOffline) {
            triggerBtn.disabled = true;
            triggerBtn.innerHTML = `<i class="fa-solid fa-ban text-[10px]"></i> Turn ON`;
            triggerBtn.className = 'flex-1 bg-gray-800 text-gray-500 font-extrabold py-3.5 px-4 rounded-xl cursor-not-allowed text-xs uppercase tracking-widest flex items-center justify-center gap-2';
        } else if (pumpIsActive) {
            triggerBtn.disabled = false;
            triggerBtn.innerHTML = `<i class="fa-solid fa-spinner animate-spin text-[10px]"></i> Running...`;
            triggerBtn.className = 'flex-1 bg-[#00d2ff] hover:bg-[#00b0d9] text-[#080d16] font-extrabold py-3.5 px-4 rounded-xl shadow-[0_0_20px_rgba(0,210,255,0.2)] transition-all duration-300 text-xs uppercase tracking-widest flex items-center justify-center gap-2';
        } else {
            triggerBtn.disabled = false;
            triggerBtn.innerHTML = `<i class="fa-solid fa-play text-[10px]"></i> Turn ON`;
            triggerBtn.className = 'flex-1 bg-[#00ff9d] hover:bg-[#00d27f] text-[#080d16] font-extrabold py-3.5 px-4 rounded-xl shadow-[0_0_20px_rgba(0,255,157,0.2)] hover:shadow-[0_0_30px_rgba(0,255,157,0.4)] transition-all duration-300 transform hover:-translate-y-0.5 text-xs uppercase tracking-widest flex items-center justify-center gap-2';
        }
    }

    if (stopBtn) {
        if (isOffline) {
            stopBtn.disabled = true;
            stopBtn.innerHTML = `<i class="fa-solid fa-ban text-[10px]"></i> Turn OFF`;
            stopBtn.className = 'flex-1 bg-gray-800 text-gray-500 font-extrabold py-3.5 px-4 rounded-xl cursor-not-allowed text-xs uppercase tracking-widest flex items-center justify-center gap-2';
        } else {
            stopBtn.disabled = false;
            stopBtn.innerHTML = `<i class="fa-solid fa-stop text-[10px]"></i> Turn OFF`;
            stopBtn.className = 'flex-1 bg-[#ff4d4d] hover:bg-[#e03d3d] text-white font-extrabold py-3.5 px-4 rounded-xl shadow-[0_0_20px_rgba(255,77,77,0.2)] hover:shadow-[0_0_30px_rgba(255,77,77,0.4)] transition-all duration-300 transform hover:-translate-y-0.5 text-xs uppercase tracking-widest flex items-center justify-center gap-2';
        }
    }

    const card1 = document.getElementById('soil-card-1');
    const card2 = document.getElementById('soil-card-2');
    const card3 = document.getElementById('soil-card-3');

    // 1. Dynamic Card States & Visibility Management
    if (isOffline) {
        // If offline, all three zones show unified offline overlays
        card1?.classList.add('state-offline');
        card2?.classList.add('state-offline');
        card3?.classList.add('state-offline');
        
        card1?.classList.remove('state-unconfigured');
        card2?.classList.remove('state-unconfigured');
        card3?.classList.remove('state-unconfigured');
    } else {
        // If online: zone 1 shows active telemetries
        card1?.classList.remove('state-offline', 'state-unconfigured');
        
        // Zone 2 and 3 show "Not Configured" only if no node data has been received yet
        const hasN2 = data.nodes && data.nodes['AGR-Node-002'] && data.nodes['AGR-Node-002'].sensor;
        if (!hasN2) {
            card2?.classList.add('state-unconfigured');
            card2?.classList.remove('state-offline');
        } else {
            card2?.classList.remove('state-unconfigured');
        }
        
        const hasN3 = data.nodes && data.nodes['AGR-Node-003'] && data.nodes['AGR-Node-003'].sensor;
        if (!hasN3) {
            card3?.classList.add('state-unconfigured');
            card3?.classList.remove('state-offline');
        } else {
            card3?.classList.remove('state-unconfigured');
        }
    }
    
    // 2. Update Crops 1 Gauge (Dynamic live values)
    if (moistureEl) {
        moistureEl.textContent = isOffline ? '--%' : `${liveMoistureValue.toFixed(0)}%`;
        setCircularGauge('moisture-gauge-1', isOffline ? 0 : liveMoistureValue);
        
        const moistureRawEl = document.getElementById('live-moisture-raw');
        if (moistureRawEl) {
            moistureRawEl.textContent = isOffline ? 'Raw: --' : `Raw: ${data.raw_moisture || '--'}`;
        }
        
        const status1 = document.getElementById('moisture-status-1');
        if (status1) {
            if (isOffline) {
                status1.textContent = 'Disconnected';
                status1.className = 'text-[10px] uppercase font-bold text-red-500 tracking-wider mt-0.5';
            } else if (liveMoistureValue >= 60) {
                status1.textContent = 'Optimized';
                status1.className = 'text-[10px] uppercase font-bold text-[#00d2ff] tracking-wider mt-0.5';
                moistureGauge1?.setAttribute('class', 'gauge-fill text-[#00d2ff]');
            } else if (liveMoistureValue >= 35) {
                status1.textContent = 'Optimal';
                status1.className = 'text-[10px] uppercase font-bold text-[#00ff9d] tracking-wider mt-0.5';
                moistureGauge1?.setAttribute('class', 'gauge-fill text-[#00ff9d]');
            } else {
                status1.textContent = 'Needs Attention';
                status1.className = 'text-[10px] uppercase font-bold text-[#ff9f43] tracking-wider mt-0.5';
                moistureGauge1?.setAttribute('class', 'gauge-fill text-[#ff9f43]');
            }
        }
        
        // Only push real live telemetries to ambient temperature curve chart when online
        if (!isOffline) {
            updateChartData(tempChart, new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}), liveTempValue);
        }
    }
    
    if (tempEl) {
        tempEl.textContent = isOffline ? '--.-°C' : `${liveTempValue.toFixed(1)}°C`;
    }

    // Fallback Mode & ESP32 Offline Banner UI
    const offlineBanner = document.getElementById('esp32-offline-banner');
    const fallbackBanner = document.getElementById('fallback-banner');
    const statusInd = document.getElementById('status-indicator');
    const statusTxt = document.getElementById('status-text');
    const systemHealthyText = document.getElementById('system-healthy-text');
    
    if (data.sensor_status === 'Offline / Failing') {
        if (!esp32OfflineState) {
            esp32OfflineState = true;
            fetchWeatherData();
        }
        if (offlineBanner) offlineBanner.classList.remove('hidden');
        if (fallbackBanner) fallbackBanner.classList.add('hidden');
        if (statusInd) statusInd.className = 'w-2.5 h-2.5 rounded-full bg-red-500';
        if (statusTxt) statusTxt.textContent = 'SYSTEM OFFLINE';
        if (systemHealthyText) {
            systemHealthyText.textContent = '● Offline';
            systemHealthyText.className = 'text-xs font-bold text-red-500 uppercase tracking-wider';
        }
        const systemStatusTitle = document.getElementById('system-status-title');
        if (systemStatusTitle) {
            systemStatusTitle.textContent = 'ESP32: OFF';
        }
        
        // Trigger native Browser Desktop Notification
        if (!window.esp32WasOffline) {
            window.esp32WasOffline = true;
            if ("Notification" in window && Notification.permission === "granted") {
                new Notification("ESP32 Offline Alert ⚠️", {
                    body: "ESP32 is off, please switch it on!",
                    icon: "/static/images/warning-icon.png"
                });
            }
        }
    } else {
        if (esp32OfflineState) {
            esp32OfflineState = false;
            fetchWeatherData();
        }
        window.esp32WasOffline = false;
        if (offlineBanner) offlineBanner.classList.add('hidden');
        
        const systemStatusTitle = document.getElementById('system-status-title');
        if (systemStatusTitle) {
            systemStatusTitle.textContent = 'ESP32: ON';
        }
        
        if (fallbackBanner) {
            if (data.prediction && data.prediction.is_fallback_mode) {
                fallbackBanner.classList.remove('hidden');
                if (statusInd) statusInd.className = 'w-2.5 h-2.5 rounded-full bg-yellow-500 heart-pulse';
                if (statusTxt) statusTxt.textContent = 'AI Fallback Mode';
                if (systemHealthyText) {
                    systemHealthyText.textContent = '● Warning';
                    systemHealthyText.className = 'text-xs font-bold text-yellow-500 uppercase tracking-wider';
                }
            } else {
                fallbackBanner.classList.add('hidden');
                if (statusInd) statusInd.className = 'w-2.5 h-2.5 rounded-full bg-[#00ff9d] heart-pulse';
                if (statusTxt) statusTxt.textContent = 'System Healthy';
                if (systemHealthyText) {
                    systemHealthyText.textContent = '● Healthy';
                    systemHealthyText.className = 'text-xs font-bold text-[#00ff9d] uppercase tracking-wider';
                }
            }
        }
    }

    // Update AI Predictions
    const waterNeededEl = document.getElementById('ai-water-needed');
    const recommendEl = document.getElementById('ai-recommendation');
    
    if (data.prediction) {
        if (waterNeededEl) {
            waterNeededEl.textContent = data.prediction.water_needed ? 'Yes - Irrigation Required' : 'No - Soil is Optimal';
            waterNeededEl.className = data.prediction.water_needed ? 'text-blue-400 font-bold' : 'text-green-400 font-bold';
        }
        if (recommendEl) recommendEl.textContent = data.prediction.recommendation;
    }

    // 4. Update AI Prediction Logs List dynamically based on live predictions
    const logsContainer = document.getElementById('ai-logs-list');
    if (logsContainer) {
        logsContainer.innerHTML = '';
        
        // Log Item 1: Current status dynamically calculated
        let item1Class = 'success';
        let item1Text = 'Optimal Conditions';
        let item1Sub = `<i class="fa-solid fa-circle-check text-[10px]"></i> Soil is healthy and well-watered`;
        
        if (data.prediction) {
            if (data.prediction.water_needed) {
                item1Class = 'critical';
                item1Text = 'Irrigation Needed';
                item1Sub = `<i class="fa-solid fa-droplet text-[10px]"></i> ${data.prediction.soil_condition || 'Dry Conditions'}`;
            } else {
                item1Class = 'success';
                item1Text = 'Success';
                item1Sub = `<i class="fa-solid fa-circle-check text-[10px]"></i> ${data.prediction.recommendation || 'Soil conditions optimal'}`;
            }
        }
        
        // Check for weather override alerts
        let item2Html = `
            <div class="log-item override">
                <div class="flex justify-between items-baseline">
                    <span class="text-xs text-gray-400">Scheduled: 6:00 AM</span>
                </div>
                <p class="text-sm font-bold text-white mt-0.5">Weather Shield</p>
                <p class="text-xs text-gray-500 flex items-center gap-1.5 mt-0.5">
                    <i class="fa-solid fa-cloud-sun text-[10px]"></i> Auto-protection Active
                </p>
            </div>
        `;
        
        if (data.alerts && data.alerts.some(a => a.alert_type === 'Weather Override' || a.message.includes('Rain expected'))) {
            item2Html = `
                <div class="log-item override">
                    <div class="flex justify-between items-baseline">
                        <span class="text-xs text-gray-400">Now - Weather Block</span>
                    </div>
                    <p class="text-sm font-bold text-[#ff9f43] mt-0.5">Weather Override</p>
                    <p class="text-xs text-[#ff9f43]/85 flex items-center gap-1.5 mt-0.5">
                        <i class="fa-solid fa-cloud-showers-heavy text-[10px]"></i> Rain Forecasted - No Irrigation
                    </p>
                </div>
            `;
        }

        logsContainer.innerHTML = `
            <div class="log-item ${item1Class}">
                <div class="flex justify-between items-baseline">
                    <span class="text-xs text-gray-400">Now - crops 1</span>
                </div>
                <p class="text-sm font-bold mt-0.5 ${item1Class === 'critical' ? 'text-[#ff4d4d]' : 'text-[#00ff9d]'}">${item1Text}</p>
                <p class="text-xs text-gray-500 flex items-center gap-1.5 mt-0.5">
                    ${item1Sub}
                </p>
            </div>
            ${item2Html}
            <div class="log-item success">
                <div class="flex justify-between items-baseline">
                    <span class="text-xs text-gray-400">May 26, 6:01 AM - Field A</span>
                </div>
                <p class="text-sm font-bold text-[#00ff9d] mt-0.5">Success</p>
                <p class="text-xs text-gray-500 flex items-center gap-1.5 mt-0.5">
                    <i class="fa-solid fa-circle-check text-[10px]"></i> Irrigation Completed, 68%
                </p>
            </div>
        `;
    }

    // Check for Fire Alarm & High Temp Banners
    if (data.alerts) {
        const hasFire = data.alerts.some(a => a.alert_type === 'Fire Warning');
        const fireAlarmEl = document.getElementById('fire-alarm');
        if (fireAlarmEl && hasFire && !window.fireAlarmDismissed && fireAlarmEl.classList.contains('hidden')) {
            fireAlarmEl.classList.remove('hidden');
        }

        const hasHighTemp = data.alerts.some(a => a.alert_type === 'High Temp');
        const highTempBanner = document.getElementById('high-temp-banner');
        if (highTempBanner) {
            if (hasHighTemp && !isOffline) {
                highTempBanner.classList.remove('hidden');
            } else {
                highTempBanner.classList.add('hidden');
            }
        }
    }

    // Populate System Alerts Page container
    const alertsContainer = document.getElementById('alerts-container');
    if (alertsContainer) {
        if (!data.alerts || data.alerts.length === 0) {
            alertsContainer.innerHTML = '<p class="text-center text-gray-500 py-8">No active alerts.</p>';
        } else {
            alertsContainer.innerHTML = '';
            data.alerts.forEach(alert => {
                const alertDiv = document.createElement('div');
                alertDiv.className = `p-4 rounded-xl border flex justify-between items-center bg-yellow-950/20 border-yellow-500/20 text-yellow-200`;
                let iconClass = 'fa-triangle-exclamation text-yellow-400 bg-yellow-500/20';
                let typeClass = 'bg-yellow-500 text-[#080d16]';
                
                if (alert.alert_type === 'Fire Warning') {
                    alertDiv.className = `p-4 rounded-xl border flex justify-between items-center bg-red-950/40 border-red-500/50 text-red-100 shadow-[0_0_15px_rgba(255,77,77,0.1)]`;
                    iconClass = 'fa-fire text-red-400 bg-red-500/20 animate-pulse';
                    typeClass = 'bg-red-500 text-white';
                } else if (alert.alert_type === 'High Temp') {
                    alertDiv.className = `p-4 rounded-xl border flex justify-between items-center bg-orange-950/20 border-orange-500/20 text-orange-200`;
                    iconClass = 'fa-temperature-high text-orange-400 bg-orange-500/20';
                    typeClass = 'bg-orange-500 text-[#080d16]';
                }
                
                alertDiv.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center ${iconClass.split(' ').slice(2).join(' ')}">
                            <i class="fa-solid ${iconClass.split(' ')[0]}"></i>
                        </div>
                        <div>
                            <p class="font-bold text-sm text-white">${alert.message}</p>
                            <p class="text-[10px] text-gray-500">${new Date(alert.timestamp + ' UTC').toLocaleString()}</p>
                        </div>
                    </div>
                    <span class="text-[10px] uppercase font-extrabold px-2 py-0.5 rounded ${typeClass}">${alert.alert_type}</span>
                `;
                alertsContainer.appendChild(alertDiv);
            });
        }
    }

    // Update multiple nodes dynamically (Node 2 & Node 3)
    if (data.nodes) {
        // --- NODE 2: Orchard Node (AGR-Node-002) ---
        const n2 = data.nodes['AGR-Node-002'];
        const card2 = document.getElementById('soil-card-2');
        const nodeCard2 = document.getElementById('node-card-2');
        
        if (n2 && n2.sensor) {
            // Remove unconfigured opacity
            nodeCard2?.classList.remove('opacity-50');
            nodeCard2?.classList.add('border-[#00d27f]/30');
            nodeCard2?.classList.remove('border-white/5');
            
            const n2Offline = n2.sensor_status === 'Offline';
            if (n2Offline) {
                card2?.classList.add('state-offline');
                
                // Update Node 2 status card elements
                const statusEl2 = document.getElementById('node-status-2');
                if (statusEl2) {
                    statusEl2.textContent = 'OFF';
                    statusEl2.className = 'bg-red-500/20 text-red-500 text-xs px-2 py-1 rounded border border-red-500/30';
                }
                const iconContainer2 = document.getElementById('node-icon-container-2');
                if (iconContainer2) {
                    iconContainer2.className = 'w-10 h-10 rounded bg-red-500/20 flex items-center justify-center text-red-500';
                }
            } else {
                card2?.classList.remove('state-offline');
                
                // Update Node 2 status card elements
                const statusEl2 = document.getElementById('node-status-2');
                if (statusEl2) {
                    statusEl2.textContent = 'ON';
                    statusEl2.className = 'bg-[#00d27f]/20 text-[#00d27f] text-xs px-2 py-1 rounded border border-[#00d27f]/30';
                }
                const iconContainer2 = document.getElementById('node-icon-container-2');
                if (iconContainer2) {
                    iconContainer2.className = 'w-10 h-10 rounded bg-[#00d27f]/20 flex items-center justify-center text-[#00d27f]';
                }
            }
            
            // Update gauges and values
            const moisture2 = n2.sensor.moisture;
            const temp2 = n2.sensor.temperature;
            const mVal2 = document.getElementById('moisture-val-2');
            if (mVal2) mVal2.textContent = n2Offline ? '--%' : `${moisture2.toFixed(0)}%`;
            setCircularGauge('moisture-gauge-2', n2Offline ? 0 : moisture2);
            
            // Update node status card values
            const lastSeen2 = document.getElementById('status-last-seen-2');
            if (lastSeen2) lastSeen2.textContent = n2.seconds_since_last_seen === null ? 'Never' : `${n2.seconds_since_last_seen}s ago`;
            const conn2 = document.getElementById('status-connection-mode-2');
            if (conn2) conn2.textContent = n2Offline ? 'None' : 'Wi-Fi';
            
            const mState2 = document.getElementById('status-moisture-val-2');
            if (mState2) {
                mState2.textContent = n2Offline ? 'Inactive' : 'Active';
                mState2.className = n2Offline ? 'font-medium text-gray-500' : 'font-medium text-[#00ff9d]';
            }
            const tState2 = document.getElementById('status-temp-val-2');
            if (tState2) {
                tState2.textContent = n2Offline ? 'Inactive' : `Active (${temp2.toFixed(1)}°C)`;
                tState2.className = n2Offline ? 'font-medium text-gray-500' : 'font-medium text-[#00ff9d]';
            }
        }
        
        // --- NODE 3: Garden Node (AGR-Node-003) ---
        const n3 = data.nodes['AGR-Node-003'];
        const card3 = document.getElementById('soil-card-3');
        const nodeCard3 = document.getElementById('node-card-3');
        
        if (n3 && n3.sensor) {
            // Remove unconfigured opacity
            nodeCard3?.classList.remove('opacity-50');
            nodeCard3?.classList.add('border-[#00d27f]/30');
            nodeCard3?.classList.remove('border-white/5');
            
            const n3Offline = n3.sensor_status === 'Offline';
            if (n3Offline) {
                card3?.classList.add('state-offline');
                
                // Update Node 3 status card elements
                const statusEl3 = document.getElementById('node-status-3');
                if (statusEl3) {
                    statusEl3.textContent = 'OFF';
                    statusEl3.className = 'bg-red-500/20 text-red-500 text-xs px-2 py-1 rounded border border-red-500/30';
                }
                const iconContainer3 = document.getElementById('node-icon-container-3');
                if (iconContainer3) {
                    iconContainer3.className = 'w-10 h-10 rounded bg-red-500/20 flex items-center justify-center text-red-500';
                }
            } else {
                card3?.classList.remove('state-offline');
                
                // Update Node 3 status card elements
                const statusEl3 = document.getElementById('node-status-3');
                if (statusEl3) {
                    statusEl3.textContent = 'ON';
                    statusEl3.className = 'bg-[#00d27f]/20 text-[#00d27f] text-xs px-2 py-1 rounded border border-[#00d27f]/30';
                }
                const iconContainer3 = document.getElementById('node-icon-container-3');
                if (iconContainer3) {
                    iconContainer3.className = 'w-10 h-10 rounded bg-[#00d27f]/20 flex items-center justify-center text-[#00d27f]';
                }
            }
            
            // Update gauges and values
            const moisture3 = n3.sensor.moisture;
            const temp3 = n3.sensor.temperature;
            const mVal3 = document.getElementById('moisture-val-3');
            if (mVal3) mVal3.textContent = n3Offline ? '--%' : `${moisture3.toFixed(0)}%`;
            setCircularGauge('moisture-gauge-3', n3Offline ? 0 : moisture3);
            
            // Update node status card values
            const lastSeen3 = document.getElementById('status-last-seen-3');
            if (lastSeen3) lastSeen3.textContent = n3.seconds_since_last_seen === null ? 'Never' : `${n3.seconds_since_last_seen}s ago`;
            const conn3 = document.getElementById('status-connection-mode-3');
            if (conn3) conn3.textContent = n3Offline ? 'None' : 'Wi-Fi';
            
            const mState3 = document.getElementById('status-moisture-val-3');
            if (mState3) {
                mState3.textContent = n3Offline ? 'Inactive' : 'Active';
                mState3.className = n3Offline ? 'font-medium text-gray-500' : 'font-medium text-[#00ff9d]';
            }
            const tState3 = document.getElementById('status-temp-val-3');
            if (tState3) {
                tState3.textContent = n3Offline ? 'Inactive' : `Active (${temp3.toFixed(1)}°C)`;
                tState3.className = n3Offline ? 'font-medium text-gray-500' : 'font-medium text-[#00ff9d]';
            }
        }
    }
}

function updateChartData(chart, label, data) {
    if (!chart) return;
    
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(data);
    
    // Keep only last 10 points for optimal display curve
    if (chart.data.labels.length > 10) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    
    chart.update('none'); // Update without animation for smooth polling
}

async function initAnalytics() {
    // Fetch historical data for full charts
    try {
        const response = await fetch('/api/historical_data');
        const data = await response.json();
        
        const historyCtx = document.getElementById('historyChart');
        if (historyCtx) {
            new Chart(historyCtx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Soil Moisture (%)',
                            data: data.moisture,
                            borderColor: '#00d27f',
                            backgroundColor: 'rgba(0, 210, 127, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.45
                        },
                        {
                            label: 'Temperature (°C)',
                            data: data.temperature,
                            borderColor: '#ff9f43',
                            backgroundColor: 'rgba(255, 159, 107, 0.05)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.45
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { 
                            grid: { color: 'rgba(255,255,255,0.04)' }, 
                            ticks: { color: '#5e6b7e', font: { family: 'Outfit', size: 10 } } 
                        },
                        y: { 
                            grid: { color: 'rgba(255,255,255,0.04)' }, 
                            ticks: { color: '#5e6b7e', font: { family: 'Outfit', size: 10 } } 
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#ffffff', font: { family: 'Outfit' } } }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching analytics:', error);
    }
}

async function resolveAllAlerts() {
    try {
        const response = await fetch('/api/alerts/resolve', { method: 'POST' });
        if (response.ok) {
            // Force an immediate UI update
            fetchLiveData();
        }
    } catch (error) {
        console.error('Error resolving alerts:', error);
    }
}

// Premium glassmorphic toast notifications
function showToast(type, message) {
    const existing = document.getElementById('agrisense-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'agrisense-toast';
    toast.className = `fixed bottom-6 right-6 z-50 max-w-sm w-full backdrop-blur-xl border px-5 py-3.5 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] flex items-center gap-3.5 transition-all duration-300 transform translate-y-10 opacity-0`;
    
    if (type === 'success') {
        toast.className += ' bg-[#081510]/80 border-[#00ff9d]/30 text-[#00ff9d]';
        toast.innerHTML = `
            <div class="bg-[#00ff9d]/20 w-8 h-8 rounded-full flex items-center justify-center text-[#00ff9d]">
                <i class="fa-solid fa-circle-check"></i>
            </div>
            <div class="flex-1">
                <p class="font-extrabold text-[11px] uppercase tracking-wider text-white">Manual Override Success</p>
                <p class="text-xs text-[#00ff9d]/80 mt-0.5">${message}</p>
            </div>
        `;
    } else {
        toast.className += ' bg-[#1a0c0c]/80 border-red-500/30 text-[#ff4d4d]';
        toast.innerHTML = `
            <div class="bg-red-500/20 w-8 h-8 rounded-full flex items-center justify-center text-[#ff4d4d]">
                <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <div class="flex-1">
                <p class="font-extrabold text-[11px] uppercase tracking-wider text-white">Override Failed</p>
                <p class="text-xs text-red-400 mt-0.5">${message}</p>
            </div>
        `;
    }
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
    }, 50);
    
    setTimeout(() => {
        toast.classList.add('translate-y-10', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Bind manual pump controllers to window
window.triggerManualPumpController = async function() {
    try {
        const response = await fetch('/api/pump/trigger', { method: 'POST' });
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast('success', data.message);
            setTimeout(fetchLiveData, 500);
        } else {
            showToast('error', data.message || 'Error occurred while trying to trigger pump.');
        }
    } catch (error) {
        console.error('Error trying to trigger pump:', error);
        showToast('error', 'Connection to backend failed.');
    }
};

window.stopManualPumpController = async function() {
    try {
        const response = await fetch('/api/pump/stop', { method: 'POST' });
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast('success', data.message);
            setTimeout(fetchLiveData, 500);
        } else {
            showToast('error', data.message || 'Error occurred while trying to stop pump.');
        }
    } catch (error) {
        console.error('Error trying to stop pump:', error);
        showToast('error', 'Connection to backend failed.');
    }
};

// Toggle between AI Logs and Pump History Tabs
function switchTab(tab) {
    currentTab = tab;
    const tabAi = document.getElementById('tab-ai-logs');
    const tabPump = document.getElementById('tab-pump-history');
    const listAi = document.getElementById('ai-logs-list');
    const listPump = document.getElementById('pump-logs-list');
    
    if (tab === 'ai') {
        tabAi?.classList.remove('text-gray-500', 'hover:text-gray-300', 'border-transparent');
        tabAi?.classList.add('text-white', 'border-[#00ff9d]');
        tabPump?.classList.remove('text-white', 'border-[#00ff9d]');
        tabPump?.classList.add('text-gray-500', 'hover:text-gray-300', 'border-transparent');
        
        listAi?.classList.remove('hidden');
        listPump?.classList.add('hidden');
    } else {
        tabPump?.classList.remove('text-gray-500', 'hover:text-gray-300', 'border-transparent');
        tabPump?.classList.add('text-white', 'border-[#00ff9d]');
        tabAi?.classList.remove('text-white', 'border-[#00ff9d]');
        tabAi?.classList.add('text-gray-500', 'hover:text-gray-300', 'border-transparent');
        
        listAi?.classList.add('hidden');
        listPump?.classList.remove('hidden');
        
        fetchPumpHistory();
    }
}

// Fetch pump logs from the server
async function fetchPumpHistory() {
    try {
        const response = await fetch('/api/irrigation/history');
        if (response.ok) {
            const data = await response.json();
            renderPumpHistory(data);
        }
    } catch (error) {
        console.error('Error fetching pump history:', error);
    }
}

// Render pump logs in the UI with a premium visual presentation
function renderPumpHistory(logs) {
    const container = document.getElementById('pump-logs-list');
    if (!container) return;
    
    if (!logs || logs.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500 text-center py-4">No pump history records yet.</p>';
        return;
    }
    
    container.innerHTML = '';
    logs.forEach(log => {
        const item = document.createElement('div');
        
        const isRunning = !log.end_time;
        const itemClass = isRunning ? 'override animate-pulse' : 'success';
        const statusText = isRunning ? 'Pump Running' : (log.trigger_type === 'Manual Override' ? 'Manual Override Cycle' : 'Automatic Irrigation');
        
        // Format start time
        let startStr = 'Unknown';
        if (log.start_time) {
            const startDate = new Date(log.start_time + ' UTC');
            startStr = startDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) + ' - ' + startDate.toLocaleDateString([], {month: 'short', day: 'numeric'});
        }
        
        let detailsHtml = '';
        if (isRunning) {
            const startMoistureText = log.start_moisture !== null ? `${log.start_moisture.toFixed(1)}%` : '--%';
            detailsHtml = `
                <p class="text-xs text-yellow-300/90 flex items-center gap-1.5 mt-0.5">
                    <i class="fa-solid fa-spinner animate-spin text-[10px]"></i>
                    Started at ${startMoistureText} • Watering in progress...
                </p>
                <p class="text-[10px] text-gray-500 mt-1">
                    On at: ${startStr}
                </p>
            `;
        } else {
            const startMoistureText = log.start_moisture !== null ? `${log.start_moisture.toFixed(1)}%` : '--%';
            const endMoistureText = log.end_moisture !== null ? `${log.end_moisture.toFixed(1)}%` : '--%';
            const durationText = log.duration_seconds ? `${log.duration_seconds}s` : 'completed';
            
            detailsHtml = `
                <p class="text-xs text-[#00ff9d] flex items-center gap-1.5 mt-0.5">
                    <i class="fa-solid fa-droplet text-[10px]"></i>
                    Moisture: ${startMoistureText} &rarr; ${endMoistureText} (Sufficient)
                </p>
                <p class="text-[10px] text-gray-400 mt-1 flex justify-between">
                    <span>Duration: ${durationText}</span>
                    <span>On at: ${startStr}</span>
                </p>
            `;
        }
        
        item.className = `log-item ${itemClass}`;
        item.innerHTML = `
            <div class="flex justify-between items-baseline">
                <span class="text-xs text-gray-400">${log.trigger_type}</span>
            </div>
            <p class="text-sm font-bold mt-0.5 ${isRunning ? 'text-[#ff9f43]' : 'text-[#00ff9d]'}">${statusText}</p>
            ${detailsHtml}
        `;
        container.appendChild(item);
    });
}

// Bind to window scope so onclick calls can find them
window.switchTab = switchTab;
window.fetchPumpHistory = fetchPumpHistory;

// Robust Keyless HTTPS Auto-Geolocation Flow
async function runAutoGeolocation(onSuccess) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = parseFloat(position.coords.latitude).toFixed(6);
                const lon = parseFloat(position.coords.longitude).toFixed(6);
                await onSuccess(lat, lon);
            },
            async (error) => {
                console.log("GPS geolocation failed or denied, trying IP fallback...", error);
                await runIPGeolocation(onSuccess);
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
        );
    } else {
        await runIPGeolocation(onSuccess);
    }
}

async function runIPGeolocation(onSuccess) {
    // Try FreeIPAPI (HTTPS, free, keyless, very reliable)
    try {
        const response = await fetch('https://freeipapi.com/api/json');
        if (response.ok) {
            const data = await response.json();
            if (data.latitude && data.longitude) {
                await onSuccess(data.latitude, data.longitude);
                return;
            }
        }
    } catch (e) {
        console.log("FreeIPAPI geolocator failed: ", e);
    }
    
    // Try IPInfo.io (HTTPS, free, keyless)
    try {
        const response = await fetch('https://ipinfo.io/json');
        if (response.ok) {
            const data = await response.json();
            if (data.loc) {
                const locParts = data.loc.split(',');
                await onSuccess(parseFloat(locParts[0]), parseFloat(locParts[1]));
                return;
            }
        }
    } catch (e) {
        console.log("IPInfo geolocator failed: ", e);
    }
    
    // Try ipapi.co (HTTPS, free, keyless fallback)
    try {
        const response = await fetch('https://ipapi.co/json/');
        if (response.ok) {
            const data = await response.json();
            if (data.latitude && data.longitude) {
                await onSuccess(data.latitude, data.longitude);
                return;
            }
        }
    } catch (e) {
        console.log("ipapi.co geolocator failed: ", e);
    }
}

let geolocationRun = false;
async function checkAndAutoGeolocate(serverLat, serverLon) {
    if (sessionStorage.getItem('geolocated') || geolocationRun) {
        return;
    }
    geolocationRun = true;
    
    await runAutoGeolocation(async (lat, lon) => {
        const latDiff = Math.abs(parseFloat(serverLat) - parseFloat(lat));
        const lonDiff = Math.abs(parseFloat(serverLon) - parseFloat(lon));
        
        sessionStorage.setItem('geolocated', 'true');
        
        // If difference is more than 0.02 degrees (~2 km), update server!
        if (latDiff > 0.02 || lonDiff > 0.02) {
            console.log("Detected significant location shift. Updating server coordinates to:", lat, lon);
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        latitude: parseFloat(lat),
                        longitude: parseFloat(lon),
                        auto_location_enabled: true
                    })
                });
                // Force weather refresh
                if (typeof fetchWeatherData === 'function') {
                    fetchWeatherData();
                }
            } catch (error) {
                console.error("Failed to auto-save coordinates:", error);
            }
        }
    });
}



