// Models were: "Jurre brishti", "Muva kubwa"
// Models: "6h accumulation", "24h accumulation"
let modelName = "6h accumulation";
let datasetName = "IMERG";
let forecastModel = "ECMWF IFS";
// Regions: Burundi, Djibouti, Eritrea, Ethiopia, Kenya, Rwanda, Somalia, South Sudan,
//          Sudan, Tanzania, Uganda, ICPAC, East Africa, All.
let regionName = "East Africa";
let units = "mm/6h"; // Can be mm/h, mm/6h, mm/day, mm/week
let style = "Default"; // Can be "Default", "ICPAC", "KMD", "EMI", "ECMWF".
let plotType = "Probability"; // Can be "Probability", "Values", "Mean" or "Std".
let showPercentages = true; // On the colour scale
let maxRain = 1 / 24; // Rainfall threshold in mm/h
let probability = 0.95; // Between 0 and 1

let drawMarker = false; // Draw the marker corresponding to the histogram location
let activeHistogramCanvas = -1; // Which canvas index has the active histogram (-1 = none)
let locationChanged = false; // Did the lon/lat location of the histogram change?
let canvasClickX = 0; // Where in the canvas the click was registered
let canvasClickY = 0;
let longitudeIdx = 0; // Which location are we plotting
let latitudeIDx = 0;

let Data_Source_Base = window.Data_Source_URL || "/data/";
let Static_URL = window.Static_Source_Url ||  "/static/";
// Set only when HOST_PLATFORM=cloud_run: the forecast-data bucket's interface/ folder
let Dataset_Source_Base = window.Dataset_Source_URL || "";

// Returns the data URL prefix for the current dataset + model combination.
// IMERG data lives at the base URL (backwards compatible with existing deployment).
// Additional datasets live under subdirectories: /data/chirps/, /data/rfe/
// On Cloud Run (HOST_PLATFORM=cloud_run) every dataset, IMERG included, has its own
// folder in the bucket: interface/imerg/counts_*, interface/rfe/..., interface/chirps/...
function getDataPrefix() {
    let key = datasetName.toLowerCase();  // "imerg", "rfe", "chirps"
    if (Dataset_Source_Base) {
        return Dataset_Source_Base + key + "/";  // .../interface/imerg/counts_6h/...
    }
    if (key === "imerg") {
        return Data_Source_Base;  // backwards compatible: /data/counts_6h/...
    }
    return Data_Source_Base + key + "/";  // /data/chirps/counts_6h/...
}
// Hack to make sure clicking in the plot is handled correctly
let canvasMouseDownRects = [];

// Track which canvases already have mouse listeners to avoid adding duplicates
let canvasListenersAttached = new Set();

// Counter to abort stale draw operations — only the latest draw runs to completion
let drawGeneration = 0;

// Hack to force reloading of dates files
let dateLoadNumber = Math.floor(Math.random() * 10000);

let availableDates; // An object containing the dates we can use
let GANForecast = []; // An array of countsData objects

let validTimes = []; // An array of valid times, set in updateDateMenus

// Called by the Accumulation Period dropdown
async function modelSelect() {
  modelName = document.getElementById("modelSelect").value;

  // Switch units to match the accumulation period
  if (modelName == "24h accumulation") {
    units = "mm/day";
  } else {
    units = "mm/6h";
  }
  document.getElementById("unitsSelect").value = units;
  document.getElementById("unitsDescription").innerHTML = units;
  let norm = getPlotNormalisation(units);
  document.getElementById("thresholdValueSelect").value = roundSF(maxRain * norm, 3);

  updateDatasetOptions();
  updateModelDescription();

  await loadDates();
  await loadForecast();
  drawMarker = false;
  activeHistogramCanvas = -1;
  document.getElementById("removeHistBttn").style.display = "none";
  drawPlots();
}

// Update the Reference Dataset dropdown options based on accumulation period
function updateDatasetOptions() {
  let sel = document.getElementById("datasetSelect");
  if (modelName == "6h accumulation") {
    sel.innerHTML = '<option value="IMERG">IMERG</option>';
    datasetName = "IMERG";
  } else {
    sel.innerHTML = '<option value="IMERG">IMERG</option><option value="RFE">RFE</option><option value="CHIRPS">CHIRPS</option>';
    sel.value = datasetName;
  }
}

// Called by the Forecast Model dropdown
async function forecastModelSelect() {
  forecastModel = document.getElementById("forecastModelSelect").value;
  updateModelDescription();

  await loadDates();
  await loadForecast();
  drawMarker = false;
  activeHistogramCanvas = -1;
  document.getElementById("removeHistBttn").style.display = "none";
  drawPlots();
}

// Called by the Reference Dataset dropdown
async function datasetSelect() {
  datasetName = document.getElementById("datasetSelect").value;
  updateModelDescription();

  await loadDates();
  await loadForecast();
  drawMarker = false;
  activeHistogramCanvas = -1;
  document.getElementById("removeHistBttn").style.display = "none";
  drawPlots();
}

