// Javascript for the categoriesOfReliability.html page

// On page load do this:
// Required because menu settings are initially unknown.

// Sets the threshold category of reliability menu to have the specified thresholds
// Required because menu settings are initially unknown.
// A user has selected the threshold category menu

async function thresholdCategorySelect() {
	let region = document.getElementById("regionSelect").value;
	
	// Change the sub-region depending upon the region
	let thresholds;
	if (region=="Kenya") {
		thresholds = ["20","30","40","50"];
	} else if (region=="Ethiopia") {
		thresholds = ["20","30","40","50"];
	} else if (region=="Rwanda") {
		thresholds = ["20","30","40","50"];
	} else if (region=="GHA") {
		thresholds = ["5","20","30","40","50"];
	} else {
		console.log("ERROR: Unknown region "+region+" in thresholdCategorySelect().");
	};
	updateThresholdCatRelMenu(thresholds);
        leadTimeCategorySelect();
}
// Set the thresholds menu
// Sets the threshold cost loss menu to have the specified thresholds
function updateThresholdCatRelMenu(thresholds) {
	
	// Select the HTML select menu that we are updating
	let thresholdSelect = document.getElementById("thresholdCategorySelect");
	
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

function updateLeadTimeMenu(leadTimes) {
	
	// Select the HTML select menu that we are updating
	let leadTimeSelect = document.getElementById("leadTimeCategorySelect");
	
	// Record the menu's value before we remove it
	let leadTime = leadTimeSelect.value;
	
	// Remove all of the current menu items
	while (leadTimeSelect.hasChildNodes()) {
		leadTimeSelect.removeChild(leadTimeSelect.firstChild);
	}
		
	// Add the menu items specified in leadTimes
	for (let i=0;i<leadTimes.length;i++) {
		let option = document.createElement("option");
		option.value = leadTimes[i];
		option.innerHTML = leadTimes[i];
		leadTimeSelect.appendChild(option);
	}
	
	// If the original value does not exist.
	if (!(leadTimes.includes(leadTime))) {
		leadTime = leadTimes[leadTimes.length-1];	// Pick the final one
	}
	
	// Set the menu to the value it should be
	leadTimeSelect.value = leadTime;
}

// A user has selected the lead time category menu
function leadTimeCategorySelect() {
	// Get the region
	let region = document.getElementById("regionSelect").value;
	
	// Set the threshold menu
	let leadTimes;
	if (region=="GHA") {
		leadTimes = ["30","54","78","102","126"];	// Must be strings
	} else if (region=="Kenya") {
		leadTimes = ["30"];	// Must be strings
	} else if (region=="Ethiopia") {
		leadTimes = ["30"];	// Must be strings
	} else if (region=="Rwanda") {
		leadTimes = ["30"];	// Must be strings
	} else {
		console.log("ERROR: Unknown lead time "+region+" in leadTimeCategorySelect().");
	}
	updateLeadTimeMenu(leadTimes);
	// Get the value of the threshold menu (mm/day)
	let threshold = document.getElementById("thresholdCategorySelect").value;
	
	// Get the value of the lead time menu (days + 6 hours)
	let leadTime = document.getElementById("leadTimeCategorySelect").value;
	
	// Set the picture
	document.getElementById("GHACategoryOfReliabilityPlot").src = "../categories_of_reliability/"+region+"_category_of_reliability_"+leadTime+"-hour_leadtime_"+threshold+"_mmday.png"
}

