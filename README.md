🔋 Battery Monitoring..............................

Variables: battery_percentage, battery_voltage

Battery charge/discharge curve (trend over time).

Estimated backup time left (based on current load).

Battery health indicator (if voltage drops too fast).

Charge/discharge cycles count.


🌞 Solar Panel Monitoring...................................

Variables: solar_voltage, solar_current, solar_power, light_intensity

Solar panel efficiency (%) = (solar_power / (irradiance * panel_area)) * 100.

Sunlight vs. power curve (how well panels respond to sunlight).

Peak solar hours captured.



⚡ Load Monitoring.......................................................................................................

Variables: voltage, current, power, energy, power_factor, frequency

Real-time load usage (Wattage).

Daily/weekly energy consumption (energy).

Power quality metrics:

frequency stability (should stay near 50 Hz).

power_factor (how efficiently load uses energy).

Load trends: when peak usage happens.





🌤 Weather Correlation.............................................................................................

Variables: ESP32 + weather API (irradiance, temperature, humidity, cloud_cover)

Compare solar output vs. weather (e.g., cloudy day = lower solar).

Show predicted solar vs actual → efficiency dashboard.....

Heatmap of solar production vs. temperature.









🔌 Relay Control Monitoring...................................

Variable: nonessentialrelaystate

Show whether non-essential loads are ON/OFF.

Track relay switching history (how often system cuts non-essential loads).

Correlate with battery % (e.g., at what level relay usually trips).




Daily solar energy produced (sum of solar_power * time).
