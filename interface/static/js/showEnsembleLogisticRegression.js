// Javascript for plotting the results of the ensemble logistic regression.

let ELRForecast = new ELRData();		// Create a global ELRData object

// Select a menu item requiring data to be loaded
async function ELRSelect() {
	let region = document.getElementById("regionSelect").value;
	
	// Change the sub-region depending upon the region
	let subRegions;
	if (region=="Kenya") {
		subRegions = ["Kiambu","Nairobi","Kajiado-East"];
	} else if (region=="Ethiopia") {
		subRegions = ["Konso","Moyale"];
	} else {
		console.log("ERROR: Unknown region "+region+" in ELRSelect().");
	}
	updateSubRegionMenu(subRegions);
	
	// Load the ELR forecast
	await loadELRForecast();
	
	// Draw the ELR forecast
	await drawPlot();
}

// Change the lead time to plot
async function validTimeSelect() {
	// Draw the ELR forecast
	await drawPlot();
}

// Change the style to plot
async function styleSelect() {
	// Draw the ELR forecast
	await drawPlot();
}

// Change the threshold to plot
async function thresholdSelect() {
	// Draw the ELR forecast
	await drawPlot();
}

// Set the sub region menu
function updateSubRegionMenu(subRegions) {
	
	// Select the HTML select menu that we are updating
	let subRegionSelect = document.getElementById("subRegionSelect");
	
	// Record the menu's value before we remove it
	let subRegion = subRegionSelect.value;
	
	// Remove all of the current menu items
	while (subRegionSelect.hasChildNodes()) {
		subRegionSelect.removeChild(subRegionSelect.firstChild);
	}
	
	// Add the appropriate menu items
	let option;
	for (let i=0; i<subRegions.length;i++) {
		option = document.createElement("option");
		option.value = subRegions[i];
		option.innerHTML = subRegions[i];
		subRegionSelect.appendChild(option);
	}
	
	// If the original value does not exist.
	if (!(subRegions.includes(subRegion))) {
		subRegion = subRegions[subRegions.length-1];	// Pick the final one
	}
	
	// Set the menu to the value it should be
	subRegionSelect.value = subRegion;
}

// Set the threshold menu
// XXX Combine with updateSubRegionMenu into one function
function updateThresholdMenu(thresholds) {
	
	// Select the HTML select menu that we are updating
	let thresholdsSelect = document.getElementById("thresholdSelect");
	
	// Record the menu's value before we remove it
	let threshold = thresholdsSelect.value;
	
	// Remove all of the current menu items
	while (thresholdsSelect.hasChildNodes()) {
		thresholdsSelect.removeChild(thresholdsSelect.firstChild);
	}
	
	// Add the appropriate menu items
	let option;
	for (let i=0; i<thresholds.length;i++) {
		option = document.createElement("option");
		option.value = thresholds[i];
		option.innerHTML = thresholds[i];
		thresholdsSelect.appendChild(option);
	}
	
	// If the original value does not exist.
	if (!(thresholds.includes(threshold))) {
		threshold = thresholds[thresholds.length-1];	// Pick the final one
	}
	
	// Set the menu to the value it should be
	thresholdsSelect.value = threshold;
}

// When the user focus leaves a probability bin edge input
function pBinInput() {
	// Draw the ELR forecast
	drawPlot();
}

// Has an alert been called yet
alertCalledG = false;

// Parse and return the probability bin edges input boxes
async function getPBinEdges() {

	let inputValue;
	let pBinEdges = [];
	
	pBinEdges[0] = 0;
	inputValue = document.getElementById("probabilityBin1").value;
	pBinEdges[1] = parseInt(inputValue);
	inputValue = document.getElementById("probabilityBin2").value;
	pBinEdges[2] = parseInt(inputValue);
	inputValue = document.getElementById("probabilityBin3").value;
	pBinEdges[3] = parseInt(inputValue);
	inputValue = document.getElementById("probabilityBin4").value;
	pBinEdges[4] = parseInt(inputValue);
	pBinEdges[5] = 100;
	
	// Add alert for parse errors
	let err = false;
	for (let i=1;i<pBinEdges.length;i++) {
		
		if (!(pBinEdges[i] >= pBinEdges[i-1])) {
			pBinEdges[i] = pBinEdges[i-1];
			err = true;
		} else if (pBinEdges[i] < 0) {
			pBinEdges[i] = 0;
			err = true;
		} else if (pBinEdges[i] > 100) {
			pBinEdges[i] = 100;
			err = true;
		}
		
		if (err) {
			document.activeElement.blur();
			if (!alertCalledG) {
				alertCalledG = true;
				await alert("Probability bins must be increasing (left to right) and be between 0 and 100.");
			}
			break;
		}
	}
	
	// Now set the boxes to the integer value (removes surplus rubbish)
	document.getElementById("probabilityBin1").value = pBinEdges[1];
	document.getElementById("probabilityBin2").value = pBinEdges[2];
	document.getElementById("probabilityBin3").value = pBinEdges[3];
	document.getElementById("probabilityBin4").value = pBinEdges[4];
	
	alertCalledG = false;
	return pBinEdges;
}