// Build the dynamic description sentence from current selections
function updateModelDescription() {
  let accum = modelName == "24h accumulation" ? "24-hour" : "6-hour";
  let dataset = datasetName;
  let model = forecastModel;

  let datasetLinks = {
    "IMERG": '<a href="https://gpm.nasa.gov/data/imerg" target="_blank">IMERG</a>',
    "RFE": '<a href="https://www.cpc.ncep.noaa.gov/products/international/data.shtml" target="_blank">RFE</a>',
    "CHIRPS": '<a href="https://www.chc.ucsb.edu/data/chirps" target="_blank">CHIRPS</a>'
  };

  let modelLinks = {
    "ECMWF IFS": '<a href="https://www.ecmwf.int/" target="_blank">ECMWF</a> <a href="https://confluence.ecmwf.int/display/FUG/Section+2+The+ECMWF+Integrated+Forecasting+System+-+IFS" target="_blank">IFS</a>',
    "GEFS": '<a href="https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast" target="_blank">GEFS</a>'
  };

  let desc = "The " + (modelLinks[model] || model) + " forecast is post-processed using a " +
    '<a href="https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022MS003120" target="_blank">cGAN</a>' +
    " trained on " + (datasetLinks[dataset] || dataset) + " observations (2018\u20132021)" +
    " to generate improved " + accum + " accumulated rainfall forecasts.";

  document.getElementById("modelDescription").innerHTML = desc;
}

// Called by the regionSelect menu
function regionSelect() {
  regionName = document.getElementById("regionSelect").value;
  drawMarker = false; // No longer draw the histograms
  activeHistogramCanvas = -1;
  document.getElementById("removeHistBttn").style.display = "none"; // Hide the button
  window.adminBBox = null;
  window.adminRegionName = null;
  populateAdmin1(regionName);
  drawPlots();
}

// Populate the Admin 1 sub-selector for the chosen country (hidden for East Africa view).
async function populateAdmin1(country) {
  const grp = document.getElementById("admin1Group");
  const sel = document.getElementById("admin1Select");
  if (country == "East Africa" || country == "ICPAC" || country == "all") {
    grp.style.display = "none";
    sel.innerHTML = '<option value="">— whole country —</option>';
    return;
  }
  if (!window.regionBBoxes) {
    try {
      window.regionBBoxes = await (
        await fetch(`${Static_URL}boundaries/region_bboxes.json`)
      ).json();
    } catch (e) {
      window.regionBBoxes = {};
    }
  }
  const regs = window.regionBBoxes[country] || [];
  let html = '<option value="">— whole country —</option>';
  for (const r of regs)
    html += '<option value="' + r.name + '">' + r.name + "</option>";
  sel.innerHTML = html;
  grp.style.display = regs.length > 1 ? "" : "none";
}

// Zoom the map to a selected admin-1 region (or back to the whole country when blank).
function admin1Select() {
  const country = document.getElementById("regionSelect").value;
  const name = document.getElementById("admin1Select").value;
  window.adminBBox = null;
  window.adminRegionName = name || null;
  if (name && window.regionBBoxes && window.regionBBoxes[country]) {
    const hit = window.regionBBoxes[country].find((r) => r.name === name);
    if (hit) window.adminBBox = hit.bbox;
  }
  drawMarker = false;
  activeHistogramCanvas = -1;
  document.getElementById("removeHistBttn").style.display = "none";
  drawPlots();
}

// Called by the initYearSelect, initMonthSelect,initDaySelect and initTimeSelect menus
async function initTimeSelect() {
  updateDateMenus();
  await loadForecast();
  drawPlots();
}

// Called by the validTimeSelect menu
async function validTimeSelect() {
  await loadForecast();
  drawPlots();
}

// Called by the styleSelect menu
function styleSelect() {
  style = document.getElementById("styleSelect").value;
  drawPlots();
}

// Called by the plotSelect menu
function plotSelect() {
  plotType = document.getElementById("plotSelect").value;
  if (plotType == "Probability") {
    document.getElementById("percentagesSelect").removeAttribute("disabled", "");
  } else {
    document.getElementById("percentagesSelect").setAttribute("disabled", "");
  }
  drawPlots();
}

// Called when the focus is lost in the value threshold input
function pValueThresholdInput() {
  drawPlots();
}

// Called by the percentagesSelect menu
function percentagesSelect() {
  if (document.getElementById("percentagesSelect").value == "Percentages") {
    showPercentages = true;
  } else {
    showPercentages = false;
  }
  drawPlots();
}

// Called when the focus is lost in the probability threshold input
function pProbabilityThresholdInput() {
  drawPlots();
}

// Called by the unitsSelect menu
function unitsSelect() {
  // Get the unitsSelect menu's value
  units = document.getElementById("unitsSelect").value;

  // Set the units in the description to the selected units
  document.getElementById("unitsDescription").innerHTML = units;

  // Update the value threshold to display in the current units
  norm = getPlotNormalisation(units);
  document.getElementById("thresholdValueSelect").value = roundSF(maxRain * norm, 3);

  // Draw plots with the new units
  drawPlots();
}

