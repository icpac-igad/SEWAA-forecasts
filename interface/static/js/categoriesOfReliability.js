// Javascript for the categoriesOfReliability.html page

// On page load do this:
// Required because menu settings are initially unknown.
leadTimeCategorySelect();

// A user has selected the lead time category menu
function leadTimeCategorySelect() {
	
	// Get the value of the lead time menu (days + 6 hours)
	let leadTime = document.getElementById("leadTimeCategorySelect").value;
	
	// Get the value of the threshold menu (mm/day)
	let threshold = document.getElementById("thresholdCategorySelect").value;
	
	// Set the picture
	document.getElementById("GHACategoryOfReliabilityPlot").src = "/static/categories_of_reliability/GHA_category_of_reliability_"+leadTime+"-hour_leadtime_"+threshold+"_mmday.png"
}

// A user has selected the threshold category menu
function thresholdCategorySelect() {
	// Both menus do the same thing
	leadTimeCategorySelect();
}
