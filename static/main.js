function disableButton() {
    // Disable the button
    setTimeout(function() {
            // Code to be executed after the delay
            document.getElementById("sendButton").disabled = true;
        }, 1000);
}

// Add event listener for keydown event on the document
document.addEventListener("keydown", function(event) {
    // Check if the shift and enter keys are pressed simultaneously
    if (event.shiftKey && event.keyCode === 13) {
        // Check if the input field is focused
        if (document.activeElement === document.getElementById("requestArea")) {
            // Trigger the button click event
            document.getElementById("sendButton").click();
        }
    }
});