// Called by the showExplanations input checkbox
function showExplanation() {
  let plotType = document.getElementById("plotSelect").value;

  // If the ensemble mean or standard deviation is plotted the explanation box is always checked
  if (plotType == "Mean" || plotType == "Std") {
    document.getElementById("showExplanation").checked = true;
    document.getElementById("showExplanation").disabled = true;
  } else {
    document.getElementById("showExplanation").disabled = false;
  }

  const checked = document.getElementById("showExplanation").checked;
  let panel = document.getElementById("mapExplanationText");

  if (!checked) {
    panel.style.display = "none";
    return;
  }

  let accumulationTime = 6;
  let easiestUnits = "mm/6h";
  if (document.getElementById("modelSelect").value == "24h accumulation") {
    accumulationTime = 24;
    easiestUnits = "mm/day";
  }
  let thresholdValue = document.getElementById("thresholdValueSelect").value;
  let thresholdProbability = document.getElementById("thresholdProbabilitySelect").value;
  let units = document.getElementById("unitsSelect").value;

  let html = "";

  if (plotType == "Probability") {
    html += `<div class="explanation-heading">Map Description</div>`;
    html += `<p>The map shows the <strong>chance that rainfall accumulated over ${accumulationTime} hours</strong> between the valid times will be above <strong>${thresholdValue} ${units}</strong> at each location. This chance is calculated from the histogram at each location.</p>`;
    html += `<p>Each colour covers a range of probabilities. There are only five categories to avoid overconfidence in accuracy and to keep the plot clear. Precise probabilities are available from the histograms.</p>`;
    html += `<div class="explanation-tip"><strong>Tip:</strong> Change the value threshold (currently ${thresholdValue} ${units}) in the "Value Threshold" box above. Set units via the "Units" menu. For example, for rainfall above 20 mm/day, set units to "mm/day" then threshold to "20". Using "${easiestUnits}" means values correspond to total rainfall over the ${accumulationTime}-hour period. The colour scale labels can be toggled between percentages and words above.</div>`;

    if (drawMarker) {
      html += `<div class="explanation-heading" style="margin-top: 1rem;">Histogram Description</div>`;
      html += `<p>The histogram to the right of each map shows the rainfall predicted by each ensemble member at the marked location. Each bar shows the number of members predicting rainfall in that interval.</p>`;
      html += `<p>The <strong style="color: #3498db;">blue line</strong> marks the value threshold (${thresholdValue} ${units}). Members to its right divided by total members gives the exceedance probability. The <strong style="color: #e74c3c;">red line</strong> marks the ${thresholdProbability}% point — ${thresholdProbability}% of members are to its left. Adjust this in the "Probability Threshold" box.</p>`;
    } else {
      html += `<p class="explanation-action">Click on the map to show the histogram at that point.</p>`;
    }

  } else if (plotType == "Values") {
    html += `<div class="explanation-heading">Map Description</div>`;
    html += `<p>The map shows that for rainfall accumulated over <strong>${accumulationTime} hours</strong>, <strong>${thresholdProbability}%</strong> of ensemble members predicted rainfall <em>below</em> the plotted value at each location. The remaining members predicted rainfall above it.</p>`;
    html += `<div class="explanation-tip"><strong>Tip:</strong> Change the probability threshold (currently ${thresholdProbability}%) in the box above. 50% = <em>ensemble median</em> (good alternative to the mean for rainfall). 95% means only 5% of members exceeded the plotted value — useful for estimating rainfall range. Units in "${easiestUnits}" means values correspond to total rainfall over the ${accumulationTime}-hour period.</div>`;

    if (drawMarker) {
      html += `<div class="explanation-heading" style="margin-top: 1rem;">Histogram Description</div>`;
      html += `<p>The histogram shows the rainfall predicted by each ensemble member at the marked location. Each bar shows the number of members predicting rainfall in that interval.</p>`;
      html += `<p>The <strong style="color: #e74c3c;">red line</strong> marks the ${thresholdProbability}% point. The <strong style="color: #3498db;">blue line</strong> marks the value threshold (${thresholdValue} ${units}) — members to its right divided by total members gives the exceedance probability.</p>`;
    } else {
      html += `<p class="explanation-action">Click on the map to show the histogram at that point.</p>`;
    }

  } else if (plotType == "Mean") {
    html += `<div class="explanation-heading">Map Description</div>`;
    html += `<p>The map shows the <strong>ensemble mean rainfall</strong> accumulated over ${accumulationTime} hours between the valid times at each location.</p>`;
    html += `<p class="explanation-warning">Warning: The ensemble mean is usually not a good summary statistic for rainfall forecasts.</p>`;
    html += `<div class="explanation-tip">The predicted rainfall distribution is far from normal (see the histograms), making the ensemble mean difficult to interpret. A better alternative is the <em>ensemble median</em>: select "Values below probability" and set the probability threshold to 50%.</div>`;

    if (drawMarker) {
      html += `<div class="explanation-heading" style="margin-top: 1rem;">Histogram Description</div>`;
      html += `<p>The histogram shows the rainfall predicted by each ensemble member at the marked location.</p>`;
      html += `<p>The <strong style="color: #3498db;">blue line</strong> marks the value threshold (${thresholdValue} ${units}). The <strong style="color: #e74c3c;">red line</strong> marks the ${thresholdProbability}% point.</p>`;
    } else {
      html += `<p class="explanation-action">Click on the map to show the histogram at that point.</p>`;
    }

  } else if (plotType == "Std") {
    html += `<div class="explanation-heading">Map Description</div>`;
    html += `<p>The map shows the <strong>ensemble standard deviation</strong> of rainfall accumulated over ${accumulationTime} hours between the valid times at each location.</p>`;
    html += `<p class="explanation-warning">Warning: The ensemble standard deviation is usually not a good summary statistic for rainfall forecasts.</p>`;
    html += `<div class="explanation-tip">The predicted rainfall distribution is far from normal, making the standard deviation difficult to interpret. A better alternative for estimating rainfall range: select "Values below probability" and set the probability threshold to 95%.</div>`;

    if (drawMarker) {
      html += `<div class="explanation-heading" style="margin-top: 1rem;">Histogram Description</div>`;
      html += `<p>The histogram shows the rainfall predicted by each ensemble member at the marked location.</p>`;
      html += `<p>The <strong style="color: #3498db;">blue line</strong> marks the value threshold (${thresholdValue} ${units}). The <strong style="color: #e74c3c;">red line</strong> marks the ${thresholdProbability}% point.</p>`;
    } else {
      html += `<p class="explanation-action">Click on the map to show the histogram at that point.</p>`;
    }
  }

  panel.innerHTML = html;
  panel.style.display = "block";
}

