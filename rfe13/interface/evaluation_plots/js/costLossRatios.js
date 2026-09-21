// Javascript for the costLossRatios.html page

// On page load do this:
// Required because menu settings are initially unknown.
async function CostlossSelect() {
	let region = document.getElementById("regionSelect").value;
	
	// Change the sub-region depending upon the region
	let subRegions;
	if (region=="Kenya") {
		subRegions = ["Kiambu, Nairobi and Kajiado-East"];
	} else if (region=="Ethiopia") {
		subRegions = ["Konso and Moyale"];
	} else {
		console.log("ERROR: Unknown region "+region+" in CostlossSelect().");
	};
	updateSubRegionMenu(subRegions);
        regionCostLossSelect();
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
// Sets the threshold cost loss menu to have the specified thresholds
function updateThresholdCostLossMenu(thresholds) {
	
	// Select the HTML select menu that we are updating
	let thresholdSelect = document.getElementById("thresholdCostLossSelect");
	
	// Record the menu's value before we remove it
	let threshold = thresholdSelect.value;
	
	// Remove all of the current menu items
	while (thresholdSelect.hasChildNodes()) {
		thresholdSelect.removeChild(thresholdSelect.firstChild);
	}
		
	// Add the menu items specified in thresholds
	for (let i=0;i<thresholds.length;i++) {
		let option = document.createElement("option");
		option.value = thresholds[i];
		option.innerHTML = thresholds[i];
		thresholdSelect.appendChild(option);
	}
	
	// If the original value does not exist.
	if (!(thresholds.includes(threshold))) {
		threshold = thresholds[thresholds.length-1];	// Pick the final one
	}
	
	// Set the menu to the value it should be
	thresholdSelect.value = threshold;
}

// A user has selected the region costloss menu
function regionCostLossSelect() {
	
	// Get the region
	let region = document.getElementById("regionSelect").value;
	
	// Set the threshold menu
	let thresholds;
	if (region=="Kenya") {
		thresholds = ["40", "50", "60"];	// Must be strings
	} else if (region=="Ethiopia") {
		thresholds = ["25", "30", "40"];	// Must be strings
	} else {
		console.log("ERROR: Unknown region "+region+" in regionCostLossSelect().");
	}
	updateThresholdCostLossMenu(thresholds);
	
	// Get the value of the lead time menu (days + 6 hours)
	let leadTime = document.getElementById("leadTimeCostLossSelect").value;
	
	// Get the value of the threshold menu (mm/day)
	let threshold = document.getElementById("thresholdCostLossSelect").value;
	
	// Get the x axis scale
	let scale = document.getElementById("xScaleCostLossSelect").value;
	
	// Set the picture
	if (scale=="linear") {
		fileName = region+"_casestudy_costloss_"+leadTime+"-day_leadtime_"+threshold+"_mmday.png"
	} else {	// scale=="logarithmic"
		fileName = region+"_casestudy_logscale_costloss_"+leadTime+"-day_leadtime_"+threshold+"_mmday.png"
	}
	document.getElementById("costLossPlot").src = "../costloss/"+fileName
}

// A user has selected the lead time costloss menu
function leadTimeCostLossSelect() {
	// Menus do the same thing
	regionCostLossSelect();
}

// A user has selected the threshold costloss menu
function thresholdCostLossSelect() {
	// Menus do the same thing
	regionCostLossSelect();
}

// A user has selected the scale costloss menu
function xScaleCostLossSelect() {
	// Menus do the same thing
	regionCostLossSelect();
}