// Loads the currently selected ELR forecast (all lead times and thresholds)
async function loadELRForecast() {
	let region = document.getElementById("regionSelect").value;
	let subRegion = document.getElementById("subRegionSelect").value;
	let year = document.getElementById("initYearSelect").value;
	let month = document.getElementById("initMonthSelect").value;
	let day = document.getElementById("initDaySelect").value;
	
	// XXX Quick hack to get the file name
	let subRegionPath;
	if ((subRegion=="Konso")||(subRegion=="Kiambu")||(subRegion=="Nairobi")) {
		subRegionPath = "/county/";
	} else {
		subRegionPath = "/subcounty/";
	}
	let fileName = "/static/ELR_predictions/"+region+subRegionPath+"GAN_"+subRegion+"_"
					+year+month.padStart(2,'0')+day.padStart(2,'0')+"_logreg.nc";
	
	// Load data into the forecastDataObject
	await ELRForecast.loadELRForecast(fileName);
	
	// Update the threshold menu depending upon the available thresholds
	const thresholds = [];
	for (let i=0;i<ELRForecast.thresholds.length;i++) {
		thresholds[i] = ELRForecast.thresholds[i].toString(10);
	}
	updateThresholdMenu(thresholds);
}

async function drawPlot(){
	
	// Plot attributes
	let regionName = document.getElementById("subRegionSelect").value;
	let style = document.getElementById("styleSelect").value;
	let validTime = document.getElementById("validTimeSelect").value;
	let threshold = document.getElementById("thresholdSelect").value;
	
	// Get the context for plotting
	const canvas = document.getElementById("myCanvas");
	const ctx = canvas.getContext("2d");
	
	// Erase the canvas
	ctx.clearRect(0,0,canvas.width,canvas.height);
	
	let x = 2, y=2;			// Location of plot from top left
	let width = 500;		// Width of plot in pixels
	let height = 500;		// Height of plot in pixels
	
	// Must use await unless all of the region shape data is loaded in advance
	// otherwise the region shape data could be loaded multiple times and corrupted.
	
	// Parse the probability bin edges input boxes
	pBinEdges = await getPBinEdges();
		
	// Draw the ELR forecast
	let plotRect = await ELRForecast.plotExceedenceProbability(ctx, x, y, width, height,
														       style, validTime, threshold, 
														       pBinEdges, regionName);
}

// Function to inform the user what is going on
//    code - 0 = Not waiting
//           1 = Waiting for data to load
//           2 = Waiting for calculations
//           3 = Waiting for plots to draw
// message - A description of what we are waiting for
function showLoadingStatus(code, message) {

	if (code == 0) {	// We are not waiting
		document.getElementById("statusText").style.color = "black";
		
	} else {			// We are waiting
		document.getElementById("statusText").style.color = "#cc0000";	// dark red
	}
	
	// Inform the user what is going on
	document.getElementById("statusText").innerHTML = message;
}

async function init() {
	
	// Specify the function to call to inform the user what is going on
	setStatusUpdateFunction(showLoadingStatus);
	
	// Set appropriate menus
	await ELRSelect();
	
	// Load the currently selected forecast
	await loadELRForecast();
	
	// Detect if the enter or return key is pressed in the document
	document.addEventListener("keydown", function(event) {
		if (event.key === "Enter") {
			drawPlot();
		}
	}); 
	
	// Draw the ELR forecast
	await drawPlot();
}

init();