// Called by the removeHistBttn button
function removeHistograms() {
  drawMarker = false; // No longer draw the histograms
  activeHistogramCanvas = -1; // No canvas has a histogram
  document.getElementById("removeHistBttn").style.display = "none"; // Hide the button
  drawPlots();
}

// Loads and plots the currently selected forecast
async function loadForecast() {
  let year = document.getElementById("initYearSelect").value;
  let month = document.getElementById("initMonthSelect").value;
  let day = document.getElementById("initDaySelect").value;
  let time = document.getElementById("initTimeSelect").value;
  let validTimeMenu = document.getElementById("validTimeSelect").value;

  // The directory name depends upon which model we are looking at
  let countsDir;
  let accumulationHours;
  if (modelName == "6h accumulation") {
    countsDir = "counts_6h";
    accumulationHours = 6;
  } else if (modelName == "24h accumulation") {
    countsDir = "counts_24h";
    accumulationHours = 24;
  }

  // If we should load all valid times
  if (validTimeMenu == "All") {
    for (let i = 0; i < validTimes.length; i++) {
      // The cGAN forecast file to load
      let fileName =
        getDataPrefix() +
        countsDir +
        "/" +
        year +
        "/counts_" +
        year +
        month.padStart(2, "0") +
        day.padStart(2, "0") +
        "_" +
        time.padStart(2, "0") +
        "_" +
        validTimes[i] +
        "h.nc";

      // Load data into the forecastDataObject
      await GANForecast[i].loadGANForecast(fileName, modelName, accumulationHours);
    }
  } else {
    // Load a single valid time
    // The cGAN forecast file to load
    let fileName =
      getDataPrefix() +
      countsDir +
      "/" +
      year +
      "/counts_" +
      year +
      month.padStart(2, "0") +
      day.padStart(2, "0") +
      "_" +
      time.padStart(2, "0") +
      "_" +
      validTimeMenu +
      "h.nc";

    // Load data into the forecastDataObject
    await GANForecast[0].loadGANForecast(fileName, modelName, accumulationHours);
  }
}

// Update an HTML select menu with dates that are available.
// dateObject - Can be a years, months, day or time object (from the global
//              availableDates).
// dateText   - An array containing the menu item strings to use. If empty the dateObject
//              keys are used as menu items.
// id         - The id of the select menu element in the HTML.
function updateMenu(dateObject, datesText, id) {
  let dates;
  if (dateObject instanceof Array) {
    // dateObject is an array of numbers. Convert it to an array of strings
    dates = new Array(dateObject.length);
    for (let i = 0; i < dates.length; i++) {
      dates[i] = String(dateObject[i]);
    }
  } else {
    // dateObject's keys are a list of strings
    dates = Object.keys(dateObject);
  }

  // Select the HTML select menu that we are updating
  let dateSelect = document.getElementById(id);

  // Record the menu's value before we remove it
  let date = dateSelect.value;

  // Remove all of the current menu items
  while (dateSelect.hasChildNodes()) {
    dateSelect.removeChild(dateSelect.firstChild);
  }

  // Add the menu items specified in dates
  for (let i = 0; i < dates.length; i++) {
    let option = document.createElement("option");
    option.value = dates[i];
    if (datesText.length > 0) {
      option.innerHTML = datesText[i];
    } else {
      option.innerHTML = dates[i];
    }
    dateSelect.appendChild(option);
  }

  // Add the "Plot all valid times" menu item.
  if (datesText.length > dateObject.length) {
    if (datesText[datesText.length - 1] == "Plot all valid times") {
      let option = document.createElement("option");
      option.value = "All";
      option.innerHTML = "Plot all valid times";
      dateSelect.appendChild(option);
    }
  }

  if (date != "All") {
    // If the specified year/month/day/time/valid time does not exist.
    if (!dates.includes(date)) {
      date = dates[dates.length - 1]; // Pick the final one
    }
  }

  // Set the menu to the value it should be
  dateSelect.value = date;

  // Return the value set
  return date;
}

function updateDateMenus() {
  // The available months are listed in availableDates
  year = updateMenu(availableDates, [], "initYearSelect");

  // The available months depend upon the year
  let yearObject = availableDates[String(year)];
  month = updateMenu(yearObject, [], "initMonthSelect");

  // The available days depend upon the year and month
  let monthObject = yearObject[String(month)];
  day = updateMenu(monthObject, [], "initDaySelect");

  // The available times depend upon the year, month and day
  let daysObject = monthObject[String(day)];
  // We use a custom string for the time menu elements
  let times = Object.keys(daysObject);
  let timeStrings = new Array(times.length);
  for (let i = 0; i < times.length; i++) {
    timeStrings[i] = times[i].padStart(2, "0") + ":00 UTC";
  }
  time = updateMenu(daysObject, timeStrings, "initTimeSelect");

  // The available valid times depend upon the year, month, day and time.
  validTimes = daysObject[String(time)]; // validTimes is an Array
  // We use a custom string for the valid time menu elements
  let validTimeStrings = new Array(validTimes.length + 1);
  for (let i = 0; i < validTimes.length; i++) {
    // What's the valid date? (YYYY-MM-DD)
    validDate = timeOffsetToDate(validTimes[i] + parseInt(time), year + "-" + String(month).padStart(2, "0") + "-" + String(day).padStart(2, "0"));

    validTimeStrings[i] =
      validDate.getUTCFullYear() +
      "-" +
      String(validDate.getUTCMonth() + 1).padStart(2, "0") +
      "-" +
      String(validDate.getUTCDate()).padStart(2, "0") +
      " " +
      String(validDate.getUTCHours()).padStart(2, "0") +
      ":00 UTC (+" +
      validTimes[i] +
      "h)";
  }
  // Add an "Plot all valid times" option
  validTimeStrings[validTimes.length] = "Plot all valid times";
  updateMenu(validTimes, validTimeStrings, "validTimeSelect");

  // Set "Plot all valid times" as the default
  document.getElementById("validTimeSelect").value = "All";
}

async function loadDates() {
  // Fetch a remote file
  let fileName;
  if (modelName == "6h accumulation") {
    fileName = `${getDataPrefix()}counts_6h/available_dates.json?${dateLoadNumber}`;
  } else if (modelName == "24h accumulation") {
    fileName = `${getDataPrefix()}counts_24h/available_dates.json?${dateLoadNumber}`;
  }
  // dateLoadNumber ensures that the available_dates.json file is not cached
  dateLoadNumber += 1;
  if (dateLoadNumber > 10000) {
    dateLoadNumber = 0;
  }
  const response = await fetch(fileName);

  // No forecasts published yet for this dataset/accumulation: say so and clear the stale
  // maps of the previous selection, rather than failing on response.json() silently.
  if (!response.ok) {
    for (const canvas of document.querySelectorAll("#plotsContainer canvas")) {
      canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    }
    showLoadingStatus(1, `No ${datasetName} ${modelName} forecasts available (${fileName.split("?")[0]}: HTTP ${response.status}).`);
    throw new Error(`Response status: ${response.status} for ${fileName}`);
  }

  // Parse the JSON arrayBuffer of the file and return the resulting object
  availableDates = await response.json();

  // Pick the final date to load
  // 	let years = Object.keys(availableDates);
  // 	let year = years[years.length-1];
  // 	let yearObject = availableDates[year];
  // 	let months = Object.keys(yearObject);
  // 	let month = months[months.length-1];
  // 	let monthObject = yearObject[month];
  // 	let days = Object.keys(monthObject);
  // 	let day = days[days.length-1];
  // 	let daysObject = monthObject[day];
  // 	let times = Object.keys(daysObject);
  // 	let time = times[times.length-1];
  // 	let validTimes = daysObject[time];
  // 	let validTime = validTimes[validTimes.length-1];

  // Set the menus to match the loaded dates
  // Probably doesn't do anything. Overridden by updateDateMenus.
  // 	document.getElementById("initYearSelect").value = year;
  // 	document.getElementById("initMonthSelect").value = month;
  // 	document.getElementById("initDaySelect").value = day;
  // 	document.getElementById("initTimeSelect").value = time;
  // 	document.getElementById("validTimeSelect").value = String(validTime);

  updateDateMenus();

  // By default plot all lead times
  // 	document.getElementById("validTimeSelect").value = "All";
}

function initControls() {
  // XXX Actually should keep the settings on reload and reload the correct plots

  // Following the HTML elements in order

  document.getElementById("modelSelect").value = modelName;
  document.getElementById("forecastModelSelect").value = forecastModel;
  updateDatasetOptions();
  updateModelDescription();

  // Canvas visibility is handled by drawPlots() based on validTimes.length

  document.getElementById("regionSelect").value = regionName;

  document.getElementById("styleSelect").value = style;

  document.getElementById("plotSelect").value = plotType;

  // Need to get the units correct
  norm = getPlotNormalisation(units);
  document.getElementById("thresholdValueSelect").value = roundSF(maxRain * norm, 3);

  document.getElementById("unitsDescription").innerHTML = units;

  if (showPercentages) {
    document.getElementById("percentagesSelect").value = "Percentages";
  } else {
    document.getElementById("percentagesSelect").value = "Words";
  }

  if (plotType == "Probability") {
    document.getElementById("percentagesSelect").removeAttribute("disabled", "");
  } else {
    document.getElementById("percentagesSelect").setAttribute("disabled", "");
  }

  document.getElementById("thresholdProbabilitySelect").value = roundSF(probability * 100, 4);

  document.getElementById("unitsSelect").value = units;
}

// Function to inform the user what is going on
//    code - 0 = Not waiting
//           1 = Waiting for data to load
//           2 = Waiting for calculations
//           3 = Waiting for plots to draw
// message - A description of what we are waiting for
function showLoadingStatus(code, message) {
  if (code == 0) {
    // We are not waiting
    document.getElementById("statusText").style.color = "black";
  } else {
    // We are waiting
    document.getElementById("statusText").style.color = "#cc0000"; // dark red
  }

  // Inform the user what is going on
  document.getElementById("statusText").innerHTML = message;
}

async function init() {
  // Set the default values of the plot controls
  initControls();

  // Specify the function to call to inform the user what is going on
  setStatusUpdateFunction(showLoadingStatus);

  // GANForecast is a global array of countsData objects
  // XXX Make according to validTimes.length
  for (let i = 0; i < 7; i++) {
    GANForecast[i] = new countsData(); // Create a countsData object
  }

  // If the region names are not loaded yet, then load them and wait for them to be loaded
  // First argument is the directory, second argument is the file name.
  await GANForecast[0].regionSpec.loadRegionNames(`${Static_URL}boundaries`, "regional_names.json");
  // All point at the same regionSpec
  // XXX Make according to validTimes.length
  for (let i = 1; i < 7; i++) {
    GANForecast[i].regionSpec = GANForecast[0].regionSpec;
  }

  // Missing data for the default selection must not stop the keyboard handlers below
  // from being attached, so the user can still switch to a dataset that has data.
  try {
    // Load a list of the available forecasts
    await loadDates();

    // Load the currently selected forecast
    await loadForecast();

    // Draw everything
    await drawPlots();
  } catch (e) {
    console.error(e);
  }

  // Stop the default window scroll when the arrow keys are pressed.
  // XXX Probably should attach this to the relevant canvas instead, to enable arrow
  // keys in the input boxes. See:
  // https://stackoverflow.com/questions/8916620/disable-arrow-key-scrolling-in-users-browser
  window.addEventListener(
    "keydown",
    function (e) {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].indexOf(e.code) > -1) {
        e.preventDefault();
      }
    },
    false,
  );

  // Detect if the enter or return key is pressed in the document
  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      drawPlots();
    } else if (event.key === "ArrowRight") {
      // If we are currently drawing the location marker
      if (drawMarker) {
        // Increase the longitude index by one
        longitudeIdx += 1;

        // The lon/lat location changes with a mouse click
        locationChanged = false;

        // Draw the plots
        requestAnimationFrame(drawPlots);
      }
    } else if (event.key === "ArrowLeft") {
      // If we are currently drawing the location marker
      if (drawMarker) {
        // Increase the longitude index by one
        longitudeIdx -= 1;

        // The lon/lat location changes with a mouse click
        locationChanged = false;

        // Draw the plots
        requestAnimationFrame(drawPlots);
      }
    } else if (event.key === "ArrowUp") {
      // If we are currently drawing the location marker
      if (drawMarker) {
        // Increase the longitude index by one
        latitudeIdx += 1;

        // The lon/lat location changes with a mouse click
        locationChanged = false;

        // Draw the plots
        requestAnimationFrame(drawPlots);
      }
    } else if (event.key === "ArrowDown") {
      // If we are currently drawing the location marker
      if (drawMarker) {
        // Increase the longitude index by one
        latitudeIdx -= 1;

        // The lon/lat location changes with a mouse click
        locationChanged = false;

        // Draw the plots
        requestAnimationFrame(drawPlots);
      }
    }
  });
}

// Listens for the mouse in the supplied rectangle (corresponding to the plot picture)
function listenForMouse(canvasNum) {
  // Only attach the listener once per canvas to avoid accumulating duplicate handlers
  if (canvasListenersAttached.has(canvasNum)) {
    return;
  }
  canvasListenersAttached.add(canvasNum);

  // Get canvas for events
  const canvas = document.getElementById("mapCanvas" + canvasNum);

  // Detect the mouse location when it is within the canvas element
  canvas.addEventListener("mousedown", function (evt) {
    // Get the current rectangle for dealing with plot clicks from a global variable
    plotRect = canvasMouseDownRects[canvasNum];

    // Get the mouse position in the canvas element
    let canvasRect = canvas.getBoundingClientRect();
    let clickX = evt.clientX - canvasRect.left;
    let clickY = evt.clientY - canvasRect.top;

    // Account for canvas scaling (CSS display size vs actual canvas size)
    // The canvas element has a fixed size (width/height attributes) but may be
    // displayed at a different size due to CSS (getBoundingClientRect)
    let scaleX = canvas.width / canvasRect.width;
    let scaleY = canvas.height / canvasRect.height;

    // Convert click coordinates to actual canvas coordinate system
    clickX = clickX * scaleX;
    clickY = clickY * scaleY;

    // Get the mouse location within the plot image boundary
    let xMouse = Math.floor(clickX) - Math.round(plotRect[0]);
    let yMouse = Math.floor(clickY) - Math.round(plotRect[1]);

    // Width and height of the plot rectangle
    let width = Math.round(plotRect[2] - plotRect[0]);
    let height = Math.round(plotRect[3] - plotRect[1]);

    // If the mouse is within the plot rectangle
    if (xMouse >= 0 && yMouse >= 0 && xMouse < width && yMouse < height) {
      // Save the click location for other functions (in canvas coordinates)
      canvasClickX = clickX;
      canvasClickY = clickY;

      // When the plots are drawn, also draw the marker
      drawMarker = true;
      // Histograms will be shown on all visible maps
      document.getElementById("removeHistBttn").style.display = "inline"; // Show the button

      // The lon/lat location changes with a mouse click
      locationChanged = true;

      // Draw the plots
      requestAnimationFrame(drawPlots);
    }
  });
}

async function drawPlots() {
  // Increment generation so any in-progress draw knows it's stale and stops
  drawGeneration++;
  const myGeneration = drawGeneration;

  // It's easier to update the plot explanation every time the plots are drawn
  showExplanation();

  // See what the input boxes say
  let norm = getPlotNormalisation(units);
  maxRain = document.getElementById("thresholdValueSelect").value / norm;
  probability = document.getElementById("thresholdProbabilitySelect").value / 100.0;

  // Find out how many plots to make
  let plotAllValidTimes = document.getElementById("validTimeSelect").value;
  if (plotAllValidTimes == "All") {
    numCanvases = validTimes.length;
  } else {
    numCanvases = 1;
  }

  // Update canvas visibility based on numCanvases
  for (let i = 0; i < 7; i++) {
    const plotPair = document.getElementById("plotPair" + i);
    if (plotPair) {
      if (i < numCanvases) {
        plotPair.classList.remove("hidden-canvas");
        // Handle single canvas centering
        if (numCanvases === 1 && i === 0) {
          plotPair.classList.add("single-canvas-view");
        } else {
          plotPair.classList.remove("single-canvas-view");
        }
      } else {
        plotPair.classList.add("hidden-canvas");
        plotPair.classList.remove("single-canvas-view");
      }
    }
  }

  // Ensure the correct number of map canvases exist
  // Count existing canvases (don't remove pre-defined ones from HTML)
  let canvasNum = 0;
  while (document.getElementById("mapCanvas" + canvasNum) != null) {
    // Set up mouse listener for existing canvases
    listenForMouse(canvasNum);
    canvasNum += 1;
  }
  // If there are insufficient canvases, create more
  while (canvasNum < numCanvases) {
    const canvasElement = document.createElement("canvas");
    canvasElement.id = "mapCanvas" + canvasNum;
    canvasElement.width = 513;
    canvasElement.height = 504;
    canvasElement.innerHTML = "Your browser does not support the HTML canvas tag.";
    document.body.appendChild(canvasElement);
    // Listen for clicks in the canvas
    listenForMouse(canvasNum);
    canvasNum += 1;
  }

  // Create or remove histogram canvases based on drawMarker state
  for (let i = 0; i < 7; i++) {
    const plotPair = document.getElementById("plotPair" + i);
    if (!plotPair) continue;

    if (drawMarker && i < numCanvases) {
      // Create histogram canvas for each visible map
      let histCanvas = document.getElementById("histogramCanvas" + i);
      if (!histCanvas) {
        histCanvas = document.createElement("canvas");
        histCanvas.id = "histogramCanvas" + i;
        histCanvas.width = 511;
        histCanvas.height = 504;
        histCanvas.innerHTML = "Your browser does not support the HTML canvas tag.";
        plotPair.appendChild(histCanvas);
      }
      plotPair.classList.add("has-histogram");
    } else {
      // Remove histogram canvas from hidden maps
      let histCanvas = document.getElementById("histogramCanvas" + i);
      if (histCanvas) {
        histCanvas.remove();
      }
      plotPair.classList.remove("has-histogram");
    }
  }

  // Reset the array of rectangles containing map canvas boundaries
  canvasMouseDownRects = [];

  // Draw plots in each canvas
  for (let canvasNum = 0; canvasNum < numCanvases; canvasNum++) {
    // If a newer draw was requested, abort this one immediately
    if (myGeneration !== drawGeneration) return;

    // Get the context for plotting
    const canvas = document.getElementById("mapCanvas" + canvasNum);
    const ctx = canvas.getContext("2d");

    // Erase the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let x = 2,
      y = 2; // Location of plot from top left
    let width = 500; // Width of plot in pixels
    let height = 500; // Height of plot in pixels

    // Must use await unless all of the region shape data is loaded in advance
    // otherwise the region shape data could be loaded multiple times and corrupted.

    // The rectangles within which the plots are drawn
    let plotRect;
    if (plotType == "Probability") {
      plotRect = await GANForecast[canvasNum].plotExceedanceProbability(ctx, x, y, width, height, maxRain, units, style, showPercentages, regionName);
    } else if (plotType == "Values") {
      plotRect = await GANForecast[canvasNum].plotExceedanceValue(ctx, x, y, width, height, probability, units, style, regionName);
    } else if (plotType == "Mean") {
      plotRect = await GANForecast[canvasNum].plotMean(ctx, x, y, width, height, units, style, regionName);
    } else if (plotType == "Std") {
      plotRect = await GANForecast[canvasNum].plotStd(ctx, x, y, width, height, units, style, regionName);
    }

    // If a newer draw was requested, abort — don't continue with stale data
    if (myGeneration !== drawGeneration) return;

    // Save plotRect for understanding map clicks
    canvasMouseDownRects[canvasMouseDownRects.length] = plotRect;

    // Plot the marker and associated histogram for all visible canvases
    if (drawMarker) {
      // Need the longitude range in the current plot
      let [minLatIdx, maxLatIdx, minLonIdx, maxLonIdx] = GANForecast[0].computeLatLonIdxBounds(regionName);

      // If the location has changed (set the latitude and longitude indices)
      if (locationChanged) {
        // Get the mouse location within the plot image boundary
        let xMouse = Math.floor(canvasClickX) - Math.round(plotRect[0]);
        let yMouse = Math.floor(canvasClickY) - Math.round(plotRect[1]);

        // Find the corresponding latitude and longitude indices
        longitudeIdx = minLonIdx + Math.round((xMouse * (maxLonIdx - minLonIdx)) / (plotRect[2] - plotRect[0]));
        latitudeIdx = maxLatIdx - Math.round((yMouse * (maxLatIdx - minLatIdx)) / (plotRect[3] - plotRect[1]));

        // By default the location hasn't changed so set this flag now
        locationChanged = false;
      } else {
        // The location has not changed (set click location from the lat/lon indices)
        canvasClickX = ((longitudeIdx - minLonIdx) * (plotRect[2] - plotRect[0])) / (maxLonIdx - minLonIdx) + plotRect[0];
        canvasClickY = ((maxLatIdx - latitudeIdx) * (plotRect[3] - plotRect[1])) / (maxLatIdx - minLatIdx) + plotRect[1];
      }

      let markerWidth = 10; // Width of the plot marker in pixels

      // Thick black cross
      ctx.beginPath();
      ctx.strokeStyle = "#000000";
      ctx.lineWidth = 3;
      ctx.moveTo(canvasClickX - markerWidth / 2, canvasClickY - markerWidth / 2);
      ctx.lineTo(canvasClickX + markerWidth / 2, canvasClickY + markerWidth / 2);
      ctx.moveTo(canvasClickX + markerWidth / 2, canvasClickY - markerWidth / 2);
      ctx.lineTo(canvasClickX - markerWidth / 2, canvasClickY + markerWidth / 2);
      ctx.stroke();

      // Thin white cross
      ctx.beginPath();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.moveTo(canvasClickX - markerWidth / 2, canvasClickY - markerWidth / 2);
      ctx.lineTo(canvasClickX + markerWidth / 2, canvasClickY + markerWidth / 2);
      ctx.moveTo(canvasClickX + markerWidth / 2, canvasClickY - markerWidth / 2);
      ctx.lineTo(canvasClickX - markerWidth / 2, canvasClickY + markerWidth / 2);
      ctx.stroke();

      // Put a line dividing the two plots
      ctx.strokeStyle = "#b6b6b6";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(512, 25);
      ctx.lineTo(512, 504 - 25);
      ctx.stroke();

      // Create a new histogram specification
      let barChartSpec = new barChartSpecification();

      let y2 = y;
      let x2 = 8; // Change the location of the second plot

      // Get the context for plotting
      const histogramCanvas = document.getElementById("histogramCanvas" + canvasNum);
      const histogramCtx = histogramCanvas.getContext("2d");

      // Erase the canvas
      histogramCtx.clearRect(0, 0, histogramCanvas.width, histogramCanvas.height);

      // Plot the histogram and wait for it to finish
      await GANForecast[canvasNum].plotHistogram(
        histogramCtx,
        x2,
        y2,
        width,
        height,
        maxRain,
        probability,
        latitudeIdx,
        longitudeIdx,
        units,
        barChartSpec,
      );

      // Abort if stale after histogram draw
      if (myGeneration !== drawGeneration) return;
    }
  }
}

init();
